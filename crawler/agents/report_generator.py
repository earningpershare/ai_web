"""
每日市場籌碼觀察報告生成器
- 從 API 抓取當日完整數據
- 透過 Gemini（含 Google Search 新聞抓取）生成專業報告
- 以 HTML email 寄送給訂閱者
"""

import logging
import os
import smtplib
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
    prev = str(trade_date - timedelta(days=3))

    futures    = _get("/futures",                {"contract": "TX", "start": ds, "end": ds, "limit": 20})
    pcr        = _get("/pcr",                   {"start": ds, "end": ds})
    inst_f     = _get("/institutional/futures", {"start": ds, "end": ds})
    inst_o     = _get("/institutional/options", {"start": ds, "end": ds})
    retail_f   = _get("/retail/futures",        {"start": ds, "end": ds})
    retail_o   = _get("/retail/options",        {"start": ds, "end": ds})
    max_pain   = _get("/market/max-pain",       {"start": ds, "end": ds, "limit": 1})
    direction  = _get("/market/direction",      {"start": prev, "end": ds, "limit": 10})
    itm_otm    = _get("/market/itm-otm",        {"start": ds, "end": ds})
    oi_struct  = _get("/market/oi-structure",   {"start": ds, "end": ds})
    strike_cost = _get("/options/strike-cost",  {"trade_date": ds, "limit": 200})
    dealer_map = _get("/market/dealer-map",     {"trade_date": ds})

    # 近月 TX 收盤價
    tx_close = None
    for row in futures:
        if str(row.get("contract_month", ""))[:4] == str(trade_date)[:4]:
            if row.get("session") == "一般":
                tx_close = row.get("close_price")
                break

    # OI 最高 Top 5 履約價（Call+Put 合計）
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

    # 莊家地圖：分析賣方壓力/支撐帶
    # dealer_map API 回傳 dict（非 list），直接取用
    dm = dealer_map if isinstance(dealer_map, dict) else {}
    dm_strikes = dm.get("strikes", [])

    # 整理賣方壓力帶（Call OTM 大口數）與支撐帶（Put OTM 大口數）
    call_pressure = sorted(
        [s for s in dm_strikes if s.get("call_put") == "Call"],
        key=lambda x: abs(float(x.get("delta_oi") or 0)), reverse=True,
    )[:5]
    put_support = sorted(
        [s for s in dm_strikes if s.get("call_put") == "Put"],
        key=lambda x: abs(float(x.get("delta_oi") or 0)), reverse=True,
    )[:5]

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
        "dealer_map": dm,
        "call_pressure": call_pressure,
        "put_support": put_support,
    }


# ── Prompt 建構 ───────────────────────────────────────────────────────────────

