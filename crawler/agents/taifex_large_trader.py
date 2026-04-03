"""
TAIFEX 大額交易人未沖銷部位爬蟲
資料來源: https://www.taifex.com.tw/cht/3/largeTraderFutDown
         https://www.taifex.com.tw/cht/3/largeTraderOptDown
"""

import io
import logging
from datetime import date

import pandas as pd
import requests

from .db import get_connection, upsert, log_crawl

logger = logging.getLogger(__name__)

AGENT_NAME = "taifex_large_trader"

FUTURES_URL = "https://www.taifex.com.tw/cht/3/largeTraderFutDown"
OPTIONS_URL = "https://www.taifex.com.tw/cht/3/largeTraderOptDown"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.taifex.com.tw/",
}


def _fetch_csv(url: str, trade_date: date) -> pd.DataFrame:
    date_str = trade_date.strftime("%Y/%m/%d")
    params = {
        "queryStartDate": date_str,
        "queryEndDate": date_str,
        "commodity_id": "TX",
    }
    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
    try:
        return pd.read_csv(io.StringIO(resp.content.decode("big5", errors="replace")), on_bad_lines="skip", index_col=False)
    except Exception:
        logger.warning("large_trader: cannot parse CSV from %s for %s", url, date_str)
        return pd.DataFrame()


def _safe_int(v) -> int | None:
    try:
        return int(float(str(v).replace(",", "")))
    except Exception:
        return None


MONTH_LABEL = {
    "666666": "近二個月",
    "999999": "全部月份",
}
TRADER_LABEL = {"0": "全體交易人", "1": "特定法人"}


def parse(df: pd.DataFrame, trade_date: date, contract_code: str) -> list[dict]:
    if df.empty:
        return []
    df.columns = [str(c).strip() for c in df.columns]
    # 過濾目標契約（欄位值有尾部空白）
    contract_col = "商品(契約)"
    if contract_col in df.columns:
        df[contract_col] = df[contract_col].str.strip()
        df = df[df[contract_col] == contract_code]
    if df.empty:
        return []
    records = []
    for _, row in df.iterrows():
        month_raw = str(row.get("到期月份(週別)", "")).strip().split(".")[0]
        trader_raw = str(row.get("交易人類別", "")).strip().split(".")[0]
        month_label = MONTH_LABEL.get(month_raw, month_raw)
        trader_label = TRADER_LABEL.get(trader_raw, trader_raw)
        trader_type = f"{month_label}-{trader_label}"
        records.append({
            "trade_date": trade_date,
            "contract_code": contract_code,
            "trader_type": trader_type,
            "long_position": _safe_int(row.get("前十大交易人買方")),
            "short_position": _safe_int(row.get("前十大交易人賣方")),
            "market_oi": _safe_int(row.get("全市場未沖銷部位數")),
        })
    return records


def run(trade_date: date):
    conn = get_connection()
    total = 0
    try:
        fut_df = _fetch_csv(FUTURES_URL, trade_date)
        fut_records = parse(fut_df, trade_date, "TX")
        total += upsert(conn, "large_trader_positions", fut_records,
                        ["trade_date", "contract_code", "trader_type"])

        opt_df = _fetch_csv(OPTIONS_URL, trade_date)
        opt_records = parse(opt_df, trade_date, "TXO")
        total += upsert(conn, "large_trader_positions", opt_records,
                        ["trade_date", "contract_code", "trader_type"])

        log_crawl(conn, AGENT_NAME, str(trade_date), "success", total)
        logger.info("large_trader: %s -> %d rows", trade_date, total)
    except Exception as e:
        log_crawl(conn, AGENT_NAME, str(trade_date), "failed", 0, str(e))
        logger.error("large_trader: %s failed: %s", trade_date, e)
    finally:
        conn.close()
