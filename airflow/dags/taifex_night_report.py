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

    ★ TAIFEX 週五/週末特殊屬性：
      TAIFEX 週五下午開始的盤後（~15:00 Fri → ~05:00 Mon）屬於「跨週末長盤」，
      官方最終結算數據在 futDataDown 中標記為下週一的日期（而非週五）。
      週五 17:00 的 taifex_daily 爬蟲只抓到盤中快照（標記在週五日期），
      必須在週六早上 07:30 追補下週一的日期，才能取得正確終盤收盤價。

    一般情況（Tue-Fri）：用 OpenAPI run_latest() + options(yesterday)
    週六（Sat）：額外補爬 date.today()+2（下週一）的期貨 + 選擇權終盤，同時刪除週五的錯誤快照
    """
    from agents import taifex_futures, taifex_options

    today = date.today()
    yesterday = today - timedelta(days=1)

    log.info("用 OpenAPI 補爬最新期貨終盤資料（預期 trade_date=%s）", yesterday)
    taifex_futures.run_latest()
    log.info("補爬選擇權資料 trade_date=%s", yesterday)
    taifex_options.run(yesterday)

    # 週六特殊：週五的盤後結算數據在 TAIFEX 標記為下週一
    if today.weekday() == 5:  # Saturday
        next_monday = today + timedelta(days=2)
        log.info("[週六特殊] 補爬 %s（週五盤後終盤，TAIFEX 標記為下週一）", next_monday)
        taifex_futures.run(next_monday)
        taifex_options.run(next_monday)
        # 刪除週五的盤中快照（錯誤數據），保留下週一的正確終盤
        from agents.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM tx_futures_daily WHERE trade_date = %s AND session = '盤後'",
                    (yesterday,)
                )
                deleted = cur.rowcount
                cur.execute(
                    "DELETE FROM txo_options_daily WHERE trade_date = %s AND session = '盤後'",
                    (yesterday,)
                )
                deleted += cur.rowcount
                conn.commit()
            log.info("[週六特殊] 刪除週五(%s)盤後快照 %d 筆，保留週一(%s)終盤數據",
                     yesterday, deleted, next_monday)
        except Exception as e:
            log.error("[週六特殊] 刪除週五快照失敗: %s", e)
            conn.rollback()
        finally:
            conn.close()


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

    sent = run(trade_date=trade_date, recipients=recipients)
    # 只有報告真的寄出才通知；skipped (None/False) 不觸發
    if sent:
        from airflow.utils.email import send_email
        actual_td = trade_date or "latest"
        send_email(
            to=NOTIFY_EMAIL,
            subject=f"[✅ 夜盤報告已寄出] taifex_night_report — {actual_td}",
            html_content=f"<p>夜盤觀察報告（<b>{actual_td}</b>）已成功生成並寄送。</p>",
        )


def dag_night_success_callback(context):
    pass  # 通知改由 run_night_report 在實際寄出後觸發，避免 skipped 時誤報


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
