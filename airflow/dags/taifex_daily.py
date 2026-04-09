"""
TAIFEX 每日爬蟲 DAG
- 每日 17:00 (Asia/Taipei) 執行，週一至週五
- 所有 fetch tasks 並行執行，derived_metrics → validate 最後執行
- 成功/失敗都寄 email 到 somehandisfrank@gmail.com
"""

from __future__ import annotations

import sys
import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator

from dag_shared import (
    get_trade_date,
    on_failure_callback, dag_success_callback, dag_failure_callback,
    run_futures, run_options, run_pcr,
    run_institutional, run_large_trader,
    run_derived, run_validator,
)

sys.path.insert(0, "/opt/crawler")

log = logging.getLogger(__name__)


def check_trading_day(**context) -> bool:
    """
    ShortCircuitOperator 用：確認當日是否為交易日。
    回傳 False 時 Airflow 自動跳過所有下游 task（Skipped 狀態）。
    """
    from agents.market_calendar import is_trading_day
    trade_date = get_trade_date(**context)
    result = is_trading_day(trade_date)
    if not result:
        log.info("非交易日 %s，跳過所有爬蟲任務", trade_date)
    return result


# ── DAG 定義 ─────────────────────────────────────────────────────────────────

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "on_failure_callback": on_failure_callback,
    "email_on_failure": False,
    "email_on_retry": False,
}

with DAG(
    dag_id="taifex_daily",
    description="TAIFEX 台指每日資料爬蟲",
    default_args=default_args,
    schedule="0 17 * * 1-5",         # 每週一至五 17:00 (Asia/Taipei)
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["taifex", "financial"],
    on_success_callback=dag_success_callback,
    on_failure_callback=dag_failure_callback,
) as dag:

    t_check = ShortCircuitOperator(
        task_id="check_trading_day",
        python_callable=check_trading_day,
        ignore_downstream_trigger_rules=True,
    )

    t_futures     = PythonOperator(task_id="fetch_futures",      python_callable=run_futures)
    t_options     = PythonOperator(task_id="fetch_options",      python_callable=run_options)
    t_pcr         = PythonOperator(task_id="fetch_pcr",          python_callable=run_pcr)
    t_institutional = PythonOperator(task_id="fetch_institutional", python_callable=run_institutional)
    t_large_trader  = PythonOperator(task_id="fetch_large_trader",  python_callable=run_large_trader)
    t_derived     = PythonOperator(task_id="derived_metrics",    python_callable=run_derived)
    t_validate    = PythonOperator(task_id="validate_data",      python_callable=run_validator)

    fetchers = [t_futures, t_options, t_pcr, t_institutional, t_large_trader]
    t_check >> fetchers >> t_derived >> t_validate
