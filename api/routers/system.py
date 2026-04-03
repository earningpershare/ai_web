"""
系統端點：健康檢查、爬蟲日誌
"""

from typing import Optional

from fastapi import APIRouter, Query

from .db import query

router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/crawler-log")
def get_crawler_log(
    limit: int = Query(default=50, le=200),
    status: Optional[str] = Query(default=None),
):
    status_filter = " WHERE status = %s" if status else ""
    params: list = [status] if status else []
    params.append(limit)
    return query(
        f"SELECT * FROM crawler_log{status_filter} ORDER BY executed_at DESC LIMIT %s",
        params,
    )