def build_prompt(data: dict) -> str:
    d = data
    ds = d["trade_date"]

    ext_fut = next((r for r in d["inst_futures"] if r.get("institution_type") == "外資及陸資"), {})
    dlr_fut = next((r for r in d["inst_futures"] if r.get("institution_type") == "自營商"), {})
    ext_opt = next((r for r in d["inst_options"] if r.get("institution_type") == "外資及陸資"), {})
    dlr_opt = next((r for r in d["inst_options"] if r.get("institution_type") == "自營商"), {})
    tit_opt = next((r for r in d["inst_options"] if r.get("institution_type") == "投信"), {})

    ret_f = d["retail_futures"]
    ret_o = d["retail_options"]
    mp    = d["max_pain"]
    itm   = d["itm_otm"]
    ois   = d["oi_struct"]
    ext_dir = next((r for r in d["direction"] if r.get("group_type") == "外資及陸資"), {})

    top5_lines = "\n".join(
        f"    {i+1}. 履約價 {int(sp):,} 點 — OI {v['oi']:,.0f} 口"
        for i, (sp, v) in enumerate(d["oi_top5"])
    ) if d["oi_top5"] else "    （無資料）"

    weekly_ratio_pct = float(ois.get("weekly_oi_ratio", 0) or 0) * 100

    # 莊家地圖資料
    cp = d.get("call_pressure", [])
    ps = d.get("put_support", [])
    dm = d.get("dealer_map", {})
    dm_pcr = dm.get("pcr") or {}
    dm_mp = dm.get("max_pain") or {}

    call_pressure_lines = "\n".join(
        f"    Call {int(float(s.get('strike_price',0))):,} — delta_oi {float(s.get('delta_oi',0)):+,.0f} 口, "
        f"avg_cost {float(s.get('avg_cost',0)):,.1f}, 損平 {int(float(s.get('strike_price',0)) + float(s.get('avg_cost',0))):,}"
        for s in cp
    ) if cp else "    （無資料）"

    put_support_lines = "\n".join(
        f"    Put  {int(float(s.get('strike_price',0))):,} — delta_oi {float(s.get('delta_oi',0)):+,.0f} 口, "
        f"avg_cost {float(s.get('avg_cost',0)):,.1f}, 損平 {int(float(s.get('strike_price',0)) - float(s.get('avg_cost',0))):,}"
        for s in ps
    ) if ps else "    （無資料）"

    prompt = f"""你是台指期籌碼分析師。根據以下數據撰寫精煉的市場觀察報告。

⚠️ 合規：禁止操作建議、方向預測、投顧術語。僅陳述數據事實與條件式歷史觀察。
📏 全篇控制在 1500～2000 字，每段直接切入重點，不要鋪陳廢話。
📝 輸出 Markdown 純文字（# ## ### **粗體** 列表），不要 HTML。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 原始數據（{ds}）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TX 收盤: {d['tx_close'] or '—'} | PCR: {d['pcr'].get('put_call_ratio', '—')} | Max Pain: {mp.get('max_pain_strike', '—')}（距現價 {mp.get('delta_pts', '—')} pts）
週選到期: {ois.get('weekly_dominant_exp', '—')} | 週選 OI 占比: {weekly_ratio_pct:.1f}%

期貨淨口數: 外資 {ext_fut.get('net_oi', '—')} / 自營 {dlr_fut.get('net_oi', '—')} / 散戶 {ret_f.get('net_oi', '—')}
外資 delta: 期貨 {ext_dir.get('futures_delta_mtx', '—')} + 選擇權 {ext_dir.get('options_delta_mtx', '—')} = 合計 {ext_dir.get('total_delta_mtx', '—')} 小台

選擇權 OI（BC/SC/BP/SP）:
  外資: {ext_opt.get('call_buy_oi','—')}/{ext_opt.get('call_sell_oi','—')}/{ext_opt.get('put_buy_oi','—')}/{ext_opt.get('put_sell_oi','—')}
  自營: {dlr_opt.get('call_buy_oi','—')}/{dlr_opt.get('call_sell_oi','—')}/{dlr_opt.get('put_buy_oi','—')}/{dlr_opt.get('put_sell_oi','—')}
  散戶: {ret_o.get('call_buy_oi','—')}/{ret_o.get('call_sell_oi','—')}/{ret_o.get('put_buy_oi','—')}/{ret_o.get('put_sell_oi','—')}

ITM/ATM/OTM: Call {itm.get('call_itm_oi','—')}/{itm.get('call_atm_oi','—')}/{itm.get('call_otm_oi','—')} | Put {itm.get('put_itm_oi','—')}/{itm.get('put_atm_oi','—')}/{itm.get('put_otm_oi','—')}

OI Top5: {top5_lines}

【莊家地圖 — 賣方壓力/支撐帶】
概念：OTM 賣方 = 主力（smart money），delta_oi（今日增減）比靜態 OI 更重要。
上方壓力帶（Call 賣方，delta_oi 變動最大）:
{call_pressure_lines}
下方支撐帶（Put 賣方，delta_oi 變動最大）:
{put_support_lines}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 報告章節（四章，每章 300～500 字）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 一、莊家地圖與關鍵價位
分析賣方的壓力帶與支撐帶分布，結合 Max Pain 與 OI Top5，
描述賣方資金集中在哪些區間、今日增減口數揭示的方向意圖、損平價位對現價的關係。
不要重複列出原始數字，而是解讀數字背後的意涵。

## 二、法人籌碼結構
外資期貨 vs 選擇權 delta 是否一致、各法人 BC/SC/BP/SP 的策略傾向、
散戶與法人的方向差異。用 2～3 個最值得注意的觀察點即可，不需逐項羅列。

## 三、今日市場事件
用 Google Search 搜尋「台股 {ds}」「美股 {ds}」，挑最重要的 2～3 則事件，
每則一句話事實 + 一句話「可觀察哪個指標」。不需要寫長段落。

## 四、後續觀察重點（3 點）
結合以上分析，列出 3 個最值得追蹤的指標或價位，每點引用數字並說明原因。

---
最後附上免責聲明（逐字保留）：
「本報告源自 TAIFEX 公開資訊及公開新聞，由 AI 自動生成，僅供資料呈現與研究用途，不構成投資建議。期貨交易涉及高槓桿風險，請自行評估。」

開始輸出："""

    return prompt


