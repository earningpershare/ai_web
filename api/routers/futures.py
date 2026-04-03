"""
期貨行情端點
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query

from .db import query

router = APIRouter(prefix="/futures", tags=["futures"])


@router.get("")
def get_futures(
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    contract: Optional[str] = Query(default="TX"),
    limit: int = Query(default=60, le=500),
):
    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(days=90)
    return query(
        """
        SELECT * FROM tx_futures_daily
        WHERE trade_date BETWEEN %s AND %s
          AND contract_code = %s
        ORDER BY trade_date DESC, contract_month
        LIMIT %s
        """,
        (start, end, contract, limit),
    )
