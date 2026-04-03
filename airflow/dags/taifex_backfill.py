"""
手動回補 DAG — 在 Airflow UI 手動觸發，可指定任意日期
觸發方式：UI → Trigger DAG w/ config → {"trade_date": "2026-03-31"}
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from taifex_daily import (
    run_futures, run_options, run_pcr,
    run_institutional, run_large_trader, run_derived, run_validator,
    on_failure_callback,
    dag_success_callback, dag_failure_callback,
)

sys.path.insert(0, "/opt/crawler")

default_args = {
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": on_failure_callback,
}

with DAG(
    dag_id="taifex_backfill",
    description="TAIFEX 手動回補（指定日期）",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["taifex", "backfill"],
    on_success_callback=dag_success_callback,
    on_failure_callback=dag_failure_callback,
    params={"trade_date": "2026-03-31"},
) as dag:

    t_futures = PythonOperator(
        task_id="fetch_futures",
        python_callable=run_futures,
        **default_args,
    )
    t_options = PythonOperator(
        task_id="fetch_options",
        python_callable=run_options,
        **default_args,
    )
    t_pcr = PythonOperator(
        task_id="fetch_pcr",
        python_callable=run_pcr,
        **default_args,
    )
    t_institutional = PythonOperator(
        task_id="fetch_institutional",
        python_callable=run_institutional,
        **default_args,
    )
    t_large_trader = PythonOperator(
        task_id="fetch_large_trader",
        python_callable=run_large_trader,
        **default_args,
    )
    t_derived = PythonOperator(
        task_id="derived_metrics",
        python_callable=run_derived,
        **default_args,
    )
    t_validate = PythonOperator(
        task_id="validate_data",
        python_callable=run_validator,
        **default_args,
    )

    [t_futures, t_options, t_pcr, t_institutional, t_large_trader] >> t_derived >> t_validate
