"""
選擇權相關端點：行情、PCR、履約價平均成本
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query

from .db import query

router = APIRouter(tags=["options"])


@router.get("/options")
def get_options(
    trade_date: Optional[date] = Query(default=None),
    call_put: Optional[str] = Query(default=None, pattern="^[CP]$"),
    limit: int = Query(default=200, le=1000),
):
    if trade_date is None:
        trade_date = date.today() - timedelta(days=1)
    params: list = [trade_date]
    cp_filter = ""
    if call_put:
        cp_filter = " AND call_put = %s"
        params.append(call_put)
    params.append(limit)
    return query(
        f"""
        SELECT * FROM txo_options_daily
        WHERE trade_date = %s{cp_filter}
        ORDER BY strike_price, call_put
        LIMIT %s
        """,
        params,
    )


@router.get("/pcr")
def get_pcr(
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
        SELECT * FROM put_call_ratio
        WHERE trade_date BETWEEN %s AND %s
        ORDER BY trade_date DESC
        LIMIT %s
        """,
        (start, end, limit),
    )


@router.get("/options/strike-cost")
def get_strike_cost(
    trade_date: Optional[date] = Query(default=None),
    contract_month: Optional[str] = Query(default=None),
    call_put: Optional[str] = Query(default=None, pattern="^[CP]$"),
):
    if trade_date is None:
        trade_date = date.today() - timedelta(days=1)
    params: list = [trade_date]
    filters = ""
    if contract_month:
        filters += " AND contract_month = %s"
        params.append(contract_month)
    if call_put:
        filters += " AND call_put = %s"
        params.append(call_put)
    return query(
        f"""
        SELECT * FROM options_strike_avg_cost
        WHERE trade_date = %s{filters}
        ORDER BY contract_month, call_put, strike_price
        """,
        params,
    )
