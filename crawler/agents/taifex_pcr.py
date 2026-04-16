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
            s = str(v).replace(",", "").strip()
            # TAIFEX 用 "-" 或 "–" 表示無資料
            if s in ("", "-", "–", "—", "nan", "None"):
                return None
            return int(float(s))
        except Exception:
            return None

    def safe_float(v):
        try:
            s = str(v).replace(",", "").replace("%", "").strip()
            # TAIFEX 用 "-" 或 "–" 表示無資料
            if s in ("", "-", "–", "—", "nan", "None"):
                return None
            return float(s)
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

    call_oi = safe_int(get(["call未平倉", "call oi", "買權未平倉"]))
    put_oi = safe_int(get(["put未平倉", "put oi", "賣權未平倉"]))
    call_volume = safe_int(get(["call成交量", "call volume", "買權成交"]))
    put_volume = safe_int(get(["put成交量", "put volume", "賣權成交"]))

    # 嘗試解析欄位值；若解析失敗，從 put/call 自行計算
    pc_oi_ratio = safe_float(get([
        "未平倉量比率", "未平倉比率", "p/c oi", "oi比",
        "put/call ratio", "put/call未平倉",
    ]))
    if pc_oi_ratio is None and call_oi and put_oi and call_oi > 0:
        pc_oi_ratio = round(put_oi / call_oi * 100, 4)

    pc_vol_ratio = safe_float(get(["成交量比率", "p/c vol", "volume比"]))
    if pc_vol_ratio is None and call_volume and put_volume and call_volume > 0:
        pc_vol_ratio = round(put_volume / call_volume * 100, 4)

    return [{
        "trade_date": trade_date,
        "call_oi": call_oi,
        "put_oi": put_oi,
        "pc_oi_ratio": pc_oi_ratio,
        "call_volume": call_volume,
        "put_volume": put_volume,
        "pc_vol_ratio": pc_vol_ratio,
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
