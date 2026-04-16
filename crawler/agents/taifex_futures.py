"""
TAIFEX 台指期貨每日行情爬蟲
資料來源: https://www.taifex.com.tw/cht/3/futDataDown
"""

import io
import logging
from datetime import date

import pandas as pd
import requests

from .db import get_connection, upsert, log_crawl

logger = logging.getLogger(__name__)

AGENT_NAME = "taifex_futures"
URL = "https://www.taifex.com.tw/cht/3/futDataDown"
TARGET_CONTRACTS = {"TX", "MTX", "MXF"}  # 台指期、小台指、微台指


def fetch(trade_date: date) -> pd.DataFrame:
    date_str = trade_date.strftime("%Y/%m/%d")
    params = {
        "down_type": "1",
        "commodity_id": "TX",
        "queryStartDate": date_str,
        "queryEndDate": date_str,
    }
    rows = []
    for contract in TARGET_CONTRACTS:
        params["commodity_id"] = contract
        resp = requests.get(URL, params=params, timeout=30)
        try:
            df = pd.read_csv(io.StringIO(resp.content.decode("big5", errors="replace")), on_bad_lines="skip", index_col=False)
        except Exception:
            logger.warning("futures: cannot parse CSV for %s on %s", contract, date_str)
            continue
        if df.empty:
            continue
        df["_contract"] = contract
        rows.append(df)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def parse(df: pd.DataFrame, trade_date: date) -> list[dict]:
    if df.empty:
        return []
    # 欄位名稱正規化（去除空白）
    df.columns = [c.strip() for c in df.columns]
    def safe_int(v):
        try:
            s = str(v).replace(",", "").strip()
            # TAIFEX 用 "-" 或 "–" 表示無資料
            if s in ("", "-", "–", "—", "nan", "None"):
                return 0
            return int(float(s))
        except Exception:
            return 0

    records = []
    for _, row in df.iterrows():
        def safe(col, default=None):
            v = row.get(col, default)
            if pd.isna(v) if v is not None else False:
                return None
            try:
                s = str(v).replace(",", "").strip()
                # TAIFEX 用 "-" 或 "–" 表示無資料
                if s in ("", "-", "–", "—", "nan", "None"):
                    return None
                return float(s)
            except Exception:
                return None

        records.append({
            "trade_date": trade_date,
            "contract_code": str(row.get("_contract", "")).strip(),
            "contract_month": str(row.get("到期月份(週別)", row.get("到期月份", ""))).strip(),
            "session": str(row.get("交易時段", "一般")).strip() or "一般",
            "open_price": safe("開盤價"),
            "high_price": safe("最高價"),
            "low_price": safe("最低價"),
            "close_price": safe("收盤價"),
            "volume": safe_int(row.get("成交量", 0)),
            "open_interest": safe_int(row.get("未沖銷契約數", 0)),
            "settlement_price": safe("結算價"),
        })
    return records


def run(trade_date: date):
    conn = get_connection()
    try:
        df = fetch(trade_date)
        records = parse(df, trade_date)
        count = upsert(conn, "tx_futures_daily", records,
                       ["trade_date", "contract_code", "contract_month", "session"])
        log_crawl(conn, AGENT_NAME, str(trade_date), "success", count)
        logger.info("futures: %s -> %d rows", trade_date, count)
    except Exception as e:
        log_crawl(conn, AGENT_NAME, str(trade_date), "failed", 0, str(e))
        logger.error("futures: %s failed: %s", trade_date, e)
    finally:
        conn.close()
