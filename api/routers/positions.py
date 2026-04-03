"""
部位端點：散戶期貨/選擇權、大額交易人
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query

from .db import query

router = APIRouter(tags=["positions"])


@router.get("/retail/futures")
def get_retail_futures(
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
        SELECT * FROM retail_futures
        WHERE trade_date BETWEEN %s AND %s
        ORDER BY trade_date DESC, contract_code
        LIMIT %s
        """,
        (start, end, limit),
    )


@router.get("/retail/options")
def get_retail_options(
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
        SELECT * FROM retail_options
        WHERE trade_date BETWEEN %s AND %s
        ORDER BY trade_date DESC
        LIMIT %s
        """,
        (start, end, limit),
    )


@router.get("/large-traders")
def get_large_traders(
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    contract: Optional[str] = Query(default=None),
    limit: int = Query(default=60, le=500),
):
    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(days=90)
    contract_filter = " AND contract_code = %s" if contract else ""
    params: list = [start, end]
    if contract:
        params.append(contract)
    params.append(limit)
    return query(
        f"""
        SELECT * FROM large_trader_positions
        WHERE trade_date BETWEEN %s AND %s{contract_filter}
        ORDER BY trade_date DESC, trader_type
        LIMIT %s
        """,
        params,
    )
