"""
市場衍生指標端點：direction / itm-otm / max-pain / oi-structure / dealer-map
（資料由 derived_metrics pipeline 預計算後存入 DB）
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query

from .db import query

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/direction")
def get_market_direction(
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    group: Optional[str] = Query(default=None),
    limit: int = Query(default=60, le=500),
):
    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(days=90)
    group_filter = " AND group_type = %s" if group else ""
    params: list = [start, end]
    if group:
        params.append(group)
    params.append(limit)
    return query(
        f"""
        SELECT * FROM market_direction
        WHERE trade_date BETWEEN %s AND %s{group_filter}
        ORDER BY trade_date DESC, group_type
        LIMIT %s
        """,
        params,
    )


@router.get("/itm-otm")
def get_itm_otm(
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    limit: int = Query(default=60, le=500),
):
    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(days=90)
    return query(
        """
        SELECT * FROM market_itm_otm
        WHERE trade_date BETWEEN %s AND %s
        ORDER BY trade_date DESC
        LIMIT %s
        """,
        (start, end, limit),
    )


@router.get("/max-pain")
def get_max_pain(
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    limit: int = Query(default=60, le=500),
):
    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(days=90)
    return query(
        """
        SELECT * FROM market_max_pain
        WHERE trade_date BETWEEN %s AND %s
        ORDER BY trade_date DESC
        LIMIT %s
        """,
        (start, end, limit),
    )


@router.get("/dealer-map")
def get_dealer_map(
    trade_date: Optional[date] = Query(default=None),
):
    """
    莊家地圖 — 聚合選擇權賣方壓力/支撐帶、法人方向、現價
    一次回傳所有前端需要的指標，減少多次 API 呼叫。
    """
    # 若未指定日期，取最新有資料的交易日
    if trade_date is None:
        rows = query(
            "SELECT MAX(trade_date) AS d FROM options_strike_avg_cost"
        )
        trade_date = rows[0]["d"] if rows and rows[0]["d"] else date.today() - timedelta(days=1)

    # 取得前一交易日（用於計算法人 OI 變化）
    prev_rows = query(
        "SELECT MAX(trade_date) AS d FROM options_strike_avg_cost WHERE trade_date < %s",
        (trade_date,),
    )
    prev_date = prev_rows[0]["d"] if prev_rows and prev_rows[0]["d"] else None

    # 1. 取得當月（最近到期）的逐履約價 OI + delta_oi + avg_cost
    #    只取 OI > 500 的有意義履約價，避免雜訊
    strikes = query(
        """
        SELECT strike_price, call_put, open_interest, delta_oi, avg_cost, contract_month
        FROM options_strike_avg_cost
        WHERE trade_date = %s AND open_interest > 500
        ORDER BY open_interest DESC
        """,
        (trade_date,),
    )

    # 2. 台指期收盤價（近月合約）
    fut = query(
        """
        SELECT close_price FROM tx_futures_daily
        WHERE trade_date = %s AND session = '一般'
          AND LENGTH(contract_month) = 6
        ORDER BY contract_month LIMIT 1
        """,
        (trade_date,),
    )
    underlying = float(fut[0]["close_price"]) if fut and fut[0].get("close_price") else None

    # 3. 法人選擇權買賣 OI（外資 + 自營商）
    inst = query(
        """
        SELECT institution_type,
               call_buy_oi, call_sell_oi, call_net_oi,
               put_buy_oi, put_sell_oi, put_net_oi
        FROM institutional_options
        WHERE trade_date = %s
        ORDER BY institution_type
        """,
        (trade_date,),
    )

    # 法人前日資料（計算變化量）
    inst_prev = []
    if prev_date:
        inst_prev = query(
            """
            SELECT institution_type,
                   call_buy_oi, call_sell_oi, call_net_oi,
                   put_buy_oi, put_sell_oi, put_net_oi
            FROM institutional_options
            WHERE trade_date = %s
            ORDER BY institution_type
            """,
            (prev_date,),
        )

    # 4. PCR（當日）
    pcr = query(
        "SELECT pc_oi_ratio, pc_vol_ratio FROM put_call_ratio WHERE trade_date = %s",
        (trade_date,),
    )

    # 5. Max Pain（當日）
    mp = query(
        "SELECT max_pain_strike, underlying_price, delta_pts FROM market_max_pain WHERE trade_date = %s",
        (trade_date,),
    )

    return {
        "trade_date": str(trade_date),
        "prev_date": str(prev_date) if prev_date else None,
        "underlying": underlying,
        "strikes": strikes,
        "institutional": inst,
        "institutional_prev": inst_prev,
        "pcr": pcr[0] if pcr else None,
        "max_pain": mp[0] if mp else None,
    }


@router.get("/oi-structure")
def get_oi_structure(
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    limit: int = Query(default=60, le=500),
):
    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(days=90)
    return query(
        """
        SELECT * FROM market_oi_structure
        WHERE trade_date BETWEEN %s AND %s
        ORDER BY trade_date DESC
        LIMIT %s
        """,
        (start, end, limit),
    )
