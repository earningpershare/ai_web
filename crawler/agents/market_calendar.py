"""
市場交易日判斷

判斷邏輯：直接向 TAIFEX 查詢當日期貨成交資料，
若無任何成交量（空資料 or 全為 0）則判定為休市日。

優點：
- 以期交所實際資料為準，不需自行維護假日表
- 可處理臨時停市、颱風假等非預期休市
- 完全無需人工維護
"""

import logging
import requests
from datetime import date

logger = logging.getLogger(__name__)

FUTURES_URL = "https://www.taifex.com.tw/cht/3/futDataDown"


def is_trading_day(trade_date: date) -> bool:
    """
    回傳 True  = 該日有開盤，可以爬取資料
    回傳 False = 休市（假日、颱風假、臨時停市等）
    """
    date_str = trade_date.strftime("%Y/%m/%d")
    try:
        resp = requests.post(
            FUTURES_URL,
            data={
                "down_type":    "1",
                "commodity_id": "TX",
                "queryStartDate": date_str,
                "queryEndDate":   date_str,
            },
            timeout=15,
        )
        resp.raise_for_status()

        # 解碼（Big5）
        try:
            text = resp.content.decode("big5", errors="replace")
        except Exception:
            text = resp.text

        lines = [l.strip() for l in text.splitlines() if l.strip()]

        # 只有 header（1行）或完全空白 → 休市
        if len(lines) <= 1:
            logger.info("market_calendar: %s — 無資料，判定休市", trade_date)
            return False

        # 找有成交量的資料行（第一個非 header 行的第5欄為成交量）
        for line in lines[1:]:
            cols = [c.strip() for c in line.split(",")]
            # 成交量欄位為空或 "-" 或 "0" → 休市
            if len(cols) >= 5:
                vol = cols[4].replace(",", "").replace("-", "").strip()
                if vol and vol != "0":
                    logger.info("market_calendar: %s — 有成交量 %s，開盤", trade_date, vol)
                    return True

        logger.info("market_calendar: %s — 成交量為 0，判定休市", trade_date)
        return False

    except Exception as e:
        # 網路錯誤時保守處理：假設有開盤，讓後續 agent 自行處理
        logger.warning("market_calendar: %s — 無法確認，預設視為開盤: %s", trade_date, e)
        return True
