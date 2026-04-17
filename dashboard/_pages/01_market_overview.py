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

auth_sidebar()

st.title("📊 市場快照")
st.caption("三大法人期貨籌碼概覽 — 每交易日收盤後更新　🟢 免費公開")

# ── 夜盤速覽（差異化籌碼資訊） ──────────────────────────────────────────────────
st.markdown("### 🌙 最新夜盤速覽")
try:
    _ns_resp = requests.get(f"{API_URL}/market/night-session", timeout=10)
    _ns_resp.raise_for_status()
    _ns = _ns_resp.json()
except Exception:
    _ns = {}

if _ns and _ns.get("night_session"):
    _td = _ns.get("trade_date", "—")
    _day = _ns.get("day_session") or {}
    _night = _ns.get("night_session") or {}
    _gap = _ns.get("gap_day_to_night")
    _gap_pct = _ns.get("gap_day_to_night_pct")
    _opt = _ns.get("options_night_summary") or {}
    _gap_color = "#EF5350" if (_gap or 0) < 0 else "#66BB6A" if (_gap or 0) > 0 else "#888"
    _gap_sign = "+" if (_gap or 0) > 0 else ""

    _ns_cols = st.columns(4)
    _ns_cols[0].metric("夜盤收盤", f"{_night.get('close', '—'):,.0f}" if _night.get("close") else "—",
                       delta=None)
    _ns_cols[1].metric("日盤→夜盤缺口",
                       f"{_gap_sign}{_gap:,.0f} 點" if _gap is not None else "—",
                       delta=f"{_gap_sign}{_gap_pct:.2f}%" if _gap_pct is not None else None,
                       delta_color="normal" if (_gap or 0) >= 0 else "inverse")
    _ns_cols[2].metric("夜盤成交量", f"{_night.get('volume', 0):,}" if _night.get("volume") else "—")
    _cv = _opt.get("call_volume") or 0
    _pv = _opt.get("put_volume") or 0
    _pcr = (_pv / _cv) if _cv else None
    _ns_cols[3].metric("夜盤選擇權 P/C Ratio",
                       f"{_pcr:.2f}" if _pcr is not None else "—",
                       help=f"Call {_cv:,} / Put {_pv:,}")
    st.caption(f"資料日期：{_td}　|　夜盤 15:00~次日 05:00　|　詳細分析見 [市場進階分析](/analysis)（Pro）")
else:
    st.caption("目前無最新夜盤資料。")

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
                "contract": "臺股期貨",
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
retail_data = [r for r in load_retail_futures() if r.get("contract_code") == "臺股期貨"]

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

# ── 今日籌碼重點摘要 ──────────────────────────────────────────────────────────
st.subheader("📊 今日籌碼重點")

# 從已載入的 latest / prev / retail_data 取出關鍵數字（不重複呼叫 API）

# 1. 外資期貨淨口數與日增減
foreign_row = latest.get("外資及陸資", {})
foreign_prev_row = prev.get("外資及陸資", {})
foreign_net = foreign_row.get("net_oi", None)
foreign_prev_net = foreign_prev_row.get("net_oi", None)
foreign_delta = (foreign_net - foreign_prev_net) if (foreign_net is not None and foreign_prev_net is not None) else None

# 2. 三大法人合計淨口數
_institutions = ["外資及陸資", "投信", "自營商"]
combined_net = None
_all_present = all(latest.get(i, {}).get("net_oi") is not None for i in _institutions)
if _all_present:
    combined_net = sum(latest.get(i, {}).get("net_oi", 0) or 0 for i in _institutions)

