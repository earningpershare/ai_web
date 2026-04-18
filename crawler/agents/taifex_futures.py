"""
TAIFEX 台指期貨每日行情爬蟲

資料來源:
- 歷史/回填: https://www.taifex.com.tw/cht/3/futDataDown （依日期查詢，CSV Big5）
- 最新行情: https://openapi.taifex.com.tw/v1/DailyMarketReportFut （JSON，無日期篩選，回最新交易日）
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
OPENAPI_URL = "https://openapi.taifex.com.tw/v1/DailyMarketReportFut"
TARGET_CONTRACTS = {"TX", "MTX", "MXF"}  # 台指期、小台指、微台指


def fetch(trade_date: date) -> pd.DataFrame:
    """futDataDown：依日期查詢，用於回填或特定日期補抓。"""
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
    df.columns = [c.strip() for c in df.columns]

    def safe_int(v):
        try:
            s = str(v).replace(",", "").strip()
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


def fetch_latest() -> list[dict]:
    """OpenAPI：取最新交易日所有期貨行情（JSON），自動忽略日期參數，回最新。"""
    resp = requests.get(OPENAPI_URL, headers={"Accept": "application/json"}, timeout=30)
    resp.raise_for_status()
    return [item for item in resp.json() if item.get("Contract", "").strip() in TARGET_CONTRACTS]


def _parse_openapi_record(item: dict) -> dict | None:
    def _f(v):
        try:
            s = str(v).replace(",", "").strip()
            if s in ("", "-", "–", "—", "nan", "None", "NULL"):
                return None
            return float(s)
        except Exception:
            return None

    def _i(v):
        try:
            s = str(v).replace(",", "").strip()
            if s in ("", "-", "–", "—", "nan", "None", "NULL"):
                return 0
            return int(float(s))
        except Exception:
            return 0

    date_str = item.get("Date", "")
    if not date_str or len(date_str) != 8:
        return None
    try:
        td = date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    except Exception:
        return None

    cm = item.get("ContractMonth(Week)", "").strip()
    if "/" in cm:  # 跳過價差合約
        return None

    return {
        "trade_date": td,
        "contract_code": item.get("Contract", "").strip(),
        "contract_month": cm,
        "session": item.get("TradingSession", "一般").strip() or "一般",
        "open_price": _f(item.get("Open")),
        "high_price": _f(item.get("High")),
        "low_price": _f(item.get("Low")),
        "close_price": _f(item.get("Last")),
        "volume": _i(item.get("Volume")),
        "open_interest": _i(item.get("OpenInterest")),
        "settlement_price": _f(item.get("SettlementPrice")),
    }


def run(trade_date: date):
    """依日期抓取並 upsert（用於 taifex_daily DAG 和回填）。"""
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


def run_latest():
    """用 OpenAPI 更新最新交易日行情（供 taifex_night_report DAG 在 07:30 補爬夜盤終盤用）。"""
    conn = get_connection()
    try:
        items = fetch_latest()
        records = [r for item in items if (r := _parse_openapi_record(item)) is not None]
        if not records:
            logger.warning("futures openapi: no records returned")
            return
        trade_dates = sorted({str(r["trade_date"]) for r in records})
        count = upsert(conn, "tx_futures_daily", records,
                       ["trade_date", "contract_code", "contract_month", "session"])
        log_crawl(conn, AGENT_NAME, ",".join(trade_dates), "success", count)
        logger.info("futures openapi: trade_dates=%s -> %d rows", trade_dates, count)
    except Exception as e:
        log_crawl(conn, AGENT_NAME, "latest", "failed", 0, str(e))
        logger.error("futures openapi latest failed: %s", e)
    finally:
        conn.close()
