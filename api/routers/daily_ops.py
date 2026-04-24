"""
每日操作日誌端點

GET    /daily-ops                — 列出已發布操作日誌（分頁）
GET    /daily-ops/{id}           — 取得單筆
POST   /daily-ops                — 新增（需 admin token）
PUT    /daily-ops/{id}           — 編輯（需 admin token）
DELETE /daily-ops/{id}           — 刪除（需 admin token）
POST   /daily-ops/trading-ingest — 本機交易系統上傳當日摘要（需 TRADING_INGEST_SECRET）
"""

import logging
import os
from datetime import date
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel

from .db import get_conn, query
from .auth import _current_user

router = APIRouter(prefix="/daily-ops", tags=["daily-ops"])
log = logging.getLogger(__name__)

_DAILY_OPS_EDITORS = {
    "ohmygot65@yahoo.com.tw",
    "somehandisfrank@gmail.com",
}


# ── 管理員驗證 ────────────────────────────────────────────────────────────────

def _require_admin(authorization: str):
    """驗證 token 且確認為每日操作編輯者"""
    user = _current_user(authorization)
    if (user.email or "").lower().strip() not in _DAILY_OPS_EDITORS:
        raise HTTPException(status_code=403, detail="此操作僅限管理員")
    return user


# ── Schemas ───────────────────────────────────────────────────────────────────

class DailyOpBody(BaseModel):
    trade_date: date
    title: str
    trigger_indicators: Optional[str] = None
    direction: Optional[str] = None          # 做多/做空/出場/觀望
    entry_price: Optional[Decimal] = None
    entry_contracts: Optional[int] = None
    exit_price: Optional[Decimal] = None
    pnl: Optional[Decimal] = None
    pnl_note: Optional[str] = None
    content: Optional[str] = None
    is_published: bool = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
def list_daily_ops(
    limit: int = Query(default=30, le=100),
    offset: int = Query(default=0, ge=0),
):
    """列出已發布操作日誌（依交易日期降序）"""
    return query(
        """
        SELECT * FROM daily_operations
        WHERE is_published = TRUE
        ORDER BY trade_date DESC, created_at DESC
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    )


@router.get("/{op_id}")
def get_daily_op(op_id: int):
    """取得單筆操作日誌"""
    rows = query(
        """
        SELECT * FROM daily_operations
        WHERE id = %s AND is_published = TRUE
        """,
        (op_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="操作日誌不存在或尚未發布")
    return rows[0]


@router.post("", status_code=201)
def create_daily_op(body: DailyOpBody, authorization: str = Header(default="")):
    """新增操作日誌（需 admin token）"""
    _require_admin(authorization)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO daily_operations
                    (trade_date, title, trigger_indicators, direction,
                     entry_price, entry_contracts, exit_price,
                     pnl, pnl_note, content, is_published)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING *
                """,
                (
                    body.trade_date,
                    body.title,
                    body.trigger_indicators,
                    body.direction,
                    body.entry_price,
                    body.entry_contracts,
                    body.exit_price,
                    body.pnl,
                    body.pnl_note,
                    body.content,
                    body.is_published,
                ),
            )
            row = dict(cur.fetchone())
        conn.commit()
    log.info("管理員新增操作日誌 id=%s trade_date=%s", row["id"], row["trade_date"])
    return row


