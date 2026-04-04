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

    prompt = f"""你是一位頂級的台指期貨與選擇權籌碼分析師，擁有豐富的實戰經驗。
今日任務：根據以下 TAIFEX 實際數據，撰寫一份深度、專業、有洞見的市場籌碼觀察報告。

==================================================
⚠️  嚴格合規限制（全程必須遵守，違反即報告無效）
==================================================
絕對禁止：
  × 給予任何「建議買進/賣出」「應該持有」「值得買」等操作指令
  × 直接預測指數漲跌方向或點位（「指數將會上漲/下跌」）
  × 使用「支撐」「壓力」「突破」「跌破」「強烈看好/看壞」等投顧術語
  × 任何形式的暗示性操作建議

允許且鼓勵：
  ✓ 客觀陳述「哪個履約價 OI 最集中」「各群體淨口數的實際數字」
  ✓ 深度解讀籌碼結構背後的市場邏輯（描述現象，不給操作指令）
  ✓ 條件式歷史觀察：「歷史資料顯示，當 [X] 出現時，市場曾觀察到 [Y]，但不代表必然」
  ✓ 情境引導：「若 [事件發生]，可關注 [指標] 的變化」
  ✓ 根據實際數據說明關鍵價位區間，讓讀者自行思考
==================================================

==================================================
📊 今日 TAIFEX 市場原始數據（{ds}）
==================================================

【期貨籌碼】
TX 近月收盤價     : {d['tx_close'] or '（無資料）'} 點
外資 期貨淨口數   : {ext_fut.get('net_oi', '—')} 口（正=多方淨部位）
自營商 期貨淨口數 : {dlr_fut.get('net_oi', '—')} 口
散戶 期貨淨口數   : {ret_f.get('net_oi', '—')} 口
外資 期貨 delta   : {ext_dir.get('futures_delta_mtx', '—')} 小台
外資 選擇權 delta : {ext_dir.get('options_delta_mtx', '—')} 小台（BC+SP-SC-BP 折算）
外資 合計 delta   : {ext_dir.get('total_delta_mtx', '—')} 小台

【選擇權籌碼】
PCR（P/C 比）     : {d['pcr'].get('put_call_ratio', '—')}
Max Pain 點位     : {mp.get('max_pain_strike', '—')} 點（距現價 {mp.get('delta_pts', '—')} pts）
週選主力到期      : {ois.get('weekly_dominant_exp', '—')}
週選 OI 比重      : {weekly_ratio_pct:.1f}%

外資選擇權部位（口）:
  BC={ext_opt.get('call_buy_oi','—')}  SC={ext_opt.get('call_sell_oi','—')}  BP={ext_opt.get('put_buy_oi','—')}  SP={ext_opt.get('put_sell_oi','—')}

散戶選擇權部位（口）:
  BC={ret_o.get('call_buy_oi','—')}  SC={ret_o.get('call_sell_oi','—')}  BP={ret_o.get('put_buy_oi','—')}  SP={ret_o.get('put_sell_oi','—')}

自營商選擇權部位（口）:
  BC={dlr_opt.get('call_buy_oi','—')}  SC={dlr_opt.get('call_sell_oi','—')}  BP={dlr_opt.get('put_buy_oi','—')}  SP={dlr_opt.get('put_sell_oi','—')}

投信選擇權部位（口）:
  BC={tit_opt.get('call_buy_oi','—')}  SC={tit_opt.get('call_sell_oi','—')}  BP={tit_opt.get('put_buy_oi','—')}  SP={tit_opt.get('put_sell_oi','—')}

ITM/ATM/OTM 分布（口）:
  Call: ITM={itm.get('call_itm_oi','—')} / ATM={itm.get('call_atm_oi','—')} / OTM={itm.get('call_otm_oi','—')}
  Put : ITM={itm.get('put_itm_oi','—')} / ATM={itm.get('put_atm_oi','—')} / OTM={itm.get('put_otm_oi','—')}

OI 最集中履約價 Top 5（Call+Put 合計）:
{top5_lines}

==================================================
📋 報告輸出要求
==================================================

請用純文字（Markdown 格式）輸出報告內容，不要輸出任何 HTML 標籤。
使用 # ## ### 作為標題層級，用 **粗體** 標示重要數字，用 - 或數字列表。
格式範例：
  ## 一、籌碼現況總結
  ### （一）選擇權關鍵價位
  **Max Pain：19,000 點**，距現價 -250 點
  - OI 最集中：18,800 點...

必須按以下章節順序完整輸出：

─────────────────────────────────────────────────
一、籌碼現況總結
─────────────────────────────────────────────────

（一）選擇權關鍵價位
請根據 OI Top5 數據，說明：
- 即將結算的週選（{ois.get('weekly_dominant_exp', '本週')}）OI 最集中的履約價是哪個？
- Call 端與 Put 端各自的最大 OI 履約價在哪裡？
- Max Pain 目前在 {mp.get('max_pain_strike', '—')} 點，與現價 {d['tx_close'] or '—'} 點相差 {mp.get('delta_pts', '—')} 點，
  這個差距在歷史上代表什麼樣的結算動態？（條件式描述）
- 整體 OI 分布顯示市場目前把注碼集中在哪個價格區間？

（二）三大法人與散戶的布局解讀
請深度分析（用實際數字支撐，不給操作建議）：
- 外資在期貨端（淨口數）與選擇權端（delta）的方向是否一致？若有分歧代表什麼？
- 外資選擇權的 BC vs SC、BP vs SP 各自的口數，揭示外資目前是買方策略還是賣方策略？
- 自營商選擇權布局的特徵為何？（偏買方還是賣方？BC/SC 比 or BP/SP 比）
- 散戶的 BC/BP 比例（BC={ret_o.get('call_buy_oi','—')} vs BP={ret_o.get('put_buy_oi','—')}）顯示散戶整體傾向為何？
  歷史上這樣的散戶結構出現時，市場曾有哪些走向？（條件式，不做預測）
- 三大法人與散戶方向是否出現顯著差異？這種差異在籌碼學上的意涵為何？

（三）短線（週選）vs 長線（月選）籌碼狀況
- 目前週選 OI 占比 {weekly_ratio_pct:.1f}%，代表目前市場主要參與者以短線還是長線佈局為主？
- ITM/ATM/OTM 比例揭示市場目前對於價格停留區間的預期集中在哪裡？
- 週選即將結算（{ois.get('weekly_dominant_exp', '—')}），若結算前出現什麼樣的籌碼變化值得特別留意？

─────────────────────────────────────────────────
二、時事結合（請使用 Google Search 搜尋後填入）
─────────────────────────────────────────────────

搜尋關鍵字：「台股 台指期 {ds}」「TAIEX {ds}」「美股 {ds}」「台幣匯率 {ds}」
請列出今日對台指有潛在影響的重要市場事件，包括但不限於：
- 美股前日走勢與主要科技股動態
- 台幣兌美元匯率變化
- 重要總經數據公布（CPI、非農、Fed 官員講話等）
- 台灣在地事件（外資買賣超、上市公司法說/財報、政策面消息）
- 地緣政治或國際貿易相關消息

每個事件：
1. 客觀描述「發生了什麼」（純事實，不加方向判斷）
2. 說明「若此事件持續發展，可觀察 [哪個期貨/選擇權指標] 的變化」

─────────────────────────────────────────────────
三、值得持續觀察的重點（3～5 點）
─────────────────────────────────────────────────

根據今日數據，列出後續最值得追蹤的籌碼指標或價位，每點需：
- 引用實際數字
- 說明為何值得關注
- 允許使用條件式歷史觀察句型

─────────────────────────────────────────────────
四、免責聲明（必須逐字完整保留）
─────────────────────────────────────────────────

「本報告所有內容均源自台灣期貨交易所（TAIFEX）公開資訊及公開新聞媒體，
 由 AI 系統自動整理生成，僅供資料呈現與學術研究用途，
 不構成任何投資建議、期貨交易建議或買賣推薦。
 本服務不具期貨信託事業、期貨顧問事業或任何金融從業資格。
 期貨交易涉及高度槓桿風險，可能損失全部本金。
 任何投資決策請自行評估風險，並諮詢合格之期貨顧問。
 過去的數據走勢不代表未來的交易結果。」

現在請開始輸出 Markdown 格式報告（純文字，不要任何 HTML 標籤）："""

    return prompt


# ── Gemini 呼叫 ───────────────────────────────────────────────────────────────

def call_gemini(prompt: str) -> str:
    """
    透過 REST API 呼叫 Gemini，啟用 Google Search grounding 取得當日新聞。
    使用 v1beta endpoint 以確保 grounding 功能可用。
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY 未設定")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-pro-latest:generateContent?key={GEMINI_API_KEY}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
        },
        "tools": [{"googleSearch": {}}],
    }

    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
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

def run(trade_date: date, recipients: list[str] = None):
    """
    生成並寄送當日市場籌碼觀察報告。

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
