"""
夜盤觀察報告 DAG
- 每日 07:30 Asia/Taipei 執行（週二至週六：涵蓋週一至週五的夜盤收盤後）
- 夜盤收盤：次日 05:00；日盤開盤：08:45；本 DAG 卡在 07:30 正好在兩者之間
- 呼叫 Gemini 生成簡短盤前夜盤報告，SMTP 寄送
- 可手動觸發：Trigger DAG w/ config → {"trade_date": "2026-04-16", "recipients": "a@b.com"}
"""

from __future__ import annotations

import sys
import logging
from datetime import datetime, timedelta, date

from airflow import DAG
from airflow.operators.python import PythonOperator
from dag_shared import on_failure_callback, dag_failure_callback

sys.path.insert(0, "/opt/crawler")

log = logging.getLogger(__name__)

NOTIFY_EMAIL = "somehandisfrank@gmail.com"


def crawl_night_session(**context):
    """
    07:30 執行時補爬夜盤終盤資料。
    taifex_daily 跑在 17:00（夜盤開盤後 2 小時），抓到的是盤中快照。
    這裡改用 TAIFEX OpenAPI run_latest()，回傳最新交易日資料（無日期篩選），
    搭配 taifex_options.run(yesterday) 確保選擇權資料也補齊。
    """
    from agents import taifex_futures, taifex_options
    yesterday = date.today() - timedelta(days=1)
    log.info("用 OpenAPI 補爬最新期貨終盤資料（預期 trade_date=%s）", yesterday)
    taifex_futures.run_latest()
    log.info("補爬選擇權資料 trade_date=%s", yesterday)
    taifex_options.run(yesterday)


def run_night_report(ds: str, params: dict = None, **context):
    """生成並寄送夜盤觀察報告；若無夜盤資料則跳過。"""
    import os
    import requests
    from agents.night_report import run

    td_override = ((params or {}).get("trade_date") or "").strip()
    trade_date = None
    if td_override:
        from datetime import date
        trade_date = date.fromisoformat(td_override)

    recipients_str = (params or {}).get("recipients", "")
    recipients = [e.strip() for e in recipients_str.split(",") if e.strip()] or None

    # 先探查 /market/night-session 是否有資料；若無則 skip
    api_url = os.getenv("API_URL", "http://api:8000")
    try:
        probe_params = {"trade_date": str(trade_date)} if trade_date else {}
        resp = requests.get(f"{api_url}/market/night-session", params=probe_params, timeout=15)
        resp.raise_for_status()
        probe = resp.json()
        if not probe or not probe.get("night_session"):
            log.info("無夜盤資料（trade_date=%s），跳過報告", trade_date or "latest")
            return
        # 資料新鮮度檢查：超過 2 天的舊資料不寄（避免用舊資料生成幻覺報告）
        from datetime import date as _date
        api_td = _date.fromisoformat(probe["trade_date"])
        days_old = (_date.today() - api_td).days
        if days_old > 2:
            log.warning("夜盤資料過期（%s，%d 天前），跳過報告避免幻覺", api_td, days_old)
            return
    except Exception as e:
        log.warning("探查夜盤資料失敗（%s），仍嘗試執行", e)

    run(trade_date=trade_date, recipients=recipients)


def dag_night_success_callback(context):
    from airflow.utils.email import send_email
    dag_id = context["dag"].dag_id
    trade_date = context["ds"]
    send_email(
        to=NOTIFY_EMAIL,
        subject=f"[✅ 夜盤報告已寄出] {dag_id} — {trade_date}",
        html_content=f"<p>執行日期 <b>{trade_date}</b> 夜盤觀察報告已成功生成並寄送。</p>",
    )


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=3),
    "on_failure_callback": on_failure_callback,
    "email_on_failure": False,
    "email_on_retry": False,
}

with DAG(
    dag_id="taifex_night_report",
    description="夜盤觀察報告（Gemini 生成，日盤開盤前寄送）",
    default_args=default_args,
    schedule="30 7 * * 2-6",         # 週二至週六 07:30 Asia/Taipei（涵蓋週一至週五夜盤）
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["taifex", "report", "night"],
    on_success_callback=dag_night_success_callback,
    on_failure_callback=dag_failure_callback,
    params={
        "trade_date": "",        # 空 = 取最新有夜盤資料的日期
        "recipients": "",        # 空 = 使用環境變數 NIGHT_REPORT_RECIPIENTS
    },
) as dag:

    t_crawl = PythonOperator(
        task_id="crawl_night_session",
        python_callable=crawl_night_session,
    )

    t_night = PythonOperator(
        task_id="generate_and_send_night_report",
        python_callable=run_night_report,
    )

    t_crawl >> t_night
