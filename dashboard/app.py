"""
台指金融資料庫 — 首頁
"""
import os
from datetime import date, timedelta

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="台指金融資料庫",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📈 台指金融資料庫")
st.caption("TAIFEX 期交所資料 — 即時分析平台")
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

# ── 頁面導覽 ─────────────────────────────────────────────────────────────────

st.subheader("功能頁面")

c1, c2 = st.columns(2)

with c1:
    st.info("""
**📊 選擇權資金地圖**
（左側選單 → 02 options map）

- 選擇權 T 字報價表 + 各履約價資金分布（含歷史累積成本色彩）
- 外資 / 散戶 BC / BP / SC / SP 每日變化
- 各身份別持倉比例圓餅圖
- ITM / OTM 未平倉分布
- PCR、Max Pain、關鍵支撐壓力位
""")

with c2:
    st.info("""
**🔬 市場進階分析**
（左側選單 → 03 market analysis）

- ⭐⭐⭐ 外資累計 Delta 趨勢（期貨 + 選擇權合計，折算小台）
- ⭐⭐⭐ Max Pain 移動方向 vs 現價
- ⭐⭐⭐ 散戶買 Call 平均成本 vs 現價
- ⭐⭐ 週選 / 月選 OI 比重
- ⭐⭐ 外資選擇權金額流向（千元）
""")

st.divider()
st.caption("資料來源：台灣期貨交易所（TAIFEX）  |  更新頻率：每交易日收盤後自動爬取")