# ── Gemini 呼叫 ───────────────────────────────────────────────────────────────

# 模型偏好順序：越前面越優先
_MODEL_PREFERENCE = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"]


def _pick_best_model() -> str:
    """動態查詢 Gemini API 可用模型，回傳最強的一個。"""
    try:
        resp = requests.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}",
            timeout=10,
        )
        resp.raise_for_status()
        available = {m["name"].replace("models/", "") for m in resp.json().get("models", [])}
        for model in _MODEL_PREFERENCE:
            if model in available:
                logger.info("動態選擇 Gemini 模型: %s", model)
                return model
    except Exception as e:
        logger.warning("無法查詢 Gemini 模型列表（%s），使用預設", e)
    fallback = _MODEL_PREFERENCE[0]
    logger.info("使用預設 Gemini 模型: %s", fallback)
    return fallback


def call_gemini(prompt: str) -> str:
    """
    透過 REST API 呼叫 Gemini，啟用 Google Search grounding 取得當日新聞。
    動態選擇可用的最強模型。
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY 未設定")

    model = _pick_best_model()
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={GEMINI_API_KEY}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 16384,
        },
        "tools": [{"googleSearch": {}}],
    }

    try:
        resp = requests.post(url, json=payload, timeout=180)
        resp.raise_for_status()
        data = resp.json()

        # 記錄結束原因，方便診斷截斷問題
        finish_reason = data["candidates"][0].get("finishReason", "UNKNOWN")
        logger.info("Gemini finishReason: %s", finish_reason)
        if finish_reason == "MAX_TOKENS":
            logger.warning("⚠️ Gemini 輸出被截斷（達到 maxOutputTokens 上限）")

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        logger.info("Gemini 回傳內容（前 300 字）:\n%s", text[:300])

        # Gemini 常把 HTML 包在 ```html ... ``` 裡，剝掉包裝
        import re
        stripped = re.sub(r"^```[a-z]*\n?", "", text.strip(), flags=re.IGNORECASE)
        stripped = re.sub(r"\n?```\s*$", "", stripped.strip())
        return stripped.strip()
    except Exception as e:
        logger.error("Gemini REST API 呼叫失敗: %s", e)
        raise


# ── Email 寄送 ────────────────────────────────────────────────────────────────

def _markdown_to_html(md: str) -> str:
    """
    把 Gemini 回傳的 Markdown 轉成 email-safe HTML body 內容。
    不依賴外部套件，用正規表達式手動轉換。
    """
    import re

    def inline(text: str) -> str:
        text = re.sub(r"\*\*(.+?)\*\*", r'<strong>\1</strong>', text)
        text = re.sub(r"\*(.+?)\*",     r'<em>\1</em>', text)
        text = re.sub(r"`(.+?)`",       r'<code style="background:#f0f0f0;padding:1px 4px;border-radius:3px">\1</code>', text)
        return text

    # 剝掉 ```markdown / ``` 包裝（Gemini 偶爾會加）
    md = re.sub(r"^```[a-z]*\n?", "", md.strip(), flags=re.MULTILINE)
    md = re.sub(r"```$", "", md.strip(), flags=re.MULTILINE)
    md = md.strip()

    html_lines = []
    in_ul = False
    in_ol = False
    in_disclaimer = False

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            html_lines.append("</ul>")
            in_ul = False
        if in_ol:
            html_lines.append("</ol>")
            in_ol = False

    for raw_line in md.splitlines():
        line = raw_line.rstrip()

        if "免責聲明" in line and line.startswith("#"):
            in_disclaimer = True

        if line.startswith("#### "):
            close_lists()
            html_lines.append(f'<h4 style="color:#455a64;margin:16px 0 6px">{inline(line[5:].strip())}</h4>')
        elif line.startswith("### "):
            close_lists()
            html_lines.append(f'<h3 style="color:#37474f;margin:20px 0 8px;border-left:3px solid #90a4ae;padding-left:8px">{inline(line[4:].strip())}</h3>')
        elif line.startswith("## "):
            close_lists()
            html_lines.append(f'<h2 style="color:#1a237e;margin:28px 0 10px;background:#e8eaf6;padding:8px 12px;border-radius:4px">{inline(line[3:].strip())}</h2>')
        elif line.startswith("# "):
            close_lists()
            html_lines.append(f'<h1 style="color:#0d1b8a;border-bottom:3px solid #1a237e;padding-bottom:10px;margin-bottom:6px">{inline(line[2:].strip())}</h1>')
        elif line.startswith("- ") or line.startswith("* "):
            if not in_ul:
                if in_ol:
                    html_lines.append("</ol>"); in_ol = False
                html_lines.append('<ul style="margin:4px 0;padding-left:22px;line-height:1.8">')
                in_ul = True
            html_lines.append(f"<li>{inline(line[2:].strip())}</li>")
        elif re.match(r"^\d+\. ", line):
            if not in_ol:
                if in_ul:
                    html_lines.append("</ul>"); in_ul = False
                html_lines.append('<ol style="margin:4px 0;padding-left:22px;line-height:1.8">')
                in_ol = True
            item_text = re.sub(r"^\d+\.\s*", "", line).strip()
            html_lines.append(f"<li>{inline(item_text)}</li>")
        elif re.match(r"^[-=]{3,}$", line):
            close_lists()
            html_lines.append('<hr style="border:none;border-top:1px solid #ddd;margin:16px 0">')
        elif line == "":
            close_lists()
            html_lines.append("")
        else:
            close_lists()
            color = "color:#555;" if in_disclaimer else ""
            html_lines.append(f'<p style="margin:4px 0;line-height:1.8;{color}">{inline(line)}</p>')

    close_lists()
    return "\n".join(html_lines)


def _wrap_email_html(content: str, trade_date: str) -> str:
    """
    把 Gemini 回傳內容轉成完整 HTML email。
    - 若 Gemini 回傳完整 HTML（<!DOCTYPE 或 <html>）→ 直接插入 footer 使用
    - 否則視為 Markdown → 轉換成 HTML body
    """
    # 若 Gemini 已輸出完整 HTML，直接用（加 footer）
    c = content.strip()
    if c.lower().startswith("<!doctype") or c.lower().startswith("<html"):
        footer = (
            f'<div style="font-size:11px;color:#999;margin-top:24px;border-top:1px solid #eee;'
            f'padding-top:12px;text-align:center;font-family:Arial,sans-serif">'
            f'本郵件由台指金融資料庫自動系統寄送 &nbsp;|&nbsp; 資料日期：{trade_date}<br>'
            f'如需取消訂閱，請回覆此郵件並說明。<br>'
            f'<span style="color:#bbb">本報告不構成投資建議。</span></div>'
        )
        if "</body>" in c.lower():
            return c.replace("</body>", footer + "\n</body>", 1)
        return c + footer

    # 否則把 Markdown 轉成 HTML body
    body = _markdown_to_html(content)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body {{
    font-family: 'Helvetica Neue', Arial, 'PingFang TC', 'Microsoft JhengHei', sans-serif;
    color: #333; background: #f4f6fb;
    margin: 0; padding: 20px;
  }}
  .container {{
    max-width: 820px; margin: 0 auto;
    background: #fff; border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    padding: 32px 40px;
  }}
  .header {{
    background: linear-gradient(135deg,#1a237e,#283593);
    color: white; padding: 20px 24px; border-radius: 6px;
    margin-bottom: 28px;
  }}
  .header h1 {{ color:white; margin:0; font-size:20px; border:none; }}
  .header .subtitle {{ color:#c5cae9; font-size:13px; margin-top:4px; }}
  .disclaimer-box {{
    background: #fff8e1; border-left: 4px solid #ffa000;
    padding: 14px 18px; margin-top: 28px;
    font-size: 12px; color: #6d4c00; line-height: 1.8;
    border-radius: 0 4px 4px 0;
  }}
  .footer {{
    font-size: 11px; color: #999; margin-top: 24px;
    border-top: 1px solid #eee; padding-top: 12px;
    text-align: center;
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="h1">📊 台指籌碼觀察報告</div>
    <div class="subtitle">資料日期：{trade_date} &nbsp;|&nbsp; 資料來源：TAIFEX 公開資訊</div>
  </div>
  {body}
  <div class="footer">
    本郵件由台指金融資料庫自動系統寄送 &nbsp;|&nbsp; 資料日期：{trade_date}<br>
    如需取消訂閱，請回覆此郵件並說明。<br>
    <span style="color:#bbb">本報告不構成投資建議。期貨交易有高度風險，請自行評估。</span>
  </div>
</div>
</body>
</html>"""


