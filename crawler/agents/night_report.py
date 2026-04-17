"""
夜盤狀況報告生成器 — 每日日盤開盤前寄送
- 抓 /market/night-session 的夜盤收盤、缺口、成交量
- 透過 Gemini 生成簡短盤前摘要（含國際盤重點 + 夜盤解讀）
- SMTP 寄送（參考 report_generator 的 SMTP 設定）
"""

import logging
import os
import smtplib
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from agents.report_generator import call_gemini, _markdown_to_html  # 重用既有的 Gemini 呼叫 + markdown 轉換

logger = logging.getLogger(__name__)

API_URL = os.getenv("API_URL", "http://api:8000")
SMTP_HOST = os.getenv("AIRFLOW__SMTP__SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("AIRFLOW__SMTP__SMTP_PORT", "587"))
SMTP_USER = os.getenv("AIRFLOW__SMTP__SMTP_USER", "")
SMTP_PASS = os.getenv("AIRFLOW__SMTP__SMTP_PASSWORD", "")


def fetch_night_data(trade_date: date = None) -> dict:
    """抓 /market/night-session；若指定日期則查該日，否則取最新有盤後資料的日期"""
    params = {"trade_date": str(trade_date)} if trade_date else {}
    try:
        r = requests.get(f"{API_URL}/market/night-session", params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error("抓夜盤資料失敗: %s", e)
        return {}


def build_prompt(data: dict) -> str:
    if not data:
        return ""
    td = data.get("trade_date", "—")
    day = data.get("day_session") or {}
    night = data.get("night_session") or {}
    prev = data.get("prev_day_close") or {}
    opt = data.get("options_night_summary") or {}
    gap_dn = data.get("gap_day_to_night")
    gap_dn_pct = data.get("gap_day_to_night_pct")
    gap_pn = data.get("gap_prev_to_night")

    return f"""你是台指期貨分析助理。以下是 {td} 的 TAIFEX 夜盤（session='盤後'）與日盤（session='一般'）近月 TX 收盤資料。
請產出『盤前夜盤觀察報告』，要在日盤開盤（次日 08:45）前寄送給交易人。

**資料**
- 日盤 {day.get('contract_month','—')}：開 {day.get('open','—')}、高 {day.get('high','—')}、低 {day.get('low','—')}、收 {day.get('close','—')}，量 {day.get('volume','—')}
- 夜盤 {night.get('contract_month','—')}：開 {night.get('open','—')}、高 {night.get('high','—')}、低 {night.get('low','—')}、收 {night.get('close','—')}，量 {night.get('volume','—')}
- 日盤→夜盤缺口：{gap_dn} 點（{gap_dn_pct:.2f}% ）
- 前一交易日 {prev.get('trade_date','—')} 日盤收：{prev.get('close','—')}（用來觀察整段時序變化）
- 前日日盤→本夜盤缺口：{gap_pn} 點
- 夜盤選擇權成交量：Call {opt.get('call_volume','—')}、Put {opt.get('put_volume','—')}、總計 {opt.get('total_volume','—')}

**要求**
1. 用繁體中文、**800–1200 字**、HTML 格式（可用 <h3>、<h4>、<p>、<ul>、<li>、<strong>、<table> 基本標籤；不要用 <html><body> 包外層、不要用 markdown 語法、不要有 ```html``` 之類的代碼圍欄）
2. 結構：
   - **<h3>夜盤速覽</h3>**：一段 3–4 句話的重點濃縮（夜盤漲跌、缺口方向、成交量熱度）
   - **<h3>國際盤脈絡</h3>**：用 Google Search 查當天凌晨美股（S&P 500、那斯達克、費城半導體）、原油、黃金、美債殖利率、台積電 ADR 的重點變化；150–250 字
   - **<h3>夜盤解讀</h3>**：夜盤走勢反映什麼 risk sentiment？call vs put 成交量暗示方向？200–300 字
   - **<h3>日盤開盤劇本</h3>**：基於夜盤缺口推演開盤可能場景（往上跳空、往下跳空、平開，以及後續可能壓力/支撐位）；150–250 字，語氣客觀、不做 call 單
3. 結尾加一段極小聲明：「本報告不構成投資建議，期貨交易涉及高度風險。」
4. 使用 Google Search 抓國際市場即時新聞，但只提供與台指相關的重點
"""


def send_night_report(html_body: str, trade_date: str, recipients: list[str]):
    """簡化版 SMTP 寄送（不含訂閱管理）"""
    if not recipients:
        logger.warning("無收件人，跳過寄送")
        return

    full_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: 'Microsoft JhengHei', 'PingFang TC', sans-serif; background:#f7f9fc; margin:0; padding:20px; color:#333 }}
  .wrap {{ max-width:720px; margin:0 auto; background:#fff; border-radius:10px; padding:28px 32px; box-shadow:0 2px 8px rgba(0,0,0,0.06) }}
  h2 {{ color:#1a73e8; border-bottom:2px solid #1a73e8; padding-bottom:8px; margin-top:0 }}
  h3 {{ color:#e07b00; margin-top:22px }}
  h4 {{ color:#555; margin-top:16px }}
  table {{ border-collapse:collapse; margin:12px 0 }}
  th, td {{ border:1px solid #ddd; padding:6px 10px; font-size:14px }}
  th {{ background:#f4f6fa }}
  .foot {{ margin-top:24px; padding-top:14px; border-top:1px solid #eee; font-size:12px; color:#888 }}
</style></head><body>
<div class="wrap">
  <h2>🌙 台指夜盤觀察 — {trade_date}</h2>
  {html_body}
  <div class="foot">
    本郵件由 TaifexAI 自動系統寄送 &nbsp;|&nbsp; 夜盤交易日：{trade_date}<br>
    <span style="color:#bbb">本報告不構成投資建議。期貨交易有高度風險，請自行評估。</span>
  </div>
</div>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🌙【夜盤觀察】{trade_date} 盤前簡報"
    msg["From"] = SMTP_USER
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(full_html, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, recipients, msg.as_string())

    logger.info("夜盤報告已寄送至 %s", recipients)


def run(trade_date: date = None, recipients: list[str] = None):
    """
    生成並寄送夜盤觀察報告。
    Args:
        trade_date: 若未指定則 API 會取最新有 '盤後' 資料的日期
        recipients: 若未指定則用環境變數 NIGHT_REPORT_RECIPIENTS（fallback: somehandisfrank@gmail.com）
    """
    if recipients is None:
        env = os.getenv("NIGHT_REPORT_RECIPIENTS", "somehandisfrank@gmail.com")
        recipients = [e.strip() for e in env.split(",") if e.strip()]

    if not recipients:
        logger.warning("無收件人，跳過夜盤報告")
        return

    data = fetch_night_data(trade_date)
    if not data or not data.get("night_session"):
        logger.warning("夜盤資料缺失（trade_date=%s），跳過生成", trade_date)
        return

    actual_td = data.get("trade_date", str(trade_date) if trade_date else "")
    logger.info("生成夜盤報告 trade_date=%s，收件人：%s", actual_td, recipients)

    prompt = build_prompt(data)
    if not prompt:
        return

    raw = call_gemini(prompt)
    # Gemini 可能回 markdown or HTML，做寬鬆轉換：若看起來像 markdown 則轉
    if "<h3>" in raw or "<p>" in raw:
        body_html = raw
    else:
        body_html = _markdown_to_html(raw)

    send_night_report(body_html, actual_td, recipients)
    logger.info("夜盤報告流程完成")
