"""
市場衍生指標端點：direction / itm-otm / max-pain / oi-structure
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
