"""
台指天空 SpaceTFX — 首頁
"""
import os
from datetime import date, timedelta

import requests
import streamlit as st
from auth import auth_sidebar, is_logged_in, has_plan, show_login_modal, PLAN_LABEL

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="台指天空 SpaceTFX",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

auth_sidebar()

# 從驗證信頁面跳回來時，自動彈出登入框
if st.session_state.pop("_auto_show_login", False) and not is_logged_in():
    show_login_modal()

st.title("🚀 台指天空 SpaceTFX")
st.caption("從高空俯視台指市場　TAIFEX 籌碼數據平台")
st.divider()

st.warning(
    "⚠️ **免責聲明**　本網站所有資料均源自台灣期貨交易所（TAIFEX）公開資訊，"
    "僅供資料呈現與學術研究用途，**不構成任何投資建議、期貨交易建議或買賣推薦**。"
    "期貨交易涉及高度風險，可能損失全部本金。本網站不具期貨信託事業、期貨顧問事業"
    "或任何金融從業資格，不得視為期貨投資分析意見。任何投資決策請自行評估風險，"
    "並諮詢合格之期貨顧問。**過去的數據走勢不代表未來的交易結果。**"
)

st.divider()

# ── 系統狀態 ─────────────────────────────────────────────────────────────────

col1, col2, col3 = st.columns(3)

try:
    r = requests.get(f"{API_URL}/health", timeout=5)
    api_ok = r.status_code == 200
except Exception:
    api_ok = False

col1.metric("API 狀態", "✅ 正常" if api_ok else "❌ 離線")

if api_ok:
    try:
        r = requests.get(f"{API_URL}/crawler-log", params={"limit": 1, "status": "success"}, timeout=5)
        logs = r.json()
        last_run = logs[0]["executed_at"][:10] if logs else "—"
    except Exception:
        last_run = "—"
    col2.metric("最後爬蟲時間", last_run)

    try:
        r = requests.get(f"{API_URL}/market/max-pain", params={"limit": 1}, timeout=5)
        mp = r.json()
        last_data = mp[0]["trade_date"] if mp else "—"
    except Exception:
        last_data = "—"
    col3.metric("最新資料日期", last_data)

st.divider()

# ── 功能頁面 ──────────────────────────────────────────────────────────────────

st.subheader("功能頁面")

FREE_BADGE = "🟢 免費"
PRO_BADGE  = "🔵 進階版"

# 免費功能
with st.container(border=True):
    st.markdown(f"**📊 市場快照** &nbsp; `{FREE_BADGE}`")
    st.markdown(
        "- 三大法人期貨淨未平倉口數（最新 + 近 5 日趨勢）\n"
        "- 散戶期貨多空部位概況\n"
        "- 升級 CTA（引導查看完整分析）"
    )
    if st.button("前往頁面 →", key="_go_01", use_container_width=True):
        st.switch_page("pages/01_market_overview.py")

st.markdown("<br>", unsafe_allow_html=True)

c1, c2 = st.columns(2)

with c1:
    # 付費功能
    locked = not (is_logged_in() and has_plan("pro"))
    badge = PRO_BADGE if locked else f"{PRO_BADGE} ✅"
    with st.container(border=True):
        st.markdown(f"**📊 選擇權資金地圖** &nbsp; `{badge}`")
        st.markdown(
            "- 選擇權 T 字報價表 + 各履約價資金分布（含歷史累積成本色彩）\n"
            "- 外資 / 散戶 BC / BP / SC / SP 每日變化\n"
            "- 各身份別持倉比例圓餅圖\n"
            "- ITM / OTM 未平倉分布\n"
            "- PCR、Max Pain、關鍵價位"
        )
        if locked:
            if st.button("🔒 解鎖此功能", key="_unlock_02", use_container_width=True, type="primary"):
                if not is_logged_in():
                    show_login_modal()
                else:
                    st.switch_page("pages/05_pricing.py")
        else:
            if st.button("前往頁面 →", key="_go_02", use_container_width=True):
                st.switch_page("pages/02_options_map.py")

with c2:
    # 付費功能
    locked = not (is_logged_in() and has_plan("pro"))
    with st.container(border=True):
        st.markdown(f"**🔬 市場進階分析** &nbsp; `{badge}`")
        st.markdown(
            "- ⭐⭐⭐ 外資累計 Delta 趨勢（期貨 + 選擇權合計，折算小台）\n"
            "- ⭐⭐⭐ Max Pain 移動方向 vs 現價\n"
            "- ⭐⭐⭐ 散戶買 Call 平均成本 vs 現價\n"
            "- ⭐⭐ 週選 / 月選 OI 比重\n"
            "- ⭐⭐ 外資選擇權金額流向（千元）"
        )
        if locked:
            if st.button("🔒 解鎖此功能", key="_unlock_03", use_container_width=True, type="primary"):
                if not is_logged_in():
                    show_login_modal()
                else:
                    st.switch_page("pages/05_pricing.py")
        else:
            if st.button("前往頁面 →", key="_go_03", use_container_width=True):
                st.switch_page("pages/03_market_analysis.py")

st.divider()

# ── 每日籌碼報告（付費功能說明） ──────────────────────────────────────────────

with st.container(border=True):
    st.markdown(f"**📧 每日籌碼觀察報告 Email** &nbsp; `{PRO_BADGE}`")
    st.markdown(
        "每個交易日收盤後，系統自動以 AI 分析當日籌碼數據並寄送報告至您的信箱。\n\n"
        "訂閱進階版後，系統會以您的註冊 Email 自動加入寄送名單。"
    )
    if not (is_logged_in() and has_plan("pro")):
        col_a, col_b = st.columns([1, 3])
        with col_a:
            if st.button("查看方案", key="_report_plan", use_container_width=True, type="primary"):
                st.switch_page("pages/05_pricing.py")

st.divider()
st.caption(
    "資料來源：台灣期貨交易所（TAIFEX）公開資訊  |  更新頻率：每交易日收盤後自動彙整  |  "
    "本站不提供投資建議  |  [隱私權政策](./04_privacy)"
)
