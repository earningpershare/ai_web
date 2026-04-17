"""
市場進階分析 — 6 個方向性指標
"""
import os
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import requests

API_URL = os.getenv("API_URL", "http://localhost:8000")

from auth import require_plan, auth_sidebar, has_plan, show_blur_gate
auth_sidebar()
# 免費/未登入用戶顯示模糊預覽遮罩而非硬性擋牆，降低轉換障礙
if not has_plan("pro"):
    show_blur_gate("市場進階分析")

st.title("市場進階分析")
st.caption("⚠️ 本頁所有數據均源自 TAIFEX 公開資訊，僅供資料呈現與學術研究。不構成投資建議或期貨交易推薦。期貨交易涉及高度風險，請自行評估。")

# ── helper ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def fetch(endpoint: str, params: dict = None) -> pd.DataFrame:
    try:
        r = requests.get(f"{API_URL}{endpoint}", params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        st.error(f"API 錯誤 {endpoint}: {e}")
        return pd.DataFrame()


def safe_float(v, default=0.0):
    try:
        return float(v or default)
    except Exception:
        return default


def safe_int(v, default=0):
    try:
        return int(v or default)
    except Exception:
        return default


# ── sidebar ──────────────────────────────────────────────────────────────────

st.sidebar.header("區間設定")
end_date   = st.sidebar.date_input("結束日期", value=date.today() - timedelta(days=1))
start_date = st.sidebar.date_input("開始日期", value=end_date - timedelta(days=30))
params_range = {"start": start_date, "end": end_date, "limit": 500}

st.sidebar.markdown("---")
st.sidebar.caption("資料來源：TAIFEX 期交所")


# ═══════════════════════════════════════════════════════════════════════════════
# 指標 1：外資累計 delta 趨勢
# ═══════════════════════════════════════════════════════════════════════════════

st.header("⭐⭐⭐ 指標一：外資累計 Delta 趨勢")

with st.expander("指標說明", expanded=True):
    st.markdown("""
**指標說明：** 外資期貨淨 OI 與選擇權淨部位合計之 delta 值（折算小台口數），
反映外資整體持倉方向的統計結果。
**數據解讀（歷史統計觀察，不代表未來走勢）：**
- delta 持續往正方向移動 → 外資多方部位口數增加的歷史統計
- delta 持續往負方向移動 → 外資空方部位口數增加的歷史統計
- 期貨 delta 與選擇權 delta 方向相反 → 代表外資可能以選擇權進行部位對沖，整體方向較為複雜

本指標為持倉數據統計，不構成任何交易建議。
    """)

dir_df = fetch("/market/direction", params_range)
if not dir_df.empty:
    dir_df["trade_date"] = pd.to_datetime(dir_df["trade_date"])
    dir_df = dir_df.sort_values("trade_date")

    ext_df  = dir_df[dir_df["group_type"] == "外資及陸資"]
    ret_df  = dir_df[dir_df["group_type"] == "散戶"]
    inst_df = dir_df[dir_df["group_type"] == "三大法人"]

    # latest metrics
    if not ext_df.empty:
        last = ext_df.iloc[-1]
        c1, c2, c3 = st.columns(3)
        c1.metric("外資 期貨 delta（小台）",
                  f"{safe_float(last['futures_delta_mtx']):+,.0f}",
                  help="TX×4 + MTX×1 + MXF×0.4")
        c2.metric("外資 選擇權 delta（小台）",
                  f"{safe_float(last['options_delta_mtx']):+,.0f}",
                  help="(BC+SP−SC−BP)×4")
        c3.metric("外資 合計 delta（小台）",
                  f"{safe_float(last['total_delta_mtx']):+,.0f}",
                  delta=f"期選{'同向' if safe_float(last['futures_delta_mtx']) * safe_float(last['options_delta_mtx']) >= 0 else '方向相反'}",
                  help="期貨與選擇權合計 delta，正值代表多方口數較多（歷史統計，不代表未來走勢）")

    # chart: 外資 vs 散戶 total delta trend
    fig = go.Figure()
    if not ext_df.empty:
        fig.add_trace(go.Scatter(
            x=ext_df["trade_date"], y=ext_df["total_delta_mtx"].astype(float),
            name="外資合計 delta", line=dict(color="#2196F3", width=2),
            fill="tozeroy", fillcolor="rgba(33,150,243,0.08)",
            hovertemplate="%{x}<br>外資: %{y:+,.0f} 口<extra></extra>",
        ))
    if not ret_df.empty:
        fig.add_trace(go.Scatter(
            x=ret_df["trade_date"], y=ret_df["total_delta_mtx"].astype(float),
            name="散戶合計 delta", line=dict(color="#4CAF50", width=2, dash="dot"),
            hovertemplate="%{x}<br>散戶: %{y:+,.0f} 口<extra></extra>",
        ))
    fig.add_hline(y=0, line_color="gray", line_dash="dash", line_width=1)
    fig.update_layout(
        title="外資 vs 散戶 合計 Delta 趨勢（折算小台口數）",
        yaxis_title="小台口數（正=多方）", height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    # stacked: 期貨 delta vs 選擇權 delta for 外資
    if not ext_df.empty:
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=ext_df["trade_date"], y=ext_df["futures_delta_mtx"].astype(float),
            name="期貨 delta", marker_color="#1565C0",
            hovertemplate="%{x}<br>期貨: %{y:+,.0f}<extra></extra>",
        ))
        fig2.add_trace(go.Bar(
            x=ext_df["trade_date"], y=ext_df["options_delta_mtx"].astype(float),
            name="選擇權 delta", marker_color="#FF9800",
            hovertemplate="%{x}<br>選擇權: %{y:+,.0f}<extra></extra>",
        ))
        fig2.update_layout(
            title="外資 期貨 vs 選擇權 Delta 分解（可觀察是否背離）",
            barmode="relative", yaxis_title="小台口數", height=320,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("無市場方向資料")

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# 指標 2：Max Pain 移動方向
# ═══════════════════════════════════════════════════════════════════════════════

st.header("⭐⭐⭐ 指標二：Max Pain 移動方向")

with st.expander("指標說明", expanded=True):
    st.markdown("""
**指標說明：** Max Pain（最大痛苦點）是使全市場選擇權買方整體損失最大化的理論結算價格，
為依據未平倉口數分布計算出的統計數值。
**數據解讀（歷史統計觀察，不保證未來指數走勢）：**
- Max Pain 持續上移 → 理論結算價的統計數值上升
- Max Pain 持續下移 → 理論結算價的統計數值下降
- 現價與 Max Pain 差距較大 → 兩者之間的統計差值較大
- Max Pain 與現價差距縮小 → 兩者數值趨近

本指標為數學計算結果，不代表指數實際走勢，不構成交易建議。
    """)

mp_df = fetch("/market/max-pain", params_range)
if not mp_df.empty:
    mp_df["trade_date"]  = pd.to_datetime(mp_df["trade_date"])
    mp_df = mp_df.sort_values("trade_date")
    mp_df["max_pain_strike"]  = mp_df["max_pain_strike"].astype(float)
    mp_df["underlying_price"] = mp_df["underlying_price"].astype(float)
    mp_df["delta_pts"]        = mp_df["delta_pts"].astype(float)

    last_mp = mp_df.iloc[-1]
    c1, c2, c3 = st.columns(3)
    c1.metric("今日 Max Pain", f"{safe_float(last_mp['max_pain_strike']):,.0f}",
              delta=f"vs 前日 {safe_float(last_mp['max_pain_strike']) - safe_float(mp_df.iloc[-2]['max_pain_strike'] if len(mp_df)>1 else last_mp['max_pain_strike']):+.0f} pts")
    c2.metric("現價（TX 近月）", f"{safe_float(last_mp['underlying_price']):,.0f}")
    delta_v = safe_float(last_mp["delta_pts"])
    c3.metric("Max Pain − 現價", f"{delta_v:+,.0f} pts",
              delta="現價低於Max Pain" if delta_v > 200 else
                    ("現價高於Max Pain" if delta_v < -200 else "現價接近Max Pain"))

    # chart
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=mp_df["trade_date"], y=mp_df["underlying_price"],
        name="TX 收盤價", line=dict(color="#555555", width=2),
        hovertemplate="%{x}<br>現價: %{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=mp_df["trade_date"], y=mp_df["max_pain_strike"],
        name="Max Pain", line=dict(color="#F44336", width=2, dash="dash"),
        hovertemplate="%{x}<br>Max Pain: %{y:,.0f}<extra></extra>",
    ))
    # fill between
    fig.add_trace(go.Scatter(
        x=pd.concat([mp_df["trade_date"], mp_df["trade_date"][::-1]]),
        y=pd.concat([mp_df["max_pain_strike"], mp_df["underlying_price"][::-1]]),
        fill="toself",
        fillcolor="rgba(244,67,54,0.08)",
        line=dict(color="rgba(0,0,0,0)"),
        name="差距區間", showlegend=False,
    ))
    fig.update_layout(
        title="Max Pain vs 現價 趨勢（統計差值，不代表走勢預測）",
        yaxis_title="指數點位", height=360,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    # delta bar
    fig3 = go.Figure(go.Bar(
        x=mp_df["trade_date"],
        y=mp_df["delta_pts"],
        marker_color=["#4CAF50" if v > 0 else "#F44336" for v in mp_df["delta_pts"]],
        hovertemplate="%{x}<br>Max Pain − 現價: %{y:+.0f} pts<extra></extra>",
    ))
    fig3.add_hline(y=0, line_dash="dash", line_color="gray")
    fig3.update_layout(
        title="Max Pain − 現價 差值（正=現價低於Max Pain，負=現價高於Max Pain）",
        yaxis_title="點位差", height=280,
    )
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("無 Max Pain 資料")

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# 指標 3：散戶買 Call 平均成本 vs 現價
# ═══════════════════════════════════════════════════════════════════════════════

st.header("⭐⭐⭐ 指標三：散戶買 Call 平均成本 vs 現價")

with st.expander("指標說明", expanded=True):
    st.markdown("""
**指標說明：** 依未平倉口數加權計算之選擇權平均持倉成本（點數），
反映市場整體持倉的成本分布統計。
**數據解讀（歷史統計觀察，不代表未來走勢）：**
- **全市場 Call 加權均成本** → 所有到期月份 Call 持倉的口數加權平均買入成本統計
- **Put 加權均成本** → Put 持倉的統計成本分布
- **主要觀察近月 W1**（最大 OI 週選）各履約價之持倉成本分布

本指標為統計數值，不構成任何交易建議。
    """)

# fetch strike cost for latest date and most active W contract
strike_df = fetch("/options/strike-cost", {"trade_date": end_date})
fut_latest = fetch("/futures", {"contract": "TX", "start": end_date, "end": end_date, "limit": 10})

underlying_latest = None
if not fut_latest.empty:
    day_rows = fut_latest[
        (fut_latest["contract_month"].astype(str).str.len() == 6) &
        (fut_latest["session"] == "一般")
    ]
    if not day_rows.empty:
        v = day_rows.sort_values("contract_month").iloc[0]["close_price"]
        underlying_latest = float(v) if v else None

if not strike_df.empty:
    strike_df["strike_price"]  = pd.to_numeric(strike_df["strike_price"],  errors="coerce")
    strike_df["avg_cost"]      = pd.to_numeric(strike_df["avg_cost"],      errors="coerce")
    strike_df["open_interest"] = pd.to_numeric(strike_df["open_interest"], errors="coerce").fillna(0)
    strike_df["total_fund"]    = strike_df["avg_cost"] * strike_df["open_interest"]

    # compute market-weighted avg cost per call_put
    call_all = strike_df[strike_df["call_put"] == "C"]
    put_all  = strike_df[strike_df["call_put"] == "P"]

    def weighted_avg(df):
        total_oi = df["open_interest"].sum()
        if total_oi == 0:
            return 0
        return (df["avg_cost"] * df["open_interest"]).sum() / total_oi

    call_wavg = weighted_avg(call_all)
    put_wavg  = weighted_avg(put_all)

    c1, c2, c3 = st.columns(3)
    c1.metric("全市場 Call 加權均成本（點）", f"{call_wavg:,.1f}",
              help="所有到期月份 Call OI 加權平均買入成本")
    c2.metric("全市場 Put 加權均成本（點）", f"{put_wavg:,.1f}",
              help="所有到期月份 Put OI 加權平均買入成本")
    if underlying_latest:
        # 找 ATM strike 的 Call 現價（daily_price）
        atm_calls = call_all[abs(call_all["strike_price"] - underlying_latest) < 500]
        atm_call_price = 0
        if not atm_calls.empty:
            atm_call_price = float(atm_calls.sort_values("open_interest", ascending=False).iloc[0].get("avg_cost", 0))
        c3.metric("TX 現價", f"{underlying_latest:,.0f}",
                  delta=f"ATM Call 均成本: {atm_call_price:,.0f} pts")

    # W1 strike cost bar chart with cost vs market price
    w_months_avail = sorted({m for m in strike_df["contract_month"].unique() if "W" in m})
    if w_months_avail:
        selected_w = st.selectbox("選擇週選到期月份", w_months_avail, key="w_cost")
        w_df = strike_df[strike_df["contract_month"] == selected_w].copy()
        if not w_df.empty and underlying_latest:
            w_df = w_df[abs(w_df["strike_price"] - underlying_latest) <= 2500]
            w_df = w_df.sort_values("strike_price")

            call_w = w_df[w_df["call_put"] == "C"]
            put_w  = w_df[w_df["call_put"] == "P"]

            fig = make_subplots(rows=1, cols=2,
                                subplot_titles=["Call 各履約價均成本 vs OI", "Put 各履約價均成本 vs OI"])
            for col_idx, (sub_df, label, color) in enumerate([
                (call_w, "Call", "#2196F3"),
                (put_w,  "Put",  "#F44336"),
            ], start=1):
                if sub_df.empty:
                    continue
                fig.add_trace(go.Bar(
                    x=sub_df["open_interest"],
                    y=sub_df["strike_price"],
                    orientation="h",
                    name=f"{label} OI",
                    marker_color=color,
                    opacity=0.5,
                    hovertemplate="履約價 %{y}<br>OI: %{x:,}<extra></extra>",
                ), row=1, col=col_idx)
                # avg cost as text annotation on bars
                for _, r in sub_df.iterrows():
                    if r["open_interest"] > 0:
                        fig.add_annotation(
                            x=r["open_interest"] * 1.02,
                            y=r["strike_price"],
                            text=f"{r['avg_cost']:.0f}",
                            showarrow=False, font=dict(size=9, color="#333"),
                            xref=f"x{col_idx if col_idx > 1 else ''}",
                            yref=f"y{col_idx if col_idx > 1 else ''}",
                            row=1, col=col_idx,
                        )
                # ATM line
                fig.add_hline(y=underlying_latest, line_dash="dash",
                               line_color="#FF5722", line_width=1.5,
                               annotation_text=f"現價 {underlying_latest:,.0f}",
                               row=1, col=col_idx)

            fig.update_layout(
                title=f"{selected_w} 各履約價 OI 分布（右側數字=加權均成本，橘線=現價）",
                height=500, showlegend=False,
            )
            fig.update_yaxes(title_text="履約價")
            st.plotly_chart(fig, use_container_width=True)
else:
    st.info("無履約價成本資料")

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# 指標 4：月選 / 週選 OI 比
# ═══════════════════════════════════════════════════════════════════════════════

st.header("⭐⭐ 指標四：週選 / 月選 OI 比")

with st.expander("指標說明", expanded=True):
    st.markdown("""
**指標說明：** 週選（W/F 系列）與月選（標準月選）的未平倉口數比例統計。
**數據解讀（歷史統計觀察，不代表未來走勢）：**
- **週選 OI 比重高（>60%）**：近期市場以短週期合約為主
- **週選 OI 比重低（<40%）**：近期市場以月選等較長週期合約為主
- **週選佔比驟降**：可能為大量週選到期後的自然消化
- **月選 Put OI 增加**：機構持有較多 Put 未平倉口數

本指標為未平倉口數分布統計，不構成任何交易建議。
    """)

ois_df = fetch("/market/oi-structure", params_range)
if not ois_df.empty:
    ois_df["trade_date"] = pd.to_datetime(ois_df["trade_date"])
    ois_df = ois_df.sort_values("trade_date")
    for c in ["weekly_call_oi","weekly_put_oi","monthly_call_oi","monthly_put_oi","weekly_oi_ratio"]:
        ois_df[c] = pd.to_numeric(ois_df[c], errors="coerce").fillna(0)
    ois_df["total_oi"] = ois_df["weekly_call_oi"] + ois_df["weekly_put_oi"] + \
                          ois_df["monthly_call_oi"] + ois_df["monthly_put_oi"]

    last_ois = ois_df.iloc[-1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("週選 OI 比重", f"{safe_float(last_ois['weekly_oi_ratio'])*100:.1f}%")
    c2.metric("週選 Call OI", f"{safe_int(last_ois['weekly_call_oi']):,}")
    c3.metric("週選 Put OI",  f"{safe_int(last_ois['weekly_put_oi']):,}")
    c4.metric("主力到期", str(last_ois.get("weekly_dominant_exp", "-")))

    # stacked area chart
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=ois_df["trade_date"], y=ois_df["weekly_call_oi"],
        name="週選 Call", marker_color="#42A5F5",
        hovertemplate="%{x}<br>週選 Call OI: %{y:,}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=ois_df["trade_date"], y=ois_df["weekly_put_oi"],
        name="週選 Put", marker_color="#90CAF9",
        hovertemplate="%{x}<br>週選 Put OI: %{y:,}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=ois_df["trade_date"], y=ois_df["monthly_call_oi"],
        name="月選 Call", marker_color="#EF5350",
        hovertemplate="%{x}<br>月選 Call OI: %{y:,}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=ois_df["trade_date"], y=ois_df["monthly_put_oi"],
        name="月選 Put", marker_color="#FFCDD2",
        hovertemplate="%{x}<br>月選 Put OI: %{y:,}<extra></extra>",
    ))
    fig.update_layout(
        title="週選 vs 月選 OI 分布（可看方向性佈局比例）",
        barmode="stack", yaxis_title="未平倉口數", height=360,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)

    # weekly ratio trend line
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=ois_df["trade_date"],
        y=ois_df["weekly_oi_ratio"] * 100,
        name="週選 OI 比重%",
        line=dict(color="#FF9800", width=2),
        fill="tozeroy", fillcolor="rgba(255,152,0,0.10)",
        hovertemplate="%{x}<br>週選比重: %{y:.1f}%<extra></extra>",
    ))
    fig2.add_hline(y=60, line_dash="dash", line_color="red", line_width=1,
                    annotation_text="60% 高投機線")
    fig2.add_hline(y=40, line_dash="dash", line_color="green", line_width=1,
                    annotation_text="40% 方向性線")
    fig2.update_layout(
        title="週選 OI 比重趨勢（>60%=短期投機為主，<40%=長期方向部位為主）",
        yaxis_title="%", yaxis_range=[0, 100], height=300,
    )
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("無 OI 結構資料")

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# 指標 5：外資選擇權金額流向
# ═══════════════════════════════════════════════════════════════════════════════

