"""
市場進階分析 — 5 個方向性指標
"""
import os
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import requests

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="市場進階分析", layout="wide")
st.title("市場進階分析")

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

with st.expander("為什麼看這個？", expanded=True):
    st.markdown("""
**指標邏輯：** 外資是台灣期貨市場最大的方向性參與者，其期貨淨 OI + 選擇權淨方向的合計 delta（折算小台口數）
代表外資對大盤方向的真實押注。
**判讀方式：**
- delta 持續往正方向移動 → 外資逐步加碼多方，**偏多訊號**
- delta 持續往負方向移動 → 外資逐步加碼空方，**偏空訊號**
- 短期反轉（從大空翻多）→ 可能為結算前軋空的前兆
- 期貨 delta 與選擇權 delta **背離**時（一多一空）代表外資在用選擇權對沖，方向較不確定
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
                  delta=f"期選{'同向' if safe_float(last['futures_delta_mtx']) * safe_float(last['options_delta_mtx']) >= 0 else '背離⚠️'}",
                  help="合計值越大越偏多")

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

with st.expander("為什麼看這個？", expanded=True):
    st.markdown("""
**指標邏輯：** Max Pain（最大痛苦點）是讓「全市場選擇權買方損失最大」的結算價格，
也就是選擇權賣方（莊家）最希望指數停在的位置。
由於到期前有大量選擇權需要被「歸零」，市場確實有往 Max Pain 靠攏的傾向（尤其結算日前最後兩日）。
**判讀方式：**
- Max Pain **持續上移** → 市場結算壓力往上，偏多
- Max Pain **持續下移** → 市場結算壓力往下，偏空
- 現價 **遠低於** Max Pain → 到期前指數可能反彈回 Max Pain（支撐）
- 現價 **遠高於** Max Pain → 到期前指數可能回落（壓力）
- Max Pain 與現價差距 **縮小中** → 即將到期，結算引力增強
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
              delta="現價低於Max Pain，到期前有反彈引力" if delta_v > 200 else
                    ("現價高於Max Pain，到期前有壓力" if delta_v < -200 else "現價接近Max Pain"))

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
        title="Max Pain vs 現價 趨勢（差距越大結算引力越強）",
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
        title="Max Pain − 現價 差距（正=現價低於Max Pain有支撐，負=現價高於有壓力）",
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

with st.expander("為什麼看這個？", expanded=True):
    st.markdown("""
**指標邏輯：** 散戶（市場多數）的 Call 持倉平均買入成本，反映他們的「損益平衡點」。
當市場買 Call 的平均成本遠高於目前期權市價，代表市場整體 Call 持倉深度虧損，
這些虧損部位在反彈時會形成「解套賣壓（Sell the Rally）」。
**判讀方式：**
- **全市場 Call 加權均成本 > 當日 Call 市價均值** → 大量Call虧損，反彈時賣壓大
- **成本水位下移中** → 新多頭成本較低，上漲空間較輕鬆
- **Put 成本水位 vs 現價** → Put 均成本越高代表市場越害怕、保險費已付出，恐慌情緒可能見頂
- 主要觀察**近月 W1**（最大 OI 週選）的加權均成本分布
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

with st.expander("為什麼看這個？", expanded=True):
    st.markdown("""
**指標邏輯：** 週選（W/F 系列）是短期投機工具，月選（標準月選）是長期方向性工具。
- **週選 OI 比重 高（>60%）**：市場以短期投機為主，波動大，方向不確定，容易被軋
- **週選 OI 比重 低（<40%）**：市場轉向長期方向部位，方向性佈局較強，趨勢較明確
- **週選佔比驟降** → 大量周選到期清倉後，隔週往往出現方向選擇（指數加速）
- **月選 Put OI 大增** → 機構在佈局保護性 Put，對下行有疑慮
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

with st.expander("為什麼看這個？", expanded=True):
    st.markdown("""
**指標邏輯：** 用「交易金額（千元）」而非口數來衡量外資的選擇權投入，
避免大台（TXO）與小台混淆。金額直接反映「真實資金量」。
**判讀方式：**
- **BC 金額 > BP 金額** → 外資把更多錢押注在 Call 買方（多方偏向）
- **SP 金額 > SC 金額** → 外資賣 Put 的資金多（多方偏向，賺 Put 時間價值）
- **買方（BC+BP）金額 >> 賣方（SC+SP）金額** → 外資是方向性押注（買期望值）
- **賣方（SC+SP）金額 >> 買方** → 外資是賣方策略（穩定收租，偏中性或輕微方向）
- 比較外資 vs 散戶的金額比值 → 資金規模懸殊時，外資方向意義更強
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


# ── 總結儀表板 ────────────────────────────────────────────────────────────────

st.divider()
st.header("綜合訊號速覽")

if not dir_df.empty and not mp_df.empty and not ois_df.empty:
    last_dir = dir_df[dir_df["group_type"] == "外資及陸資"].iloc[-1] if not ext_df.empty else None
    last_mp2 = mp_df.iloc[-1]
    last_ois2 = ois_df.iloc[-1]

    signals = []

    if last_dir is not None:
        td = safe_float(last_dir["total_delta_mtx"])
        if td < -50000:
            signals.append(("🔴 外資合計 delta 大空", f"{td:+,.0f} 小台"))
        elif td > 50000:
            signals.append(("🟢 外資合計 delta 大多", f"{td:+,.0f} 小台"))
        else:
            signals.append(("⚪ 外資 delta 中性", f"{td:+,.0f} 小台"))

    dp = safe_float(last_mp2["delta_pts"])
    if dp > 300:
        signals.append(("🟢 Max Pain 高於現價", f"現價低 {dp:.0f} pts，到期前有撐"))
    elif dp < -300:
        signals.append(("🔴 Max Pain 低於現價", f"現價高 {abs(dp):.0f} pts，到期前有壓"))
    else:
        signals.append(("⚪ Max Pain 接近現價", f"差距 {dp:+.0f} pts"))

    wr = safe_float(last_ois2["weekly_oi_ratio"]) * 100
    if wr > 65:
        signals.append(("⚠️ 週選投機濃厚", f"週選占比 {wr:.0f}%，方向判斷難度高"))
    elif wr < 40:
        signals.append(("📌 長期方向部位為主", f"週選占比僅 {wr:.0f}%，趨勢較明確"))
    else:
        signals.append(("⚪ 週選比重正常", f"週選占比 {wr:.0f}%"))

    col1, col2, col3 = st.columns(3)
    for i, (title, detail) in enumerate(signals[:3]):
        [col1, col2, col3][i].info(f"**{title}**\n\n{detail}")
