"""
爬蟲排程入口
- 每日 17:00 (Asia/Taipei) 執行所有 TAIFEX 爬蟲
- 啟動時自動回補近 5 個交易日資料
"""

import logging
import time
from datetime import date

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from agents import (
    taifex_futures,
    taifex_options,
    taifex_pcr,
    taifex_institutional,
    taifex_large_trader,
    data_validator,
)
from agents.utils import get_last_n_trading_days

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler")

AGENTS = [
    taifex_futures,
    taifex_options,
    taifex_pcr,
    taifex_institutional,
    taifex_large_trader,
]


def run_all(trade_date: date):
    logger.info("=== 開始爬取 %s ===", trade_date)
    for agent in AGENTS:
        try:
            agent.run(trade_date)
        except Exception as e:
            logger.error("agent %s 執行失敗: %s", agent.AGENT_NAME, e)
    # 資料驗證在所有爬蟲完成後執行
    try:
        data_validator.run(trade_date)
    except Exception as e:
        logger.error("data_validator 執行失敗: %s", e)
    logger.info("=== 完成 %s ===", trade_date)


def daily_job():
    """每日排程任務：抓取前一個交易日資料（收盤後執行）"""
    today = date.today()
    # 取前一個工作日（週一執行時取上週五）
    trading_days = get_last_n_trading_days(1)
    if trading_days:
        run_all(trading_days[0])


def backfill():
    """啟動時回補最近 5 個交易日"""
    logger.info("開始回補近 5 個交易日資料...")
    trading_days = get_last_n_trading_days(5)
    for d in trading_days:
        run_all(d)
        time.sleep(2)  # 避免對期交所發出過密請求
    logger.info("回補完成")


if __name__ == "__main__":
    # 1. 先回補歷史資料
    backfill()

    # 2. 啟動每日排程：台灣時間 17:00
    scheduler = BlockingScheduler(timezone="Asia/Taipei")
    scheduler.add_job(
        daily_job,
        trigger=CronTrigger(hour=17, minute=0, timezone="Asia/Taipei"),
        id="daily_taifex",
        name="TAIFEX 每日爬蟲",
        misfire_grace_time=3600,  # 允許最多 1 小時延遲啟動
    )
    logger.info("排程已啟動，每日 17:00 (Asia/Taipei) 執行")
    scheduler.start()
