"""
付款對帳 DAG — 每小時主動查詢 pending 訂單
確保漏掉的綠界 callback 都能被補處理
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

import httpx

from airflow import DAG
from airflow.operators.python import PythonOperator

log = logging.getLogger(__name__)

API_INTERNAL_URL = os.getenv("API_INTERNAL_URL", "http://api:8000")
RECONCILE_SECRET = os.getenv("RECONCILE_SECRET", "")

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": None,
}


def reconcile(**context):
    """呼叫 /payment/reconcile 端點補處理漏掉的 callback"""
    if not RECONCILE_SECRET:
        log.warning("RECONCILE_SECRET not set, skipping reconcile")
        return

    try:
        with httpx.Client(timeout=30) as client:
            r = client.post(
                f"{API_INTERNAL_URL}/payment/reconcile",
                headers={"X-Reconcile-Secret": RECONCILE_SECRET},
            )
        if r.status_code == 200:
            data = r.json()
            log.info("Reconcile result: %s", data)
            if data.get("recovered", 0) > 0:
                log.warning("RECOVERED %d missed payments: %s",
                            data["recovered"], data.get("recovered_orders"))
        else:
            log.error("Reconcile HTTP %s: %s", r.status_code, r.text[:300])
    except Exception as e:
        log.error("Reconcile request failed: %s", e)
        raise


with DAG(
    dag_id="payment_reconcile",
    description="每小時對帳 pending 訂單（補漏綠界 callback）",
    schedule_interval="*/30 * * * *",   # 每 30 分鐘
    start_date=datetime(2026, 4, 9),
    catchup=False,
    default_args=default_args,
    tags=["payment"],
) as dag:

    PythonOperator(
        task_id="reconcile_pending_orders",
        python_callable=reconcile,
    )
