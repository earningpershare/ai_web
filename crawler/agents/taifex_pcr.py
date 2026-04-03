"""
TAIFEX Put/Call Ratio 爬蟲
資料來源: https://www.taifex.com.tw/cht/3/pcRatio
"""

import logging
from datetime import date

import pandas as pd
import requests

from .db import get_connection, upsert, log_crawl

logger = logging.getLogger(__name__)

AGENT_NAME = "taifex_pcr"
URL = "https://www.taifex.com.tw/cht/3/pcRatio"


def fetch(trade_date: date) -> pd.DataFrame:
    date_str = trade_date.strftime("%Y/%m/%d")
    params = {
        "queryStartDate": date_str,
        "queryEndDate": date_str,
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.taifex.com.tw/cht/3/pcRatio",
    }
    resp = requests.get(URL, params=params, headers=headers, timeout=30)
    resp.encoding = "utf-8-sig"
    try:
        tables = pd.read_html(resp.text, header=0)
    except Exception:
        logger.warning("pcr: cannot parse HTML for %s", date_str)
        return pd.DataFrame()
    for t in tables:
        if t.shape[1] >= 5:
            return t
    return pd.DataFrame()


def parse(df: pd.DataFrame, trade_date: date) -> list[dict]:
    if df.empty:
        return []
    df.columns = [str(c).strip() for c in df.columns]

    def safe_int(v):
        try:
            return int(float(str(v).replace(",", "")))
        except Exception:
            return None

    def safe_float(v):
        try:
            return float(str(v).replace(",", ""))
        except Exception:
            return None

    # 取第一筆（當日）
    row = df.iloc[0]
    col_map = {c.lower(): c for c in df.columns}

    def get(keys):
        for k in keys:
            for col_lower, col_orig in col_map.items():
                if k in col_lower:
                    return row[col_orig]
        return None

    return [{
        "trade_date": trade_date,
        "call_oi": safe_int(get(["call未平倉", "call oi", "買權未平倉"])),
        "put_oi": safe_int(get(["put未平倉", "put oi", "賣權未平倉"])),
        "pc_oi_ratio": safe_float(get(["未平倉比率", "p/c oi", "oi比"])),
        "call_volume": safe_int(get(["call成交量", "call volume", "買權成交"])),
        "put_volume": safe_int(get(["put成交量", "put volume", "賣權成交"])),
        "pc_vol_ratio": safe_float(get(["成交量比率", "p/c vol", "volume比"])),
    }]


def run(trade_date: date):
    conn = get_connection()
    try:
        df = fetch(trade_date)
        records = parse(df, trade_date)
        count = upsert(conn, "put_call_ratio", records, ["trade_date"])
        log_crawl(conn, AGENT_NAME, str(trade_date), "success", count)
        logger.info("pcr: %s -> %d rows", trade_date, count)
    except Exception as e:
        log_crawl(conn, AGENT_NAME, str(trade_date), "failed", 0, str(e))
        logger.error("pcr: %s failed: %s", trade_date, e)
    finally:
        conn.close()
