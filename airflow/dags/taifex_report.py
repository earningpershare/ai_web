"""
每日市場數據觀察報告 DAG
- 在 taifex_daily 完成後約 30 分鐘執行（17:30 Asia/Taipei）
- 呼叫 Gemini 生成報告並寄送 email
- 可手動觸發：Trigger DAG w/ config → {"trade_date": "2026-04-03", "recipients": "a@b.com,c@d.com"}
"""

from __future__ import annotations

import sys
import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from dag_shared import on_failure_callback, dag_failure_callback

sys.path.insert(0, "/opt/crawler")

log = logging.getLogger(__name__)

NOTIFY_EMAIL = "somehandisfrank@gmail.com"


def run_report(ds: str, params: dict = None, **context):
    import os
    import requests
    from agents.report_generator import run
    from dag_shared import get_trade_date

    # 手動指定 trade_date 優先；否則與 taifex_daily 一致使用 data_interval_end
    td_override = ((params or {}).get("trade_date") or "").strip()
    if td_override:
        from datetime import date
        trade_date = date.fromisoformat(td_override)
    else:
        trade_date = get_trade_date(ds=ds, params=params, **context)

    recipients_str = (params or {}).get("recipients", "")
    recipients = [e.strip() for e in recipients_str.split(",") if e.strip()] or None

    # 確認是交易日：查 API 當天是否有期貨資料
    api_url = os.getenv("API_URL", "http://api:8000")
    try:
        resp = requests.get(
            f"{api_url}/futures",
            params={"contract": "TX", "start": str(trade_date), "end": str(trade_date), "limit": 1},
            timeout=15,
        )
        resp.raise_for_status()
        if not resp.json():
            log.info("%s 無期貨資料，視為非交易日，跳過報告生成", trade_date)
            return
    except Exception as e:
        log.warning("無法確認交易日狀態（%s），繼續嘗試生成報告", e)

    run(trade_date, recipients=recipients)


def dag_report_success_callback(context):
    from airflow.utils.email import send_email
    dag_id    = context["dag"].dag_id
    trade_date = context["ds"]
    send_email(
        to=NOTIFY_EMAIL,
        subject=f"[✅ 報告已寄出] {dag_id} — {trade_date}",
        html_content=f"<p>日期 <b>{trade_date}</b> 市場數據觀察報告已成功生成並寄送。</p>",
    )


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": on_failure_callback,
    "email_on_failure": False,
    "email_on_retry": False,
}

with DAG(
    dag_id="taifex_report",
    description="每日市場數據觀察報告（Gemini 生成）",
    default_args=default_args,
    schedule="30 17 * * 1-5",       # 每週一至五 17:30 Asia/Taipei（taifex_daily 之後）
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["taifex", "report"],
    on_success_callback=dag_report_success_callback,
    on_failure_callback=dag_failure_callback,
    params={
        "trade_date": "",        # 空字串 = 使用 ds（排程日）
        "recipients": "",        # 空字串 = 使用環境變數 REPORT_RECIPIENTS
    },
) as dag:

    t_report = PythonOperator(
        task_id="generate_and_send_report",
        python_callable=run_report,
    )
