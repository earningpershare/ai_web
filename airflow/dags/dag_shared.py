"""
DAG 共用工具 — 供 taifex_daily 與 taifex_backfill 共用

此檔案不定義任何 DAG，避免 Airflow import 時重複註冊 DAG ID。
"""

from __future__ import annotations

import sys
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from airflow.utils.email import send_email

sys.path.insert(0, "/opt/crawler")

_TAIPEI = ZoneInfo("Asia/Taipei")
NOTIFY_EMAIL = "somehandisfrank@gmail.com"

log = logging.getLogger(__name__)


# ── 日期解析 ──────────────────────────────────────────────────────────────────

def get_trade_date(**context) -> date:
    """
    回傳正確的交易日期（台北時間）。優先序：
    1. params["trade_date"]（手動指定，供 backfill 使用）
    2. 排程執行 → data_interval_end（= 當天 17:00 台北時間）
    3. 手動 trigger 且無 params → logical_date
    4. fallback → 現在時間
    """
    params = context.get("params") or {}
    td_str = (params.get("trade_date") or "").strip()
    if td_str:
        return date.fromisoformat(td_str)

    dag_run = context.get("dag_run")
    if dag_run is not None and getattr(dag_run, "external_trigger", False):
        return context["logical_date"].astimezone(_TAIPEI).date()

    end = context.get("data_interval_end")
    if end is not None:
        return end.astimezone(_TAIPEI).date()

    return datetime.now(_TAIPEI).date()


# ── Email callbacks ──────────────────────────────────────────────────────────

def on_failure_callback(context):
    dag_id = context["dag"].dag_id
    trade_date = get_trade_date(**context)
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
    dag_id = context["dag"].dag_id
    trade_date = get_trade_date(**context)
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
    dag_id = context["dag"].dag_id
    trade_date = get_trade_date(**context)
    send_email(
        to=NOTIFY_EMAIL,
        subject=f"[❌ DAG 失敗] {dag_id} — {trade_date}",
        html_content=f"""
        <h3>❌ DAG 執行失敗</h3>
        <p>日期 <b>{trade_date}</b> 爬蟲 DAG 發生錯誤，請檢查 Airflow log。</p>
        <p>執行時間：{context['ts']}</p>
        """,
    )


# ── Task 函式（供 taifex_daily 與 taifex_backfill 共用）───────────────────────

def run_futures(**context):
    from agents import taifex_futures
    taifex_futures.run(get_trade_date(**context))


def run_options(**context):
    from agents import taifex_options
    taifex_options.run(get_trade_date(**context))


def run_pcr(**context):
    from agents import taifex_pcr
    taifex_pcr.run(get_trade_date(**context))


def run_institutional(**context):
    from agents import taifex_institutional
    taifex_institutional.run(get_trade_date(**context))


def run_large_trader(**context):
    from agents import taifex_large_trader
    taifex_large_trader.run(get_trade_date(**context))


def run_derived(**context):
    from agents import derived_metrics
    derived_metrics.run(get_trade_date(**context))


def run_validator(**context):
    from agents import data_validator
    data_validator.run(get_trade_date(**context))