@router.put("/{op_id}")
def update_daily_op(
    op_id: int,
    body: DailyOpBody,
    authorization: str = Header(default=""),
):
    """編輯操作日誌（需 admin token）"""
    _require_admin(authorization)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE daily_operations
                SET trade_date=%s, title=%s, trigger_indicators=%s, direction=%s,
                    entry_price=%s, entry_contracts=%s, exit_price=%s,
                    pnl=%s, pnl_note=%s, content=%s, is_published=%s
                WHERE id = %s
                RETURNING *
                """,
                (
                    body.trade_date,
                    body.title,
                    body.trigger_indicators,
                    body.direction,
                    body.entry_price,
                    body.entry_contracts,
                    body.exit_price,
                    body.pnl,
                    body.pnl_note,
                    body.content,
                    body.is_published,
                    op_id,
                ),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="操作日誌不存在")
            row = dict(row)
        conn.commit()
    log.info("管理員更新操作日誌 id=%s", op_id)
    return row


@router.delete("/{op_id}")
def delete_daily_op(op_id: int, authorization: str = Header(default="")):
    """刪除操作日誌（需 admin token）"""
    _require_admin(authorization)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM daily_operations WHERE id = %s RETURNING id",
                (op_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="操作日誌不存在")
        conn.commit()
    log.info("管理員刪除操作日誌 id=%s", op_id)
    return {"ok": True, "deleted_id": op_id}


# ── 本機交易系統上傳端點 ──────────────────────────────────────────────────────────

TRADING_INGEST_SECRET = os.getenv("TRADING_INGEST_SECRET", "")


class TradeRecord(BaseModel):
    direction: str          # long / short
    symbol: str
    entry_price: float
    exit_price: Optional[float] = None
    pnl_pts: Optional[int] = None
    pnl_twd: Optional[int] = None
    playbook: Optional[str] = None
    exit_reason: Optional[str] = None
    reasoning: Optional[str] = None


class TradingIngestBody(BaseModel):
    trade_date: date
    session: str                        # "night" or "day"
    trades: List[TradeRecord]
    total_pnl_twd: Optional[int] = None
    markdown_report: Optional[str] = None   # 完整 MD 復盤，直接存入 content
    preface: Optional[str] = None           # 首次寫序文（今日第一篇）


@router.post("/trading-ingest", status_code=201)
def trading_ingest(
    body: TradingIngestBody,
    x_trading_secret: str = Header(default=""),
):
    """
    本機 AI 交易系統每日 14:00 自動上傳當日/昨日夜盤摘要。
    驗證：X-Trading-Secret header 對比環境變數 TRADING_INGEST_SECRET。
    同一 (trade_date, session) 已存在則更新，否則新增。
    """
    if not TRADING_INGEST_SECRET or x_trading_secret != TRADING_INGEST_SECRET:
        raise HTTPException(status_code=403, detail="無效的 Trading Secret")

    wins = sum(1 for t in body.trades if (t.pnl_pts or 0) > 0)
    losses = sum(1 for t in body.trades if (t.pnl_pts or 0) < 0)
    total = len(body.trades)
    session_label = "夜盤" if body.session == "night" else "日盤"
    pnl_twd = body.total_pnl_twd or sum(t.pnl_twd or 0 for t in body.trades)
    pnl_sign = "✅" if pnl_twd >= 0 else "❌"

    title = f"{body.trade_date}｜{session_label}｜{total}筆 {wins}勝{losses}負"
    pnl_note = f"{pnl_sign} NT${pnl_twd:+,}"

    # direction 取多數
    shorts = sum(1 for t in body.trades if t.direction == "short")
    longs = total - shorts
    direction = "做空" if shorts >= longs else "做多"

    # content = 序文（若有） + markdown 復盤
    content_parts = []
    if body.preface:
        content_parts.append(body.preface)
    if body.markdown_report:
        content_parts.append(body.markdown_report)
    content = "\n\n---\n\n".join(content_parts) if content_parts else None

    session_key = f"{body.trade_date}_{body.session}"

    with get_conn() as conn:
        with conn.cursor() as cur:
            # 先查同 (trade_date, session_key in title)
            cur.execute(
                """
                SELECT id FROM daily_operations
                WHERE trade_date = %s AND title LIKE %s
                LIMIT 1
                """,
                (body.trade_date, f"%{session_label}%"),
            )
            existing = cur.fetchone()

            if existing:
                cur.execute(
                    """
                    UPDATE daily_operations
                    SET title=%s, direction=%s, pnl=%s, pnl_note=%s, content=%s, is_published=TRUE
                    WHERE id=%s RETURNING id
                    """,
                    (title, direction, pnl_twd, pnl_note, content, existing["id"]),
                )
                row = dict(cur.fetchone())
                log.info("trading-ingest 更新 id=%s date=%s session=%s", row["id"], body.trade_date, body.session)
                result_id = row["id"]
                action = "updated"
            else:
                cur.execute(
                    """
                    INSERT INTO daily_operations
                        (trade_date, title, direction, pnl, pnl_note, content, is_published)
                    VALUES (%s,%s,%s,%s,%s,%s,TRUE)
                    RETURNING id
                    """,
                    (body.trade_date, title, direction, pnl_twd, pnl_note, content),
                )
                row = dict(cur.fetchone())
                result_id = row["id"]
                log.info("trading-ingest 新增 id=%s date=%s session=%s", result_id, body.trade_date, body.session)
                action = "created"
        conn.commit()

    return {"ok": True, "action": action, "id": result_id, "title": title, "pnl_twd": pnl_twd}