st.header("⭐⭐ 指標五：外資選擇權金額流向（千元）")

with st.expander("指標說明", expanded=True):
    st.markdown("""
**指標說明：** 以交易金額（千元）統計外資各部位的資金流向，
相較口數統計可降低大台／小台契約面額差異的影響。
**數據解讀（歷史統計觀察，不代表未來走勢）：**
- **BC 金額 vs BP 金額** → Call 買方與 Put 買方的金額分布對比
- **SP 金額 vs SC 金額** → Put 賣方與 Call 賣方的金額分布對比
- **買方（BC+BP）vs 賣方（SC+SP）** → 外資選擇權買賣方金額分布比較
- 比較外資 vs 自營商的金額比值 → 各機構法人的資金規模對比

本指標為成交金額統計，不構成任何交易建議。
    """)

inst_df_full = fetch("/institutional/options", params_range)
ret_df_full  = fetch("/retail/options", params_range)

if not inst_df_full.empty:
    inst_df_full["trade_date"] = pd.to_datetime(inst_df_full["trade_date"])
    inst_df_full = inst_df_full.sort_values("trade_date")

    ext_amt = inst_df_full[inst_df_full["institution_type"] == "外資及陸資"].copy()
    dlr_amt = inst_df_full[inst_df_full["institution_type"] == "自營商"].copy()

    amt_cols = ["call_buy_amount","call_sell_amount","put_buy_amount","put_sell_amount"]
    for df in [ext_amt, dlr_amt]:
        for c in amt_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    if not ext_amt.empty:
        last_e = ext_amt.iloc[-1]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("BC 買Call 金額（千元）", f"{safe_int(last_e.get('call_buy_amount')):,}")
        c2.metric("SC 賣Call 金額（千元）", f"{safe_int(last_e.get('call_sell_amount')):,}")
        c3.metric("BP 買Put 金額（千元）",  f"{safe_int(last_e.get('put_buy_amount')):,}")
        c4.metric("SP 賣Put 金額（千元）",  f"{safe_int(last_e.get('put_sell_amount')):,}")

        # net bull amount = BC + SP - SC - BP
        ext_amt["net_bull_amt"] = (
            ext_amt["call_buy_amount"] + ext_amt["put_sell_amount"]
            - ext_amt["call_sell_amount"] - ext_amt["put_buy_amount"]
        )

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=ext_amt["trade_date"], y=ext_amt["call_buy_amount"],
            name="BC 買Call", marker_color="#4CAF50",
        ))
        fig.add_trace(go.Bar(
            x=ext_amt["trade_date"], y=ext_amt["put_sell_amount"],
            name="SP 賣Put", marker_color="#81C784",
        ))
        fig.add_trace(go.Bar(
            x=ext_amt["trade_date"], y=-ext_amt["call_sell_amount"],
            name="SC 賣Call（負）", marker_color="#F44336",
        ))
        fig.add_trace(go.Bar(
            x=ext_amt["trade_date"], y=-ext_amt["put_buy_amount"],
            name="BP 買Put（負）", marker_color="#EF9A9A",
        ))
        fig.add_trace(go.Scatter(
            x=ext_amt["trade_date"], y=ext_amt["net_bull_amt"],
            name="淨多方金額", line=dict(color="#FF9800", width=2),
            hovertemplate="%{x}<br>淨多: %{y:+,} 千元<extra></extra>",
        ))
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(
            title="外資選擇權各部位金額流向（千元，正=多方資金，負=空方資金）",
            barmode="relative", yaxis_title="千元", height=400,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

        # 外資 vs 自營 buy/sell ratio
        if not dlr_amt.empty:
            st.subheader("外資 vs 自營商 買賣方金額比")
            for df, label in [(ext_amt, "外資"), (dlr_amt, "自營商")]:
                df["buy_total"]  = df["call_buy_amount"] + df["put_buy_amount"]
                df["sell_total"] = df["call_sell_amount"] + df["put_sell_amount"]
                df["bs_ratio"]   = df["buy_total"] / df["sell_total"].replace(0, float("nan"))

            fig3 = go.Figure()
            for df, label, color in [
                (ext_amt, "外資 買/賣比", "#2196F3"),
                (dlr_amt, "自營商 買/賣比", "#FF9800"),
            ]:
                if "bs_ratio" in df.columns:
                    fig3.add_trace(go.Scatter(
                        x=df["trade_date"], y=df["bs_ratio"],
                        name=label, line=dict(color=color, width=2),
                        hovertemplate="%{x}<br>" + label + ": %{y:.2f}<extra></extra>",
                    ))
            fig3.add_hline(y=1.0, line_dash="dash", line_color="gray",
                            annotation_text="1.0 買賣平衡")
            fig3.update_layout(
                title="外資/自營商 選擇權買方金額 ÷ 賣方金額（>1=偏買方方向性押注，<1=偏賣方穩定收租）",
                yaxis_title="比值", height=320,
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("無三大法人選擇權金額資料")


# ═══════════════════════════════════════════════════════════════════════════════
# 指標 6：Put/Call Ratio 趨勢
# ═══════════════════════════════════════════════════════════════════════════════

st.header("⭐⭐⭐ 指標六：Put/Call Ratio (PCR) 趨勢")

with st.expander("指標說明", expanded=True):
    st.markdown("""
**指標說明：** Put/Call Ratio 是賣權未平倉量（或成交量）除以買權未平倉量（或成交量）的比值，
為衡量選擇權市場多空情緒的經典統計指標。
**數據解讀（歷史統計觀察，不代表未來走勢）：**
- **PCR > 1.0** → 賣權未平倉 > 買權未平倉，市場避險/保護性賣權需求較高（歷史上常出現於相對低檔，提供支撐的統計觀察）
- **PCR 介於 0.8 ~ 1.0** → 多空情緒相對均衡
- **PCR < 0.8** → 買權未平倉遠大於賣權，市場偏樂觀（歷史上可能出現過熱訊號）

本指標為未平倉口數統計，不構成任何交易建議。
    """)

pcr_df = fetch("/pcr", params_range)
if not pcr_df.empty:
    pcr_df["trade_date"] = pd.to_datetime(pcr_df["trade_date"])
    pcr_df = pcr_df.sort_values("trade_date")

    # 將百分比值轉為比值（TAIFEX 原始值為百分比，例如 85.4 表示 0.854）
    for c in ["pc_oi_ratio", "pc_vol_ratio"]:
        if c in pcr_df.columns:
            pcr_df[c] = pd.to_numeric(pcr_df[c], errors="coerce")
    # 計算比值形式（若原始值為百分比形式則除以 100）
    pcr_df["oi_ratio_val"] = pcr_df["pc_oi_ratio"].apply(
        lambda x: x / 100.0 if pd.notna(x) and x > 5 else x
    )
    pcr_df["vol_ratio_val"] = pcr_df["pc_vol_ratio"].apply(
        lambda x: x / 100.0 if pd.notna(x) and x > 5 else x
    )

    for c in ["call_oi", "put_oi", "call_volume", "put_volume"]:
        if c in pcr_df.columns:
            pcr_df[c] = pd.to_numeric(pcr_df[c], errors="coerce").fillna(0)

    last_pcr = pcr_df.iloc[-1]
    c1, c2, c3, c4 = st.columns(4)
    oi_val = safe_float(last_pcr.get("oi_ratio_val"))
    vol_val = safe_float(last_pcr.get("vol_ratio_val"))
    c1.metric("PCR（未平倉比）", f"{oi_val:.3f}",
              help="Put OI ÷ Call OI")
    c2.metric("PCR（成交量比）", f"{vol_val:.3f}",
              help="Put Volume ÷ Call Volume")
    c3.metric("Put OI", f"{safe_int(last_pcr.get('put_oi')):,}",
              help="賣權未平倉口數")
    c4.metric("Call OI", f"{safe_int(last_pcr.get('call_oi')):,}",
              help="買權未平倉口數")

    # ── PCR 未平倉比趨勢圖 ──────────────────────────────────────────────────
    fig_pcr = go.Figure()
    fig_pcr.add_trace(go.Scatter(
        x=pcr_df["trade_date"], y=pcr_df["oi_ratio_val"],
        name="PCR（未平倉比）",
        line=dict(color="#2196F3", width=2.5),
        fill="tozeroy", fillcolor="rgba(33,150,243,0.08)",
        hovertemplate="%{x}<br>PCR OI: %{y:.3f}<extra></extra>",
    ))
    if pcr_df["vol_ratio_val"].notna().any():
        fig_pcr.add_trace(go.Scatter(
            x=pcr_df["trade_date"], y=pcr_df["vol_ratio_val"],
            name="PCR（成交量比）",
            line=dict(color="#FF9800", width=1.5, dash="dot"),
            hovertemplate="%{x}<br>PCR Vol: %{y:.3f}<extra></extra>",
        ))

    # 關鍵參考線
    fig_pcr.add_hline(y=1.0, line_dash="dash", line_color="#F44336", line_width=1.5,
                       annotation_text="1.0 多空分界",
                       annotation_position="top left")
    fig_pcr.add_hline(y=0.8, line_dash="dot", line_color="#4CAF50", line_width=1,
                       annotation_text="0.8 偏多警戒",
                       annotation_position="bottom left")
    # 背景色帶：PCR > 1.0 區間淡紅、PCR < 0.8 區間淡綠
    fig_pcr.add_hrect(y0=1.0, y1=max(pcr_df["oi_ratio_val"].max() * 1.05, 1.3),
                       fillcolor="rgba(244,67,54,0.06)", line_width=0,
                       annotation_text="避險保護區", annotation_position="top right",
                       annotation_font_color="#F44336", annotation_font_size=10)
    fig_pcr.add_hrect(y0=min(pcr_df["oi_ratio_val"].min() * 0.95, 0.5), y1=0.8,
                       fillcolor="rgba(76,175,80,0.06)", line_width=0,
                       annotation_text="偏多樂觀區", annotation_position="bottom right",
                       annotation_font_color="#4CAF50", annotation_font_size=10)

    fig_pcr.update_layout(
        title="Put/Call Ratio 趨勢（>1.0 避險需求高，<0.8 市場偏樂觀）",
        yaxis_title="PCR 比值", height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
    )
    st.plotly_chart(fig_pcr, use_container_width=True)

    # ── Put / Call 未平倉口數堆疊圖 ────────────────────────────────────────────
    fig_oi = go.Figure()
    fig_oi.add_trace(go.Bar(
        x=pcr_df["trade_date"], y=pcr_df["call_oi"],
        name="Call OI（買權）", marker_color="#2196F3",
        hovertemplate="%{x}<br>Call OI: %{y:,}<extra></extra>",
    ))
    fig_oi.add_trace(go.Bar(
        x=pcr_df["trade_date"], y=pcr_df["put_oi"],
        name="Put OI（賣權）", marker_color="#F44336",
        hovertemplate="%{x}<br>Put OI: %{y:,}<extra></extra>",
    ))
    fig_oi.update_layout(
        title="Put vs Call 未平倉口數對比",
        barmode="group", yaxis_title="未平倉口數", height=340,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_oi, use_container_width=True)
else:
    st.info("無 PCR 資料，請確認 put_call_ratio 資料表已匯入數據。")

st.divider()


# ── 總結儀表板 ────────────────────────────────────────────────────────────────

st.header("綜合指標速覽")

if not dir_df.empty and not mp_df.empty and not ois_df.empty:
    last_dir = dir_df[dir_df["group_type"] == "外資及陸資"].iloc[-1] if not ext_df.empty else None
    last_mp2 = mp_df.iloc[-1]
    last_ois2 = ois_df.iloc[-1]

    signals = []

    st.caption("以下為各項統計數據的當日數值摘要，不構成投資建議。")

    if last_dir is not None:
        td = safe_float(last_dir["total_delta_mtx"])
        if td < -50000:
            signals.append(("📊 外資合計 delta 空方較多", f"{td:+,.0f} 小台（統計值）"))
        elif td > 50000:
            signals.append(("📊 外資合計 delta 多方較多", f"{td:+,.0f} 小台（統計值）"))
        else:
            signals.append(("📊 外資 delta 多空相近", f"{td:+,.0f} 小台（統計值）"))

    dp = safe_float(last_mp2["delta_pts"])
    if dp > 300:
        signals.append(("📊 Max Pain 高於現價", f"差值 {dp:.0f} pts"))
    elif dp < -300:
        signals.append(("📊 Max Pain 低於現價", f"差值 {abs(dp):.0f} pts"))
    else:
        signals.append(("📊 Max Pain 接近現價", f"差值 {dp:+.0f} pts"))

    wr = safe_float(last_ois2["weekly_oi_ratio"]) * 100
    if wr > 65:
        signals.append(("📊 週選占比較高", f"週選占比 {wr:.0f}%"))
    elif wr < 40:
        signals.append(("📊 月選占比較高", f"週選占比 {wr:.0f}%"))
    else:
        signals.append(("📊 週月選比重均衡", f"週選占比 {wr:.0f}%"))

    # PCR 訊號
    if not pcr_df.empty:
        last_pcr_val = safe_float(pcr_df.iloc[-1].get("oi_ratio_val"))
        if last_pcr_val > 1.0:
            signals.append(("📊 PCR 偏高（避險需求）", f"PCR {last_pcr_val:.3f}"))
        elif last_pcr_val < 0.8:
            signals.append(("📊 PCR 偏低（市場樂觀）", f"PCR {last_pcr_val:.3f}"))
        else:
            signals.append(("📊 PCR 中性區間", f"PCR {last_pcr_val:.3f}"))

    sig_cols = st.columns(len(signals[:4]))
    for i, (title, detail) in enumerate(signals[:4]):
        sig_cols[i].info(f"**{title}**\n\n{detail}")

st.divider()

# ─── 結算日 Pinning 歷史分析 ────────────────────────────────────────────────
st.header("🎯 結算日 Pinning 歷史分析")
st.caption(
    "每月第三個星期三為台指月選擇權結算日。本區驗證『台指收盤是否收斂到 Max Pain / 最大 OI 履約價』的交易假說，"
    "提供賣方 pinning 強度的歷史證據。"
)

_sh_col1, _sh_col2 = st.columns([1, 3])
with _sh_col1:
    _lookback = st.selectbox("回溯月數", [6, 12, 18, 24], index=1, key="_sh_lookback")

try:
    _sh_r = requests.get(
        f"{API_URL}/market/settlement-history",
        params={"lookback_months": int(_lookback)},
        timeout=15,
    )
    _sh_r.raise_for_status()
    _sh = _sh_r.json()
except Exception as e:
    _sh = None
    st.warning(f"無法載入結算歷史：{e}")

if _sh and _sh.get("settlements"):
    _ss = _sh["summary"] or {}
    _rows = _sh["settlements"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("樣本數", f"{_ss.get('count', 0)} 次")
    _avg_abs = _ss.get("avg_abs_delta_vs_max_pain")
    c2.metric("平均偏差 |收盤 − Max Pain|", f"{_avg_abs:,.0f} 點" if _avg_abs is not None else "—")
    _avg_pct = _ss.get("avg_abs_pct_vs_max_pain")
    c3.metric("平均偏差 %", f"{_avg_pct:.2f}%" if _avg_pct is not None else "—")
    _hit_2 = _ss.get("hit_within_2pct", 0)
    _cnt = _ss.get("count", 1) or 1
    c4.metric("命中 ±2% 比率", f"{_hit_2}/{_cnt}", f"{_hit_2/_cnt*100:.0f}%")

    _sh_df = pd.DataFrame(_rows)
    _display_cols = [
        "settlement_date", "underlying_close", "max_pain_strike",
        "delta_vs_max_pain", "delta_vs_max_pain_pct",
        "top_call_oi_strike", "top_put_oi_strike",
    ]
    _rename = {
        "settlement_date": "結算日",
        "underlying_close": "台指收盤",
        "max_pain_strike": "Max Pain",
        "delta_vs_max_pain": "偏差點",
        "delta_vs_max_pain_pct": "偏差 %",
        "top_call_oi_strike": "最大 Call OI",
        "top_put_oi_strike": "最大 Put OI",
    }
    _t = _sh_df[_display_cols].rename(columns=_rename).copy()
    for col in ["台指收盤", "Max Pain", "偏差點", "最大 Call OI", "最大 Put OI"]:
        _t[col] = _t[col].apply(lambda v: f"{v:,.0f}" if pd.notnull(v) else "—")
    _t["偏差 %"] = _t["偏差 %"].apply(lambda v: f"{v:+.2f}%" if pd.notnull(v) else "—")
    st.dataframe(_t, hide_index=True, use_container_width=True)

    _plot_df = _sh_df.dropna(subset=["delta_vs_max_pain"]).copy()
    if not _plot_df.empty:
        _colors = ["rgba(102,187,106,0.85)" if d <= 0 else "rgba(239,83,80,0.85)" for d in _plot_df["delta_vs_max_pain"]]
        _fig_sh = go.Figure()
        _fig_sh.add_trace(go.Bar(
            x=_plot_df["settlement_date"],
            y=_plot_df["delta_vs_max_pain"],
            marker=dict(color=_colors),
            name="收盤 − Max Pain",
            hovertemplate="%{x}<br>偏差: %{y:+,.0f} 點<extra></extra>",
        ))
        _fig_sh.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.4)")
        _fig_sh.update_layout(
            title=dict(text="歷次結算偏差（正 = 收盤高於 Max Pain）", font=dict(size=14, color="#E0E0E0")),
            xaxis=dict(title="結算日", color="#E0E0E0", gridcolor="rgba(255,255,255,0.1)"),
            yaxis=dict(title="偏差（點）", color="#E0E0E0", gridcolor="rgba(255,255,255,0.1)", zerolinecolor="rgba(255,255,255,0.3)"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#E0E0E0"),
            height=340,
            margin=dict(l=40, r=10, t=50, b=60),
        )
        st.plotly_chart(_fig_sh, use_container_width=True, key="settlement_history_chart")

    with st.expander("📖 如何解讀此分析？"):
        st.markdown(
            """
            - **Max Pain** 理論認為選擇權賣方（莊家）會把收盤推向讓買方總損失最大（即賣方總獲利最大）的履約價。
            - **平均偏差** 愈小、**命中 ±2% 比率** 愈高，代表 pinning 現象愈強、賣方籌碼掌控力愈大。
            - **最大 Call OI / Put OI** 是另一種 pinning 觀察指標：近月合約最多未平倉口數的履約價，往往形成結算日的磁吸或防守點。
            - 本分析僅以歷史收盤價比對，不含結算價（結算採開盤 SQ 競價）。
            """
        )
else:
    st.info("目前樣本數不足，等更多結算日資料累積後此區會顯示分析結果。")

st.divider()

# ── Calendar Spread（跨期價差） ───────────────────────────────────────────────
st.subheader("📐 跨期價差（Calendar Spread）— 近月 vs 次月")
st.caption("近月與次月 TX 期貨收盤價差；負值 = contango（次月高於近月，多頭結構），正值 = backwardation（近月高於次月，空頭/事件壓力）")

try:
    _cs_resp = requests.get(f"{API_URL}/market/calendar-spread", params={"days": 30}, timeout=15)
    _cs_resp.raise_for_status()
    _cs_data = _cs_resp.json()
except Exception as e:
    st.error(f"跨期價差 API 錯誤：{e}")
    _cs_data = {}

_cs_series = _cs_data.get("series") or []
_cs_stats = _cs_data.get("stats") or {}

if _cs_series and _cs_stats:
    _k1, _k2, _k3, _k4 = st.columns(4)
    _latest = _cs_stats.get("latest_spread") or 0
    _state = _cs_stats.get("state") or "—"
    _z = _cs_stats.get("z_score") or 0
    _mean = _cs_stats.get("mean") or 0
    _state_label = {"contango": "Contango（次月高）", "backwardation": "Backwardation（近月高）", "flat": "平水"}.get(_state, _state)
    _k1.metric("最新 spread", f"{_latest:+.0f} 點")
    _k2.metric("結構狀態", _state_label)
    _k3.metric("30 日 z-score", f"{_z:+.2f}")
    _k4.metric("30 日均值", f"{_mean:+.1f} 點")

    _df_cs = pd.DataFrame(_cs_series)
    _df_cs["trade_date"] = pd.to_datetime(_df_cs["trade_date"])

    _fig_cs = make_subplots(specs=[[{"secondary_y": True}]])
    _fig_cs.add_trace(
        go.Scatter(x=_df_cs["trade_date"], y=_df_cs["near_close"], name="近月收盤",
                   line=dict(color="#4FC3F7", width=2),
                   hovertemplate="%{x|%Y-%m-%d}<br>近月 %{y:,.0f}<extra></extra>"),
        secondary_y=False,
    )
    _fig_cs.add_trace(
        go.Scatter(x=_df_cs["trade_date"], y=_df_cs["next_close"], name="次月收盤",
                   line=dict(color="#BA68C8", width=2, dash="dot"),
                   hovertemplate="%{x|%Y-%m-%d}<br>次月 %{y:,.0f}<extra></extra>"),
        secondary_y=False,
    )
    _spread_colors = ["#EF5350" if v > 0 else "#66BB6A" for v in _df_cs["spread"]]
    _fig_cs.add_trace(
        go.Bar(x=_df_cs["trade_date"], y=_df_cs["spread"], name="Spread（近-次）",
               marker_color=_spread_colors, opacity=0.55,
               hovertemplate="%{x|%Y-%m-%d}<br>spread %{y:+,.0f} 點<extra></extra>"),
        secondary_y=True,
    )
    _fig_cs.update_layout(
        title=dict(text="30 日跨期價差", font=dict(size=14, color="#E0E0E0")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E0E0E0"),
        height=380,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08),
        margin=dict(l=40, r=40, t=50, b=40),
        barmode="relative",
    )
    _fig_cs.update_xaxes(title="交易日", color="#E0E0E0", gridcolor="rgba(255,255,255,0.1)")
    _fig_cs.update_yaxes(title="收盤價（點）", secondary_y=False, color="#E0E0E0", gridcolor="rgba(255,255,255,0.1)")
    _fig_cs.update_yaxes(title="Spread（點）", secondary_y=True, color="#E0E0E0", zerolinecolor="rgba(255,255,255,0.3)", showgrid=False)

    st.plotly_chart(_fig_cs, use_container_width=True, key="calendar_spread_chart")

    with st.expander("📖 如何解讀跨期價差？"):
        st.markdown(
            """
            - **Contango（spread < 0，次月高於近月）**：常見於多頭、市場平靜期；反映持有遠月的溢價。
            - **Backwardation（spread > 0，近月高於次月）**：常伴隨結算日壓力、重大事件或空頭情緒；需留意波動放大風險。
            - **z-score**：標準化後的異常值指標，|z| > 2 代表偏離 30 日均值超過 2 個標準差，值得關注。
            - 注意：結算前 3-5 交易日近月合約會因 roll（換倉）造成 spread 扭曲，屬正常現象。
            """
        )
else:
    st.info("跨期價差資料不足（需至少兩個近月合約同時有成交），等 TAIFEX 次月合約流動性累積後顯示。")

st.divider()

# ── 法人 net_oi vs 指數 背離偵測 ───────────────────────────────────────────────
st.subheader("🔀 法人 Delta 趨勢 — 外資 vs 指數 背離偵測")
st.caption("外資 / 投信 / 自營商 臺股期貨淨未平倉 (net_oi) 30 日時序；與近月 TX 收盤對比，偵測前後 5 日平均走勢的方向背離")

try:
    _div_resp = requests.get(f"{API_URL}/market/institutional-divergence", params={"days": 30}, timeout=15)
    _div_resp.raise_for_status()
    _div_data = _div_resp.json()
except Exception as e:
    st.error(f"法人背離 API 錯誤：{e}")
    _div_data = {}

_div_series = _div_data.get("series") or []
_div_info = _div_data.get("divergence") or {}

if _div_series and _div_info:
    _state_map = {
        "bearish": ("⚠️ 負背離（派發）", "#EF5350"),
        "bullish": ("🟢 正背離（接盤）", "#66BB6A"),
        "neutral": ("—", "#888"),
        "insufficient_data": ("資料不足", "#888"),
    }
    _kc1, _kc2, _kc3 = st.columns(3)
    for _col, _key, _label in [(_kc1, "foreign", "外資"), (_kc2, "trust", "投信"), (_kc3, "dealer", "自營商")]:
        _info = _div_info.get(_key) or {}
        _state = _info.get("state", "neutral")
        _lbl, _clr = _state_map.get(_state, ("—", "#888"))
        _delta_inst = _info.get("inst_delta") or 0
        _col.markdown(
            f"""
            <div style="padding:12px;border-radius:8px;background:rgba(255,255,255,0.03);border-left:4px solid {_clr}">
              <div style="color:#888;font-size:12px">{_label} 背離狀態</div>
              <div style="color:{_clr};font-size:16px;font-weight:600;margin:4px 0">{_lbl}</div>
              <div style="color:#E0E0E0;font-size:12px">淨部位變化：{_delta_inst:+,.0f} 口</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    _df_d = pd.DataFrame(_div_series)
    _df_d["trade_date"] = pd.to_datetime(_df_d["trade_date"])

    _fig_d = make_subplots(specs=[[{"secondary_y": True}]])
    _fig_d.add_trace(
        go.Scatter(x=_df_d["trade_date"], y=_df_d["index_close"], name="近月 TX 收盤",
                   line=dict(color="#FFD54F", width=2),
                   hovertemplate="%{x|%Y-%m-%d}<br>指數 %{y:,.0f}<extra></extra>"),
        secondary_y=False,
    )
    _fig_d.add_trace(
        go.Scatter(x=_df_d["trade_date"], y=_df_d["foreign_net_oi"], name="外資 net_oi",
                   line=dict(color="#4FC3F7", width=2),
                   hovertemplate="%{x|%Y-%m-%d}<br>外資 %{y:+,.0f}<extra></extra>"),
        secondary_y=True,
    )
    _fig_d.add_trace(
        go.Scatter(x=_df_d["trade_date"], y=_df_d["trust_net_oi"], name="投信 net_oi",
                   line=dict(color="#BA68C8", width=1.5, dash="dot"),
                   hovertemplate="%{x|%Y-%m-%d}<br>投信 %{y:+,.0f}<extra></extra>"),
        secondary_y=True,
    )
    _fig_d.add_trace(
        go.Scatter(x=_df_d["trade_date"], y=_df_d["dealer_net_oi"], name="自營商 net_oi",
                   line=dict(color="#66BB6A", width=1.5, dash="dash"),
                   hovertemplate="%{x|%Y-%m-%d}<br>自營 %{y:+,.0f}<extra></extra>"),
        secondary_y=True,
    )
    _fig_d.update_layout(
        title=dict(text="30 日指數 vs 三大法人淨未平倉", font=dict(size=14, color="#E0E0E0")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E0E0E0"),
        height=400,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08),
        margin=dict(l=40, r=40, t=50, b=40),
    )
    _fig_d.update_xaxes(title="交易日", color="#E0E0E0", gridcolor="rgba(255,255,255,0.1)")
    _fig_d.update_yaxes(title="近月 TX 收盤（點）", secondary_y=False, color="#FFD54F", gridcolor="rgba(255,255,255,0.1)")
    _fig_d.update_yaxes(title="法人 net_oi（口）", secondary_y=True, color="#E0E0E0", zerolinecolor="rgba(255,255,255,0.3)", showgrid=False)

    st.plotly_chart(_fig_d, use_container_width=True, key="inst_divergence_chart")

    with st.expander("📖 如何解讀法人背離？"):
        st.markdown(
            """
            - **負背離（bearish）**：指數近 5 日均值 > 前 5 日均值，但法人 net_oi 反而下降 → 上漲是散戶/程式盤推動，法人在派發，常預示反轉。
            - **正背離（bullish）**：指數下跌但法人 net_oi 增加 → 法人在接盤，常是底部訊號。
            - **注意**：此為方向性警示，非 100% 準確；外資資金流是最重要但非唯一訊號，需搭配 put/call ratio、結算日位置共同判讀。
            - **資料來源**：臺股期貨（大台）三大法人每日淨未平倉；指數以近月 TX 收盤為 proxy。
            """
        )
else:
    st.info("法人背離資料不足，需至少 10 個交易日的完整資料。")

st.divider()

# ── 大額交易人動向（特定法人前 5/10 大戶） ────────────────────────────────────
st.subheader("🐋 大額交易人動向 — 特定法人（前 5/10 大戶）")
st.caption("TAIFEX 公布的「大額交易人」資料（前 5/10 大戶部位），顆粒度比三大法人週報更細；特定法人 = 當日最大倉位的 5-10 家機構合計")

try:
    _lt_resp = requests.get(f"{API_URL}/market/large-trader-watch", params={"days": 7}, timeout=15)
    _lt_resp.raise_for_status()
    _lt_data = _lt_resp.json()
except Exception as e:
    st.error(f"大戶動向 API 錯誤：{e}")
    _lt_data = {}

_lt_series = _lt_data.get("series") or []
_lt_stats = _lt_data.get("stats") or {}
_near_month = _lt_data.get("near_month") or "—"

if _lt_series and _lt_stats:
    _lean_map = {
        "bearish_hedge": ("⚠️ 避險/看空", "#EF5350", "買 Put 賣 Call"),
        "bullish": ("🟢 看多", "#66BB6A", "買 Call 賣 Put"),
        "long_vol": ("🟡 做多波動", "#FFB74D", "買 Call 買 Put"),
        "short_vol": ("🔵 做空波動", "#4FC3F7", "賣 Call 賣 Put"),
        "neutral": ("—", "#888", "方向模糊"),
    }
    _lean = _lt_stats.get("options_lean", "neutral")
    _lean_lbl, _lean_clr, _lean_desc = _lean_map.get(_lean, ("—", "#888", ""))

    _lt_cols = st.columns(4)
    _tx_net = _lt_stats.get("tx_specific_net") or 0
    _call_net = _lt_stats.get("txo_call_specific_net") or 0
    _put_net = _lt_stats.get("txo_put_specific_net") or 0
    _lt_cols[0].metric("TX 近月特定法人 net", f"{_tx_net:+,.0f} 口",
                       delta_color="normal" if _tx_net >= 0 else "inverse",
                       help=f"近月 {_near_month}，長倉 - 短倉")
    _lt_cols[1].metric("TXO 買權特定法人 net", f"{_call_net:+,.0f} 口",
                       delta_color="normal" if _call_net >= 0 else "inverse",
                       help="Call long - short；負值 = 大戶淨賣 Call")
    _lt_cols[2].metric("TXO 賣權特定法人 net", f"{_put_net:+,.0f} 口",
                       delta_color="normal" if _put_net >= 0 else "inverse",
                       help="Put long - short；正值 = 大戶淨買 Put（避險）")
    _lt_cols[3].markdown(
        f"""
        <div style="padding:12px;border-radius:8px;background:rgba(255,255,255,0.03);border-left:4px solid {_lean_clr}">
          <div style="color:#888;font-size:12px">期權大戶傾向</div>
          <div style="color:{_lean_clr};font-size:15px;font-weight:600;margin:4px 0">{_lean_lbl}</div>
          <div style="color:#aaa;font-size:11px">{_lean_desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _df_lt = pd.DataFrame(_lt_series)
    _df_lt["trade_date"] = pd.to_datetime(_df_lt["trade_date"])

    _fig_lt = make_subplots(specs=[[{"secondary_y": True}]])
    _fig_lt.add_trace(
        go.Bar(x=_df_lt["trade_date"], y=_df_lt.get("tx_specific_net"), name="TX 特定法人 net",
               marker_color="#FFD54F", opacity=0.7,
               hovertemplate="%{x|%Y-%m-%d}<br>TX net %{y:+,.0f} 口<extra></extra>"),
        secondary_y=False,
    )
    _fig_lt.add_trace(
        go.Scatter(x=_df_lt["trade_date"], y=_df_lt.get("txo_call_specific_net"), name="TXO Call net（特定）",
                   line=dict(color="#4FC3F7", width=2),
                   hovertemplate="%{x|%Y-%m-%d}<br>Call net %{y:+,.0f}<extra></extra>"),
        secondary_y=True,
    )
    _fig_lt.add_trace(
        go.Scatter(x=_df_lt["trade_date"], y=_df_lt.get("txo_put_specific_net"), name="TXO Put net（特定）",
                   line=dict(color="#BA68C8", width=2, dash="dot"),
                   hovertemplate="%{x|%Y-%m-%d}<br>Put net %{y:+,.0f}<extra></extra>"),
        secondary_y=True,
    )
    _fig_lt.update_layout(
        title=dict(text=f"7 日特定法人 net — 近月 {_near_month}", font=dict(size=14, color="#E0E0E0")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E0E0E0"),
        height=380,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08),
        margin=dict(l=40, r=40, t=50, b=40),
    )
    _fig_lt.update_xaxes(title="交易日", color="#E0E0E0", gridcolor="rgba(255,255,255,0.1)")
    _fig_lt.update_yaxes(title="TX 期貨 net（口）", secondary_y=False, color="#FFD54F", gridcolor="rgba(255,255,255,0.1)")
    _fig_lt.update_yaxes(title="TXO 選擇權 net（口）", secondary_y=True, color="#E0E0E0", zerolinecolor="rgba(255,255,255,0.3)", showgrid=False)

    st.plotly_chart(_fig_lt, use_container_width=True, key="large_trader_chart")

    with st.expander("📖 如何解讀大額交易人動向？"):
        st.markdown(
            """
            - **特定法人**：當日未平倉量前 5 大（TX）/前 10 大（TXO）交易人的合計，通常是外資大機構或造市商，精明度高於一般散戶。
            - **TX 近月 net > 0**：大戶淨多；net < 0：大戶淨空。可與三大法人淨部位互相印證。
            - **TXO 期權傾向組合**：
              - **避險/看空**（買 Put 賣 Call）：期貨多頭可能搭配 Put 避險，或直接看空。
              - **看多**（買 Call 賣 Put）：積極看多的明確訊號。
              - **做多波動**（買 Call 買 Put）：預期大事件/結算行情。
              - **做空波動**（賣 Call 賣 Put）：預期盤整，賺時間價值。
            - **注意**：特定法人 ≠ 外資，可能是本土券商自營、外資自營或做市商；組合型交易（跨式、價差）無法從 net 判斷。
            """
        )
else:
    st.info("大額交易人資料尚未載入或近月合約無部位。")

st.divider()
st.caption("資料來源：台灣期貨交易所（TAIFEX）公開資訊  |  本頁所有內容僅供資料呈現與學術研究，不構成投資建議。期貨交易涉及高度風險，請自行評估並諮詢合格期貨顧問。")