# 3. PCR（Put/Call OI Ratio）— 從 retail_data 或另外載入
@st.cache_data(ttl=600)
def load_pcr_latest():
    """只取最近一筆 PCR"""
    try:
        r = requests.get(
            f"{API_URL}/pcr",
            params={"limit": 1},
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json()
        return rows[0] if rows else None
    except Exception:
        return None

pcr_row = load_pcr_latest()
pcr_oi_ratio = None
if pcr_row:
    pcr_oi_ratio = pcr_row.get("oi_ratio")  # 通常是 put_oi / call_oi * 100

# ── 判斷邏輯（規則式，無 AI）────────────────────────────────────────────────

def _direction_label(net):
    """根據淨口數產生偏多/偏空標籤與顏色"""
    if net is None:
        return "數據待更新", "#888"
    if net > 0:
        return "偏多 ▲", "#4ade80"
    elif net < 0:
        return "偏空 ▼", "#f87171"
    else:
        return "中性 ─", "#facc15"

def _pcr_label(ratio):
    """PCR OI 比率判斷：> 100% 偏空保護；< 100% 偏多樂觀"""
    if ratio is None:
        return "數據待更新", "#888", "—"
    ratio_pct = float(ratio)
    if ratio_pct > 120:
        return "選擇權偏空保護", "#f87171", f"{ratio_pct:.1f}%"
    elif ratio_pct > 100:
        return "略偏空保護", "#fb923c", f"{ratio_pct:.1f}%"
    elif ratio_pct > 80:
        return "偏多樂觀", "#4ade80", f"{ratio_pct:.1f}%"
    else:
        return "強烈偏多", "#22d3ee", f"{ratio_pct:.1f}%"

def _summary_sentence(foreign_n, combined_n, pcr_r):
    """產生一句話文字摘要"""
    parts = []
    if foreign_n is not None:
        if foreign_n > 0:
            parts.append("外資持多單")
        elif foreign_n < 0:
            parts.append("外資持空單")
    if combined_n is not None:
        if combined_n > 0:
            parts.append("三大法人合計偏多")
        elif combined_n < 0:
            parts.append("三大法人合計偏空")
    if pcr_r is not None:
        ratio_pct = float(pcr_r)
        if ratio_pct > 100:
            parts.append("選擇權市場有下跌避險需求")
        else:
            parts.append("選擇權市場情緒偏樂觀")
    if not parts:
        return "今日尚無交易數據，請於交易日收盤後查看。"
    return "；".join(parts) + "。"

foreign_label, foreign_color = _direction_label(foreign_net)
combined_label, combined_color = _direction_label(combined_net)
pcr_label, pcr_color, pcr_display = _pcr_label(pcr_oi_ratio)
summary_text = _summary_sentence(foreign_net, combined_net, pcr_oi_ratio)

# ── 4 個指標卡片 ─────────────────────────────────────────────────────────────

m1, m2, m3, m4 = st.columns(4)

with m1:
    delta_str = f"{foreign_delta:+,} 口" if foreign_delta is not None else "無前日資料"
    net_str = f"{foreign_net:+,} 口" if foreign_net is not None else "—"
    st.markdown(
        f"""
        <div style="background:#111;border:1px solid #222;border-radius:10px;padding:18px 14px;">
          <div style="font-size:12px;color:#888;margin-bottom:4px">外資期貨淨口數</div>
          <div style="font-size:22px;font-weight:bold;color:{foreign_color}">{net_str}</div>
          <div style="font-size:12px;color:#aaa;margin-top:4px">較前日 {delta_str}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m2:
    combined_str = f"{combined_net:+,} 口" if combined_net is not None else "—"
    st.markdown(
        f"""
        <div style="background:#111;border:1px solid #222;border-radius:10px;padding:18px 14px;">
          <div style="font-size:12px;color:#888;margin-bottom:4px">三大法人合計</div>
          <div style="font-size:22px;font-weight:bold;color:{combined_color}">{combined_str}</div>
          <div style="font-size:12px;color:#aaa;margin-top:4px">{combined_label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m3:
    st.markdown(
        f"""
        <div style="background:#111;border:1px solid #222;border-radius:10px;padding:18px 14px;">
          <div style="font-size:12px;color:#888;margin-bottom:4px">Put/Call OI 比率</div>
          <div style="font-size:22px;font-weight:bold;color:{pcr_color}">{pcr_display}</div>
          <div style="font-size:12px;color:#aaa;margin-top:4px">{pcr_label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m4:
    # 散戶方向（已在頁面載入）
    if retail_data:
        r_net = retail_data[0].get("net_oi", None)
        r_label, r_color = _direction_label(r_net)
        r_str = f"{r_net:+,} 口" if r_net is not None else "—"
    else:
        r_str, r_label, r_color = "—", "數據待更新", "#888"
    st.markdown(
        f"""
        <div style="background:#111;border:1px solid #222;border-radius:10px;padding:18px 14px;">
          <div style="font-size:12px;color:#888;margin-bottom:4px">散戶期貨淨部位</div>
          <div style="font-size:22px;font-weight:bold;color:{r_color}">{r_str}</div>
          <div style="font-size:12px;color:#aaa;margin-top:4px">{r_label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ── 一句話摘要 ────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div style="background:#0d1117;border-left:4px solid #4f8ef7;border-radius:0 8px 8px 0;
                padding:14px 20px;color:#e0e0e0;font-size:14px;line-height:1.7">
      <span style="color:#4f8ef7;font-weight:bold">今日小結</span>　{summary_text}
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown("<br>", unsafe_allow_html=True)

# ── 免費用戶升級 CTA（付費用戶不顯示）────────────────────────────────────────
from auth import has_plan as _has_plan
if not _has_plan("pro"):
    st.markdown(
        """
        <div style="background:#0a1628;border:1px dashed #2a4a7f;border-radius:10px;
                    padding:16px 24px;text-align:center;color:#aaa;font-size:14px">
          👆 完整趨勢圖表、選擇權資金地圖與歷史數據 →
          <strong style="color:#4f8ef7">Pro 版解鎖</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)
    _, _cta2, _ = st.columns([1, 1, 1])
    with _cta2:
        if st.button("升級 Pro 解鎖完整功能 →", use_container_width=True, type="primary", key="_summary_cta"):
            st.switch_page("_pages/05_pricing.py")
    st.markdown("<br>", unsafe_allow_html=True)

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
        st.switch_page("_pages/05_pricing.py")

st.divider()
st.caption(
    "資料來源：台灣期貨交易所（TAIFEX）公開資訊  |  "
    "本站不提供投資建議  |  期貨交易涉及高度風險，可能損失全部本金"
)
