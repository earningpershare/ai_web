"""
TAIFEX 三大法人 期貨 + 選擇權 爬蟲
期貨: https://www.taifex.com.tw/cht/3/futContractsDateDown  (CSV)
選擇權: https://www.taifex.com.tw/cht/3/callsAndPutsDateDown (CSV, Call/Put 分開)
"""

import io
import logging
from datetime import date

import pandas as pd
import requests

from .db import get_connection, upsert, log_crawl

logger = logging.getLogger(__name__)

AGENT_NAME = "taifex_institutional"

FUTURES_URL = "https://www.taifex.com.tw/cht/3/futContractsDateDown"
OPTIONS_URL = "https://www.taifex.com.tw/cht/3/callsAndPutsDateDown"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.taifex.com.tw/",
}

TARGET_FUTURES_CONTRACTS = {"臺股期貨", "小型臺指期貨", "微型臺指期貨"}
TARGET_OPTIONS_CONTRACTS = {"臺指選擇權"}


def _fetch_csv(url: str, trade_date: date) -> pd.DataFrame:
    date_str = trade_date.strftime("%Y/%m/%d")
    resp = requests.post(
        url,
        data={"queryStartDate": date_str, "queryEndDate": date_str},
        headers=HEADERS,
        timeout=30,
    )
    try:
        return pd.read_csv(
            io.StringIO(resp.content.decode("cp950", errors="replace")),
            index_col=False,
        )
    except Exception:
        logger.warning("institutional: cannot parse CSV from %s for %s", url, date_str)
        return pd.DataFrame()


def _safe_int(v) -> int | None:
    try:
        s = str(v).replace(",", "").strip()
        # TAIFEX 用 "-" 或 "–" 表示無資料
        if s in ("", "-", "–", "—", "nan", "None"):
            return None
        return int(float(s))
    except Exception:
        return None


# ── 期貨 ────────────────────────────────────────────────────────────────────

def parse_futures(df: pd.DataFrame, trade_date: date) -> list[dict]:
    if df.empty:
        return []
    df.columns = [str(c).strip() for c in df.columns]
    df["商品名稱"] = df["商品名稱"].str.strip()
    df["身份別"] = df["身份別"].str.strip()
    df = df[df["商品名稱"].isin(TARGET_FUTURES_CONTRACTS)]
    records = []
    for _, row in df.iterrows():
        records.append({
            "trade_date": trade_date,
            "contract_code": row["商品名稱"],
            "institution_type": row["身份別"],
            "long_volume": _safe_int(row.get("多方交易口數")),
            "long_amount": _safe_int(row.get("多方交易契約金額(千元)")),
            "short_volume": _safe_int(row.get("空方交易口數")),
            "short_amount": _safe_int(row.get("空方交易契約金額(千元)")),
            "net_volume": _safe_int(row.get("多空交易口數淨額")),
            "net_amount": _safe_int(row.get("多空交易契約金額淨額(千元)")),
            "long_oi": _safe_int(row.get("多方未平倉口數")),
            "short_oi": _safe_int(row.get("空方未平倉口數")),
            "net_oi": _safe_int(row.get("多空未平倉口數淨額")),
        })
    return records


# ── 選擇權 (callsAndPutsDateDown: CALL/PUT 分開) ────────────────────────────

def parse_options(df: pd.DataFrame, trade_date: date) -> list[dict]:
    """
    callsAndPutsDateDown 欄位:
    日期, 商品名稱, 買賣權別(CALL/PUT), 身份別,
    買方交易口數, 買方交易契約金額(千元),
    賣方交易口數, 賣方交易契約金額(千元),
    交易口數買賣淨額, 交易契約金額買賣淨額(千元),
    買方未平倉口數, 買方未平倉契約金額(千元),
    賣方未平倉口數, 賣方未平倉契約金額(千元),
    未平倉口數買賣淨額, 未平倉契約金額買賣淨額(千元)
    """
    if df.empty:
        return []
    df.columns = [str(c).strip() for c in df.columns]
    df["商品名稱"] = df["商品名稱"].str.strip()
    df["身份別"] = df["身份別"].str.strip()
    df["買賣權別"] = df["買賣權別"].str.strip().str.upper()
    df = df[df["商品名稱"].isin(TARGET_OPTIONS_CONTRACTS)]

    # 每個 (institution, call/put) 一筆 → 合併成 (institution) 一筆
    by_inst = {}
    for _, row in df.iterrows():
        inst = row["身份別"]
        cp = row["買賣權別"]  # 'CALL' or 'PUT'
        if inst not in by_inst:
            by_inst[inst] = {}
        by_inst[inst][cp] = row

    records = []
    for inst, cp_data in by_inst.items():
        call = cp_data.get("CALL", {})
        put = cp_data.get("PUT", {})

        def gi(row, col):
            return _safe_int(row.get(col)) if isinstance(row, dict) or hasattr(row, 'get') else None

        records.append({
            "trade_date": trade_date,
            "contract_code": "臺指選擇權",
            "institution_type": inst,
            # CALL
            "call_buy_volume":  gi(call, "買方交易口數"),
            "call_buy_amount":  gi(call, "買方交易契約金額(千元)"),
            "call_sell_volume": gi(call, "賣方交易口數"),
            "call_sell_amount": gi(call, "賣方交易契約金額(千元)"),
            "call_net_volume":  gi(call, "交易口數買賣淨額"),
            "call_net_amount":  gi(call, "交易契約金額買賣淨額(千元)"),
            "call_buy_oi":      gi(call, "買方未平倉口數"),
            "call_sell_oi":     gi(call, "賣方未平倉口數"),
            "call_net_oi":      gi(call, "未平倉口數買賣淨額"),
            # PUT
            "put_buy_volume":   gi(put, "買方交易口數"),
            "put_buy_amount":   gi(put, "買方交易契約金額(千元)"),
            "put_sell_volume":  gi(put, "賣方交易口數"),
            "put_sell_amount":  gi(put, "賣方交易契約金額(千元)"),
            "put_net_volume":   gi(put, "交易口數買賣淨額"),
            "put_net_amount":   gi(put, "交易契約金額買賣淨額(千元)"),
            "put_buy_oi":       gi(put, "買方未平倉口數"),
            "put_sell_oi":      gi(put, "賣方未平倉口數"),
            "put_net_oi":       gi(put, "未平倉口數買賣淨額"),
        })
    return records


def run(trade_date: date):
    conn = get_connection()
    total = 0
    try:
        fut_df = _fetch_csv(FUTURES_URL, trade_date)
        fut_records = parse_futures(fut_df, trade_date)
        total += upsert(conn, "institutional_futures", fut_records,
                        ["trade_date", "contract_code", "institution_type"])

        opt_df = _fetch_csv(OPTIONS_URL, trade_date)
        opt_records = parse_options(opt_df, trade_date)
        total += upsert(conn, "institutional_options", opt_records,
                        ["trade_date", "contract_code", "institution_type"])

        log_crawl(conn, AGENT_NAME, str(trade_date), "success", total)
        logger.info("institutional: %s -> %d rows", trade_date, total)
    except Exception as e:
        log_crawl(conn, AGENT_NAME, str(trade_date), "failed", 0, str(e))
        logger.error("institutional: %s failed: %s", trade_date, e)
    finally:
        conn.close()
