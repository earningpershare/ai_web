"""
每日資料完整性驗證 Agent
確認當日所有爬蟲資料都已正確寫入
"""

import logging
from datetime import date

from .db import get_connection, log_crawl

logger = logging.getLogger(__name__)

AGENT_NAME = "data_validator"

CHECKS = [
    ("tx_futures_daily", "期貨行情"),
    ("txo_options_daily", "選擇權行情"),
    ("put_call_ratio", "PCR"),
    ("institutional_futures", "三大法人期貨"),
    ("institutional_options", "三大法人選擇權"),
    ("large_trader_positions", "大額交易人"),
]


def run(trade_date: date):
    conn = get_connection()
    issues = []
    try:
        with conn.cursor() as cur:
            for table, label in CHECKS:
                cur.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE trade_date = %s",
                    (trade_date,),
                )
                count = cur.fetchone()[0]
                if count == 0:
                    issues.append(f"{label}({table}): 0 筆，可能未爬取或當日無資料")
                    logger.warning("validator: %s has 0 rows for %s", table, trade_date)
                else:
                    logger.info("validator: %s has %d rows for %s", table, count, trade_date)

        status = "failed" if issues else "success"
        message = "; ".join(issues) if issues else "all tables OK"
        log_crawl(conn, AGENT_NAME, str(trade_date), status, 0, message)

        if issues:
            logger.warning("validator: issues on %s -> %s", trade_date, message)
        else:
            logger.info("validator: %s all OK", trade_date)
    except Exception as e:
        log_crawl(conn, AGENT_NAME, str(trade_date), "failed", 0, str(e))
        logger.error("validator: %s error: %s", trade_date, e)
    finally:
        conn.close()
