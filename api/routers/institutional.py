"""
三大法人端點：期貨部位、選擇權部位
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query

from .db import query

router = APIRouter(prefix="/institutional", tags=["institutional"])


@router.get("/futures")
def get_institutional_futures(
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
        SELECT * FROM institutional_futures
        WHERE trade_date BETWEEN %s AND %s{contract_filter}
        ORDER BY trade_date DESC, institution_type
        LIMIT %s
        """,
        params,
    )


@router.get("/options")
def get_institutional_options(
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
        SELECT * FROM institutional_options
        WHERE trade_date BETWEEN %s AND %s
        ORDER BY trade_date DESC, institution_type
        LIMIT %s
        """,
        (start, end, limit),
    )
