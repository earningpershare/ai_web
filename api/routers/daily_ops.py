"""
每日操作日誌端點

GET    /daily-ops          — 列出已發布操作日誌（分頁）
GET    /daily-ops/{id}     — 取得單筆
POST   /daily-ops          — 新增（需 admin token）
PUT    /daily-ops/{id}     — 編輯（需 admin token）
DELETE /daily-ops/{id}     — 刪除（需 admin token）
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel

from .db import get_conn, query
from .auth import _current_user

router = APIRouter(prefix="/daily-ops", tags=["daily-ops"])
log = logging.getLogger(__name__)

ADMIN_EMAIL = "ohmygot65@yahoo.com.tw"


# ── 管理員驗證 ────────────────────────────────────────────────────────────────

def _require_admin(authorization: str):
    """驗證 token 且確認為管理員帳號"""
    user = _current_user(authorization)
    if (user.email or "").lower() != ADMIN_EMAIL:
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
