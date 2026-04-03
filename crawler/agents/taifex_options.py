"""
TAIFEX 台指選擇權每日行情爬蟲
資料來源: https://www.taifex.com.tw/cht/3/optDataDown
"""

import io
import logging
from datetime import date

import pandas as pd
import requests

from .db import get_connection, upsert, log_crawl

logger = logging.getLogger(__name__)

AGENT_NAME = "taifex_options"
URL = "https://www.taifex.com.tw/cht/3/optDataDown"


def fetch(trade_date: date) -> pd.DataFrame:
    date_str = trade_date.strftime("%Y/%m/%d")
    params = {
        "down_type": "1",
        "commodity_id": "TXO",
        "queryStartDate": date_str,
        "queryEndDate": date_str,
    }
    resp = requests.get(URL, params=params, timeout=60)
    try:
        df = pd.read_csv(io.StringIO(resp.content.decode("big5", errors="replace")), on_bad_lines="skip", index_col=False)
    except Exception:
        logger.warning("options: cannot parse CSV for %s", date_str)
        return pd.DataFrame()
    return df


def parse(df: pd.DataFrame, trade_date: date) -> list[dict]:
    if df.empty:
        return []
    df.columns = [c.strip() for c in df.columns]
    def safe_int(v):
        try:
            return int(float(str(v).replace(",", "") or 0))
        except Exception:
            return 0

    records = []
    for _, row in df.iterrows():
        def safe(col):
            v = row.get(col)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            try:
                return float(str(v).replace(",", ""))
            except Exception:
                return None

        # 買賣權別：Call / Put -> C / P
        cp_raw = str(row.get("買賣權", row.get("CALL/PUT", ""))).strip()
        call_put = "C" if "C" in cp_raw.upper() or "買" in cp_raw else "P"

        records.append({
            "trade_date": trade_date,
            "contract_code": "TXO",
            "contract_month": str(row.get("到期月份(週別)", row.get("到期月份", ""))).strip(),
            "strike_price": safe("履約價") or safe("履約價格"),
            "call_put": call_put,
            "session": str(row.get("交易時段", "一般")).strip() or "一般",
            "open_price": safe("開盤價"),
            "high_price": safe("最高價"),
            "low_price": safe("最低價"),
            "close_price": safe("收盤價"),
            "volume": safe_int(row.get("成交量", 0)),
            "open_interest": safe_int(row.get("未沖銷契約數", 0)),
            "settlement_price": safe("結算價"),
        })
    return [r for r in records if r["strike_price"] is not None]


def run(trade_date: date):
    conn = get_connection()
    try:
        df = fetch(trade_date)
        records = parse(df, trade_date)
        count = upsert(conn, "txo_options_daily", records,
                       ["trade_date", "contract_code", "contract_month", "strike_price", "call_put", "session"])
        log_crawl(conn, AGENT_NAME, str(trade_date), "success", count)
        logger.info("options: %s -> %d rows", trade_date, count)
    except Exception as e:
        log_crawl(conn, AGENT_NAME, str(trade_date), "failed", 0, str(e))
        logger.error("options: %s failed: %s", trade_date, e)
    finally:
        conn.close()
