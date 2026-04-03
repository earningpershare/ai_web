"""
每日市場數據觀察報告生成器
- 從 API 抓取當日完整數據
- 透過 Gemini（含 Google Search 新聞抓取）生成客觀報告
- 以 HTML email 寄送給訂閱者

注意：prompt 明確限制 Gemini 不得給予投資建議
"""

import logging
import os
import smtplib
import textwrap
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

logger = logging.getLogger(__name__)

API_URL = os.getenv("API_URL", "http://api:8000")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SMTP_HOST = os.getenv("AIRFLOW__SMTP__SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("AIRFLOW__SMTP__SMTP_PORT", "587"))
SMTP_USER = os.getenv("AIRFLOW__SMTP__SMTP_USER", "")
SMTP_PASS = os.getenv("AIRFLOW__SMTP__SMTP_PASSWORD", "")


# ── 資料抓取 ─────────────────────────────────────────────────────────────────

def _get(endpoint: str, params: dict = None) -> list:
    try:
        r = requests.get(f"{API_URL}{endpoint}", params=params, timeout=15)
        r.raise_for_status()
        return r.json() or []
    except Exception as e:
        logger.warning("fetch %s 失敗: %s", endpoint, e)
        return []


def fetch_market_data(trade_date: date) -> dict:
    ds = str(trade_date)
    prev = str(trade_date - timedelta(days=3))   # 抓近 3 天避免週末空值

    futures = _get("/futures", {"contract": "TX", "start": ds, "end": ds, "limit": 20})
    options = _get("/options", {"start": ds, "end": ds, "limit": 5})
    pcr     = _get("/pcr",     {"start": ds, "end": ds})
    inst_f  = _get("/institutional/futures",  {"start": ds, "end": ds})
    inst_o  = _get("/institutional/options",  {"start": ds, "end": ds})
    retail_f = _get("/retail/futures",  {"start": ds, "end": ds})
    retail_o = _get("/retail/options",  {"start": ds, "end": ds})
    max_pain = _get("/market/max-pain",  {"start": ds, "end": ds, "limit": 1})
    direction = _get("/market/direction", {"start": prev, "end": ds, "limit": 10})
    itm_otm   = _get("/market/itm-otm",  {"start": ds, "end": ds})
    oi_struct  = _get("/market/oi-structure", {"start": ds, "end": ds})
    strike_cost = _get("/options/strike-cost", {"trade_date": ds, "limit": 200})

    # 近月 TX 收盤價
    tx_close = None
    for row in futures:
        if str(row.get("contract_month", ""))[:4] == str(trade_date)[:4]:
            if row.get("session") == "一般":
                tx_close = row.get("close_price")
                break

    # OI 最高 Top 5 履約價
    oi_top5 = []
    if strike_cost:
        weighted = {}
        for row in strike_cost:
            sp = row.get("strike_price")
            oi = float(row.get("open_interest") or 0)
            cost = float(row.get("avg_cost") or 0)
            if sp:
                if sp not in weighted:
                    weighted[sp] = {"oi": 0, "fund": 0}
                weighted[sp]["oi"] += oi
                weighted[sp]["fund"] += cost * oi
        oi_top5 = sorted(weighted.items(), key=lambda x: x[1]["oi"], reverse=True)[:5]

    return {
        "trade_date": ds,
        "tx_close": tx_close,
        "pcr": pcr[0] if pcr else {},
        "inst_futures": inst_f,
        "inst_options": inst_o,
        "retail_futures": retail_f[0] if retail_f else {},
        "retail_options": retail_o[0] if retail_o else {},
        "max_pain": max_pain[0] if max_pain else {},
        "direction": direction,
        "itm_otm": itm_otm[0] if itm_otm else {},
        "oi_struct": oi_struct[0] if oi_struct else {},
        "oi_top5": oi_top5,
    }


# ── Prompt 建構 ───────────────────────────────────────────────────────────────

def build_prompt(data: dict) -> str:
    d = data
    ds = d["trade_date"]

    # 整理外資數據
    ext_fut = next((r for r in d["inst_futures"] if r.get("institution_type") == "外資及陸資"), {})
    ext_opt = next((r for r in d["inst_options"] if r.get("institution_type") == "外資及陸資"), {})
    dlr_opt = next((r for r in d["inst_options"] if r.get("institution_type") == "自營商"), {})

    ret_f = d["retail_futures"]
    ret_o = d["retail_options"]
    mp    = d["max_pain"]
    itm   = d["itm_otm"]
    ois   = d["oi_struct"]

    # 外資 delta
    ext_dir = next((r for r in d["direction"] if r.get("group_type") == "外資及陸資"), {})

    top5_str = "\n".join(
        f"  - 履約價 {sp:,}：OI 合計 {v['oi']:,.0f} 口，均成本×OI 加權量 {v['fund']/1000:.0f}"
        for sp, v in d["oi_top5"]
    ) if d["oi_top5"] else "  （無資料）"

    prompt = textwrap.dedent(f"""
    你是台灣期貨市場數據分析報告系統，負責每日產生客觀的市場數據觀察報告。

    ╔══════════════════════════════════════════════════════════╗
    ║  重要限制（違反將導致報告無效，請嚴格遵守）                  ║
    ╠══════════════════════════════════════════════════════════╣
    ║  ✗ 禁止給予投資建議、買賣建議或交易方向指引               ║
    ║  ✗ 禁止使用「看多」「看空」「建議買進」「建議賣出」          ║
    ║    「應該持有」「值得買」等具有建議性質的詞彙               ║
    ║  ✗ 禁止直接預測指數漲跌（「指數將會上漲/下跌」）            ║
    ║  ✗ 禁止使用「支撐」「壓力」「強烈看好」等投顧常用術語        ║
    ║                                                          ║
    ║  ✓ 可客觀描述數據分布與統計差異                           ║
    ║  ✓ 可指出「哪個價位有大量 OI 集中」（不說支撐/壓力）        ║
    ║  ✓ 可說明各群體持倉口數的統計現況                         ║
    ║  ✓ 可使用條件式歷史統計：「歷史資料顯示，當X情況出現時，   ║
    ║    市場曾出現Y走勢，但不代表未來必然如此」                  ║
    ║  ✓ 可結合新聞描述市場背景事件（純事件描述，不加評價方向）    ║
    ║  ✓ 可說明「若發生X事件，可觀察Y指標的變化」                ║
    ╚══════════════════════════════════════════════════════════╝

    【報告格式要求】請依以下結構產生繁體中文 HTML 報告（email 格式）：
    1. 標題與日期
    2. 今日數據摘要（用表格呈現關鍵數字）
    3. OI 集中價位觀察（描述哪些履約價有顯著未平倉量，不加方向判斷）
    4. 各群體持倉統計（客觀描述法人/散戶的數字差異）
    5. 值得持續觀察的指標（列舉值得注意的數據變化，不給方向建議）
    6. 條件式歷史統計觀察（用「若...，歷史上曾出現...，但不代表必然如此」句式）
    7. 今日市場新聞背景（請使用 Google Search 搜尋「台灣期貨 台股 {ds}」相關新聞，
       客觀摘要今日重要市場事件，只描述發生了什麼，不加投資建議）
    8. 免責聲明（必須包含）

    【今日市場數據 — {ds}】

    ▎期貨
    - TX 近月收盤價：{d['tx_close'] or '（無資料）'}
    - 外資期貨淨口數：{ext_fut.get('net_oi', '—')}（正=多方）
    - 自營商期貨淨口數：{next((r.get('net_oi') for r in d['inst_futures'] if r.get('institution_type') == '自營商'), '—')}
    - 散戶期貨淨口數：{ret_f.get('net_oi', '—')}
    - 外資期貨合計 delta（折算小台）：{ext_dir.get('futures_delta_mtx', '—')}
    - 外資選擇權 delta（折算小台）：{ext_dir.get('options_delta_mtx', '—')}
    - 外資合計 delta（折算小台）：{ext_dir.get('total_delta_mtx', '—')}

    ▎選擇權
    - PCR（Put/Call 比）：{d['pcr'].get('put_call_ratio', '—')}
    - Max Pain：{mp.get('max_pain_strike', '—')} 點（vs 現價差值：{mp.get('delta_pts', '—')} pts）
    - 外資 BC/BP/SC/SP（口）：BC={ext_opt.get('call_buy_oi','—')} / BP={ext_opt.get('put_buy_oi','—')} / SC={ext_opt.get('call_sell_oi','—')} / SP={ext_opt.get('put_sell_oi','—')}
    - 散戶 BC/BP/SC/SP（口）：BC={ret_o.get('call_buy_oi','—')} / BP={ret_o.get('put_buy_oi','—')} / SC={ret_o.get('call_sell_oi','—')} / SP={ret_o.get('put_sell_oi','—')}
    - 自營商 BC/BP/SC/SP（口）：BC={dlr_opt.get('call_buy_oi','—')} / BP={dlr_opt.get('put_buy_oi','—')} / SC={dlr_opt.get('call_sell_oi','—')} / SP={dlr_opt.get('put_sell_oi','—')}
    - Call ITM/ATM/OTM OI：{itm.get('call_itm_oi','—')} / {itm.get('call_atm_oi','—')} / {itm.get('call_otm_oi','—')}
    - Put ITM/ATM/OTM OI：{itm.get('put_itm_oi','—')} / {itm.get('put_atm_oi','—')} / {itm.get('put_otm_oi','—')}
    - 週選 OI 比重：{float(ois.get('weekly_oi_ratio', 0) or 0)*100:.1f}%
    - 週選主力到期：{ois.get('weekly_dominant_exp', '—')}

    ▎OI 最集中履約價 Top 5（Call+Put 合計）
    {top5_str}

    【免責聲明文字（必須在報告末尾完整呈現）】
    「本報告所有內容均源自台灣期貨交易所（TAIFEX）公開資訊及公開新聞媒體，
    由 AI 系統自動整理生成，僅供資料呈現與學術研究用途，
    不構成任何投資建議、期貨交易建議或買賣推薦。
    本報告不具期貨信託事業、期貨顧問事業或任何金融從業資格。
    期貨交易涉及高度風險，可能損失全部本金。
    任何投資決策請自行評估風險，並諮詢合格之期貨顧問。
    過去的數據走勢不代表未來的交易結果。」

    請開始產生報告：
    """).strip()

    return prompt


# ── Gemini 呼叫 ───────────────────────────────────────────────────────────────

def call_gemini(prompt: str) -> str:
    """
    呼叫 Gemini API 產生報告（使用新版 google-genai SDK）。
    啟用 Google Search grounding 讓 Gemini 可搜尋當日新聞。
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY 未設定")

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=4096,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
        return response.text

    except Exception as e:
        logger.error("Gemini 呼叫失敗: %s", e)
        raise


# ── Email 寄送 ────────────────────────────────────────────────────────────────

def _wrap_email_html(content: str, trade_date: str) -> str:
    """將 Gemini 回傳的 HTML 包入完整 email 模板"""
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
  h1 {{ color: #1a237e; border-bottom: 2px solid #1a237e; padding-bottom: 8px; }}
  h2 {{ color: #283593; margin-top: 24px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  th {{ background: #283593; color: white; padding: 6px 12px; text-align: left; }}
  td {{ border: 1px solid #ddd; padding: 6px 12px; }}
  tr:nth-child(even) {{ background: #f5f5f5; }}
  .disclaimer {{ background: #fff3e0; border-left: 4px solid #ff6f00; padding: 12px 16px; margin-top: 24px; font-size: 12px; color: #555; }}
  .footer {{ font-size: 11px; color: #999; margin-top: 24px; border-top: 1px solid #eee; padding-top: 12px; }}
</style>
</head>
<body>
{content}
<div class="footer">
  本郵件由台指金融資料庫自動系統寄送 &nbsp;|&nbsp; 資料日期：{trade_date}<br>
  如需取消訂閱，請回覆此郵件並說明。
</div>
</body>
</html>"""


def send_report_email(report_html: str, trade_date: str, recipients: list[str]):
    """透過 Gmail SMTP 寄送報告"""
    if not recipients:
        logger.warning("無收件人，跳過寄送")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"【TAIFEX 市場數據觀察】{trade_date}"
    msg["From"] = SMTP_USER
    msg["To"] = ", ".join(recipients)

    full_html = _wrap_email_html(report_html, trade_date)
    msg.attach(MIMEText(full_html, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, recipients, msg.as_string())

    logger.info("報告已寄送至 %s", recipients)


# ── 主流程 ────────────────────────────────────────────────────────────────────

def run(trade_date: date, recipients: list[str] = None):
    """
    生成並寄送當日市場數據觀察報告。

    Args:
        trade_date: 交易日期
        recipients: 收件人 email 清單；若未指定則讀取環境變數 REPORT_RECIPIENTS
    """
    if recipients is None:
        env_list = os.getenv("REPORT_RECIPIENTS", "")
        recipients = [e.strip() for e in env_list.split(",") if e.strip()]

    if not recipients:
        logger.warning("未設定 REPORT_RECIPIENTS，跳過寄送")
        return

    logger.info("開始生成 %s 報告，收件人：%s", trade_date, recipients)

    data = fetch_market_data(trade_date)
    prompt = build_prompt(data)
    report_html = call_gemini(prompt)
    send_report_email(report_html, str(trade_date), recipients)

    logger.info("報告生成並寄送完成")
