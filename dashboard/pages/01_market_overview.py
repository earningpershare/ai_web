"""
市場快照 — 免費頁面
三大法人期貨淨部位 + 未平倉口數概覽（永遠顯示最近一個交易日資料）
"""
import os
from datetime import date, timedelta

import requests
import streamlit as st
from auth import auth_sidebar

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="市場快照", page_icon="📊", layout="wide")
auth_sidebar()

st.title("📊 市場快照")
st.caption("三大法人期貨籌碼概覽 — 每交易日收盤後更新　🟢 免費公開")
st.divider()


# ── 資料載入 ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=600)
def load_institutional_futures():
    """往回查 30 天，確保假日/長假也能找到最近交易日"""
    end = date.today()
    start = end - timedelta(days=30)
    try:
        r = requests.get(
            f"{API_URL}/institutional/futures",
            params={
                "start": str(start),
                "end": str(end),
                "contract": "TX",
                "limit": 50,
            },
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


@st.cache_data(ttl=600)
def load_retail_futures():
    end = date.today()
    start = end - timedelta(days=30)
    try:
        r = requests.get(
            f"{API_URL}/retail/futures",
            params={"start": str(start), "end": str(end), "limit": 10},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


data = load_institutional_futures()
retail_data = load_retail_futures()

# 取得最新交易日與各法人資料
if not data:
    st.warning("暫無資料，可能尚未到交易日收盤時間，請稍後再試。")
    st.stop()

latest_date = data[0]["trade_date"]

# 按最新日期篩選三大法人
latest = {row["institution_type"]: row for row in data if row["trade_date"] == latest_date}

# 取前一交易日（比較用）
prev_dates = sorted({row["trade_date"] for row in data if row["trade_date"] != latest_date}, reverse=True)
prev_date = prev_dates[0] if prev_dates else None
prev = {row["institution_type"]: row for row in data if row["trade_date"] == prev_date} if prev_date else {}

# ── 日期標題 ──────────────────────────────────────────────────────────────────

st.markdown(
    f'<div style="font-size:14px;color:#888;margin-bottom:4px">'
    f'最新資料日期：<strong style="color:#e0e0e0">{latest_date}</strong>'
    f'{"　前一交易日：" + prev_date if prev_date else ""}'
    f'</div>',
    unsafe_allow_html=True,
)
st.markdown("<br>", unsafe_allow_html=True)

# ── 三大法人淨口數指標 ─────────────────────────────────────────────────────────

INST_MAP = {
    "外資": ("外資及陸資", "#4f8ef7"),
    "投信": ("投信", "#a78bfa"),
    "自營商": ("自營商", "#34d399"),
}

cols = st.columns(3)
for col, (label, (inst_key, color)) in zip(cols, INST_MAP.items()):
    row = latest.get(inst_key, {})
    prev_row = prev.get(inst_key, {})
    net_oi = row.get("net_oi", 0) or 0
    prev_net_oi = prev_row.get("net_oi", 0) or 0
    delta = net_oi - prev_net_oi

    arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "─")
    delta_color = "#4ade80" if delta > 0 else ("#f87171" if delta < 0 else "#888")
    oi_color = color if net_oi != 0 else "#888"

    col.markdown(
        f"""
        <div style="background:#111;border:1px solid #222;border-radius:10px;padding:20px 16px;">
          <div style="font-size:13px;color:#888;margin-bottom:6px">{label} 期貨淨未平倉</div>
          <div style="font-size:28px;font-weight:bold;color:{oi_color}">
            {net_oi:+,} 口
          </div>
          <div style="font-size:13px;color:{delta_color};margin-top:6px">
            {arrow} 較前日 {delta:+,} 口
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ── 散戶多空比（最新） ────────────────────────────────────────────────────────

if retail_data:
    retail_latest = retail_data[0]
    retail_long = retail_latest.get("long_oi", 0) or 0
    retail_short = retail_latest.get("short_oi", 0) or 0
    retail_net = retail_latest.get("net_oi", 0) or 0
    retail_date = retail_latest.get("trade_date", "—")

    net_color = "#4ade80" if retail_net > 0 else ("#f87171" if retail_net < 0 else "#888")

    st.markdown("#### 散戶期貨部位概況")
    rc1, rc2, rc3 = st.columns(3)
    rc1.markdown(
        f"""
        <div style="background:#111;border:1px solid #222;border-radius:10px;padding:16px;">
          <div style="font-size:12px;color:#888">散戶多單未平倉</div>
          <div style="font-size:22px;font-weight:bold;color:#4ade80">{retail_long:,} 口</div>
        </div>
        """, unsafe_allow_html=True,
    )
    rc2.markdown(
        f"""
        <div style="background:#111;border:1px solid #222;border-radius:10px;padding:16px;">
          <div style="font-size:12px;color:#888">散戶空單未平倉</div>
          <div style="font-size:22px;font-weight:bold;color:#f87171">{retail_short:,} 口</div>
        </div>
        """, unsafe_allow_html=True,
    )
    rc3.markdown(
        f"""
        <div style="background:#111;border:1px solid #222;border-radius:10px;padding:16px;">
          <div style="font-size:12px;color:#888">散戶淨部位</div>
          <div style="font-size:22px;font-weight:bold;color:{net_color}">{retail_net:+,} 口</div>
        </div>
        """, unsafe_allow_html=True,
    )
    st.caption(f"資料日期：{retail_date}")
    st.markdown("<br>", unsafe_allow_html=True)

# ── 近 5 日三大法人淨口數趨勢（簡易表格）────────────────────────────────────

st.markdown("#### 近期三大法人期貨淨未平倉（TX）")

# 整理成表格
trade_dates = sorted({row["trade_date"] for row in data}, reverse=True)[:5]
table_rows = []
for d in trade_dates:
    day_data = {row["institution_type"]: row for row in data if row["trade_date"] == d}
    table_rows.append({
        "日期": d,
        "外資淨口": day_data.get("外資及陸資", {}).get("net_oi", "—"),
        "投信淨口": day_data.get("投信", {}).get("net_oi", "—"),
        "自營商淨口": day_data.get("自營商", {}).get("net_oi", "—"),
    })

if table_rows:
    import pandas as pd
    df = pd.DataFrame(table_rows)

    def color_val(v):
        if isinstance(v, (int, float)):
            color = "#4ade80" if v > 0 else ("#f87171" if v < 0 else "#888")
            return f"color: {color}"
        return "color: #aaa"

    st.dataframe(
        df.style.applymap(color_val, subset=["外資淨口", "投信淨口", "自營商淨口"]),
        use_container_width=True,
        hide_index=True,
    )

st.divider()

# ── 升級 CTA ──────────────────────────────────────────────────────────────────

st.markdown(
    """
    <div style="background:#0d1a2e;border:1px solid #1e3a5f;border-radius:12px;padding:28px 32px;">
      <div style="font-size:18px;font-weight:bold;color:#4f8ef7;margin-bottom:12px">
        🔵 想看更深入的分析？
      </div>
      <div style="color:#aaa;line-height:1.8;margin-bottom:20px">
        ✅ &nbsp;選擇權資金地圖（各履約價資金分布、PCR、Max Pain）<br>
        ✅ &nbsp;外資累計 Delta 趨勢（期貨 + 選擇權合計折算）<br>
        ✅ &nbsp;散戶選擇權成本分析 vs 現價<br>
        ✅ &nbsp;每日 AI 籌碼觀察報告 Email<br>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown("<br>", unsafe_allow_html=True)
_, cta_col, _ = st.columns([1, 1, 1])
with cta_col:
    if st.button("查看進階版方案 →", use_container_width=True, type="primary", key="_overview_cta"):
        st.switch_page("pages/05_pricing.py")

st.divider()
st.caption(
    "資料來源：台灣期貨交易所（TAIFEX）公開資訊  |  "
    "本站不提供投資建議  |  期貨交易涉及高度風險，可能損失全部本金"
)