def send_report_email(report_html: str, trade_date: str, recipients: list[str]):
    """透過 Gmail SMTP 寄送報告"""
    if not recipients:
        logger.warning("無收件人，跳過寄送")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"【台指籌碼觀察】{trade_date} 市場數據報告"
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

def _get_paid_member_emails() -> list[str]:
    """
    從 Supabase 查詢所有有效進階會員（pro / ultimate）的 email。
    失敗時 log warning 並回傳空清單（不中斷報告流程）。
    """
    try:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            logger.warning("SUPABASE 環境變數未設定，無法查詢進階會員")
            return []

        sb = create_client(url, key)
        sb.postgrest.auth(key)

        # 查詢所有 active 的 pro/ultimate 訂閱
        resp = (
            sb.table("user_subscriptions")
            .select("user_id")
            .in_("plan", ["pro", "ultimate"])
            .eq("status", "active")
            .execute()
        )
        user_ids = [row["user_id"] for row in (resp.data or [])]

        # 透過 admin API 取得每個 user 的 email
        emails = []
        for uid in user_ids:
            try:
                user_resp = sb.auth.admin.get_user_by_id(uid)
                if user_resp.user and user_resp.user.email:
                    emails.append(user_resp.user.email)
            except Exception as e:
                logger.warning("無法取得 user %s 的 email: %s", uid, e)

        logger.info("查詢到 %d 位進階會員收件人", len(emails))
        return emails

    except Exception as e:
        logger.warning("查詢進階會員 email 失敗（%s），繼續使用預設收件人", e)
        return []


def run(trade_date: date, recipients: list[str] = None):
    """
    生成並寄送當日市場籌碼觀察報告。

    Args:
        trade_date: 交易日期
        recipients: 手動指定收件人（覆蓋自動查詢）；
                    若未指定，自動查詢 Supabase 所有 active pro/ultimate 會員，
                    並加上環境變數 REPORT_RECIPIENTS 中的額外地址。
    """
    if recipients is None:
        # 自動查詢進階會員
        member_emails = _get_paid_member_emails()

        # 加上環境變數中額外指定的地址（如管理員通知）
        env_list = os.getenv("REPORT_RECIPIENTS", "")
        extra = [e.strip() for e in env_list.split(",") if e.strip()]

        # 合併去重
        recipients = list(dict.fromkeys(member_emails + extra))

    if not recipients:
        logger.warning("無進階會員且未設定 REPORT_RECIPIENTS，跳過寄送")
        return

    logger.info("開始生成 %s 報告，收件人（%d 位）：%s", trade_date, len(recipients), recipients)

    data = fetch_market_data(trade_date)
    prompt = build_prompt(data)
    report_html = call_gemini(prompt)
    send_report_email(report_html, str(trade_date), recipients)

    logger.info("報告生成並寄送完成")
