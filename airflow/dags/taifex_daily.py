"""
TAIFEX 每日爬蟲 DAG
- 每日 17:00 (Asia/Taipei) 執行，週一至週五
- 所有 fetch tasks 並行執行，validate 最後執行
- 成功/失敗都寄 email 到 somehandisfrank@gmail.com
"""

from __future__ import annotations

import sys
import logging
from datetime import date, datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from airflow.utils.email import send_email

# 讓 DAG 能 import crawler agents
sys.path.insert(0, "/opt/crawler")

NOTIFY_EMAIL = "somehandisfrank@gmail.com"
log = logging.getLogger(__name__)


# ── Email callbacks ──────────────────────────────────────────────────────────

def on_failure_callback(context):
    """Task 級別：只在單一 task 失敗時通知"""
    dag_id = context["dag"].dag_id
    trade_date = context["ds"]
    task_id = context["task_instance"].task_id
    exception = context.get("exception", "未知錯誤")
    send_email(
        to=NOTIFY_EMAIL,
        subject=f"[❌ 失敗] {dag_id} / {task_id} — {trade_date}",
        html_content=f"""
        <h3>❌ 任務執行失敗</h3>
        <table border="1" cellpadding="6">
          <tr><td><b>DAG</b></td><td>{dag_id}</td></tr>
          <tr><td><b>Task</b></td><td>{task_id}</td></tr>
          <tr><td><b>交易日期</b></td><td>{trade_date}</td></tr>
          <tr><td><b>執行時間</b></td><td>{context['ts']}</td></tr>
          <tr><td><b>錯誤訊息</b></td><td><pre>{exception}</pre></td></tr>
        </table>
        <p>請至 Airflow UI 查看完整 log。</p>
        """,
    )


def dag_success_callback(context):
    """整個 DAG 完成後的通知"""
    dag_id = context["dag"].dag_id
    trade_date = context["ds"]
    send_email(
        to=NOTIFY_EMAIL,
        subject=f"[✅ 全部完成] {dag_id} — {trade_date}",
        html_content=f"""
        <h3>✅ 所有爬蟲任務完成</h3>
        <p>日期 <b>{trade_date}</b> 所有資料已成功寫入資料庫。</p>
        <p>執行時間：{context['ts']}</p>
        """,
    )


def dag_failure_callback(context):
    """整個 DAG 失敗時的通知"""
    dag_id = context["dag"].dag_id
    trade_date = context["ds"]
    send_email(
        to=NOTIFY_EMAIL,
        subject=f"[❌ DAG 失敗] {dag_id} — {trade_date}",
        html_content=f"""
        <h3>❌ DAG 執行失敗</h3>
        <p>日期 <b>{trade_date}</b> 爬蟲 DAG 發生錯誤，請檢查 Airflow log。</p>
        <p>執行時間：{context['ts']}</p>
        """,
    )


# ── Task functions ───────────────────────────────────────────────────────────

def _get_trade_date(ds: str) -> date:
    """Airflow ds 是排程日，期交所資料是當天，直接使用。"""
    return datetime.strptime(ds, "%Y-%m-%d").date()


def run_futures(ds: str, **_):
    from agents import taifex_futures
    taifex_futures.run(_get_trade_date(ds))


def run_options(ds: str, **_):
    from agents import taifex_options
    taifex_options.run(_get_trade_date(ds))


def run_pcr(ds: str, **_):
    from agents import taifex_pcr
    taifex_pcr.run(_get_trade_date(ds))


def run_institutional(ds: str, **_):
    from agents import taifex_institutional
    taifex_institutional.run(_get_trade_date(ds))


def run_large_trader(ds: str, **_):
    from agents import taifex_large_trader
    taifex_large_trader.run(_get_trade_date(ds))


def check_trading_day(ds: str, **_) -> bool:
    """
    ShortCircuitOperator 用：確認當日是否為交易日。
    回傳 False 時 Airflow 會自動跳過所有下游 task（Skipped 狀態）。
    """
    from agents.market_calendar import is_trading_day
    trade_date = _get_trade_date(ds)
    result = is_trading_day(trade_date)
    if not result:
        log.info("非交易日 %s，跳過所有爬蟲任務", trade_date)
    return result


def run_derived(ds: str, **_):
    from agents import derived_metrics
    derived_metrics.run(_get_trade_date(ds))


def run_validator(ds: str, **_):
    from agents import data_validator
    data_validator.run(_get_trade_date(ds))


# ── DAG 定義 ─────────────────────────────────────────────────────────────────

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "on_failure_callback": on_failure_callback,
    "email_on_failure": False,   # 由 callback 處理
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
        # 休市時整個 DAG 標記為 Skipped（不觸發 failure callback）
        ignore_downstream_trigger_rules=True,
    )

    t_futures = PythonOperator(
        task_id="fetch_futures",
        python_callable=run_futures,
    )

    t_options = PythonOperator(
        task_id="fetch_options",
        python_callable=run_options,
    )

    t_pcr = PythonOperator(
        task_id="fetch_pcr",
        python_callable=run_pcr,
    )

    t_institutional = PythonOperator(
        task_id="fetch_institutional",
        python_callable=run_institutional,
    )

    t_large_trader = PythonOperator(
        task_id="fetch_large_trader",
        python_callable=run_large_trader,
    )

    t_derived = PythonOperator(
        task_id="derived_metrics",
        python_callable=run_derived,
    )

    t_validate = PythonOperator(
        task_id="validate_data",
        python_callable=run_validator,
    )

    # check_trading_day → 所有 fetch 並行 → derived_metrics → validate
    t_check >> [t_futures, t_options, t_pcr, t_institutional, t_large_trader] >> t_derived >> t_validate
