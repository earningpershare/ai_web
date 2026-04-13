"""
選擇權資金地圖 — T字報價 + 群體持倉分析
"""

import os
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

show_f_overlay = st.sidebar.checkbox("疊加 F 選（× 0.25 口等效）", value=True)
atm_window = st.sidebar.slider("ATM 顯示範圍（±點）", 500, 5000, 2000, step=250)

st.sidebar.caption(f"今日: {selected_date}　前日: {prev_date}")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: T字報價資金地圖
# ═══════════════════════════════════════════════════════════════════════════════

st.header("一、選擇權資金地圖（T字報價）")

cost_df = fetch("/options/strike-cost", {"trade_date": selected_date, "contract_month": selected_month})
fut_df  = fetch("/futures", {"contract": "TX", "start": selected_date, "end": selected_date, "limit": 20})

underlying = None
if not fut_df.empty and "close_price" in fut_df.columns:
    day_rows = fut_df[
        (fut_df["contract_month"].astype(str).str.len() == 6) &
        (fut_df["session"] == "一般")
    ]
    if not day_rows.empty:
        v = day_rows.sort_values("contract_month").iloc[0]["close_price"]
        underlying = float(v) if v else None

if underlying:
    st.metric("近月 TX 收盤（underlying）", f"{underlying:,.0f}")

if cost_df.empty:
    st.info("此日期無履約價成本資料")
else:
    for col in ["strike_price","avg_cost","open_interest","delta_oi","daily_price"]:
        cost_df[col] = pd.to_numeric(cost_df[col], errors="coerce").fillna(0)
    cost_df["total_fund"]   = cost_df["avg_cost"] * cost_df["open_interest"]
    cost_df["new_fund"]     = cost_df["daily_price"] * cost_df["delta_oi"].clip(lower=0)
    cost_df["new_fund_pct"] = (
        cost_df["new_fund"] / cost_df["total_fund"].replace(0, float("nan"))
    ).fillna(0)
    cost_df["source"] = "W"

    # optionally overlay F contracts
    cost_df_plot = cost_df.copy()
    if show_f_overlay and f_months:
        f_frames = []
        for fm in f_months:
            fd = fetch("/options/strike-cost", {"trade_date": selected_date, "contract_month": fm})
            if not fd.empty:
                f_frames.append(fd)
        if f_frames:
            f_all = pd.concat(f_frames, ignore_index=True)
            for col in ["strike_price","avg_cost","open_interest","delta_oi","daily_price"]:
                f_all[col] = pd.to_numeric(f_all[col], errors="coerce").fillna(0)
            f_agg = f_all.groupby(["strike_price","call_put"], as_index=False).agg(
                avg_cost=("avg_cost","mean"),
                open_interest=("open_interest","sum"),
                delta_oi=("delta_oi","sum"),
                daily_price=("daily_price","mean"),
            )
            f_agg["total_fund"] = f_agg["avg_cost"] * f_agg["open_interest"] * 0.25
            f_agg["new_fund"]   = f_agg["daily_price"] * f_agg["delta_oi"].clip(lower=0) * 0.25
            f_agg["new_fund_pct"] = 0.0
            f_agg["source"] = "F"
            merged = pd.concat([cost_df, f_agg], ignore_index=True)
            cost_df_plot = merged.groupby(["strike_price","call_put"], as_index=False).agg(
                total_fund=("total_fund","sum"),
                new_fund=("new_fund","sum"),
                open_interest=("open_interest","sum"),
                avg_cost=("avg_cost","mean"),
                delta_oi=("delta_oi","sum"),
            )
            cost_df_plot["new_fund_pct"] = (
                cost_df_plot["new_fund"] / cost_df_plot["total_fund"].replace(0, float("nan"))
            ).fillna(0)

    call_df = cost_df_plot[cost_df_plot["call_put"] == "C"].set_index("strike_price")
    put_df  = cost_df_plot[cost_df_plot["call_put"] == "P"].set_index("strike_price")
    all_strikes = sorted(set(call_df.index) | set(put_df.index))
    if underlying:
        all_strikes = [s for s in all_strikes if abs(s - underlying) <= atm_window]

    max_cf = call_df["total_fund"].max() if not call_df.empty else 1
    max_pf = put_df["total_fund"].max()  if not put_df.empty  else 1

    top_c_fund = int(call_df["total_fund"].idxmax()) if not call_df.empty else None
    top_p_fund = int(put_df["total_fund"].idxmax())  if not put_df.empty  else None
    top_c_new  = int(call_df["new_fund"].idxmax())   if not call_df.empty else None
    top_p_new  = int(put_df["new_fund"].idxmax())    if not put_df.empty  else None

    def fund_bg(fund, max_fund, new_pct):
        if max_fund == 0:
            return "#FFFFFF"
        ratio = min(fund / max_fund, 1.0)
        if new_pct > 0.30:
            r = 255; g = int(255 - 155*ratio); b = int(255 - 220*ratio)
        else:
            r = int(255 - 90*ratio); g = int(255 - 90*ratio); b = 255
        return f"#{r:02X}{g:02X}{b:02X}"

    rows_html = []
    for sp in reversed(all_strikes):
        c = call_df.loc[sp]   if sp in call_df.index else None
        p = put_df.loc[sp]    if sp in put_df.index  else None
        atm_tag = ""
        if underlying and abs(sp - underlying) <= 125:
            atm_tag = " <span style='color:#FF5722;font-weight:bold'>◄ATM</span>"

        if c is not None:
            c_bg = fund_bg(c["total_fund"], max_cf, c["new_fund_pct"])
            c_ann = ("★ " if sp == top_c_fund else "") + ("🔥" if sp == top_c_new else "")
            c_td = (f"<td style='background:{c_bg};text-align:right;padding:3px 6px'>"
                    f"<b>{int(c['open_interest']):,}</b>&nbsp;"
                    f"<small style='color:#555'>{c['total_fund']/10000:.1f}萬 {c_ann}</small><br>"
                    f"<small style='color:#888'>新:{c['new_fund']/10000:.1f}萬({c['new_fund_pct']*100:.0f}%)</small>"
                    f"</td>"
                    f"<td style='background:{c_bg};text-align:right;padding:3px 6px;color:#555'>"
                    f"<small>{c['avg_cost']:.0f}</small></td>")
        else:
            c_td = "<td>─</td><td>─</td>"

        if p is not None:
            p_bg = fund_bg(p["total_fund"], max_pf, p["new_fund_pct"])
            p_ann = ("★ " if sp == top_p_fund else "") + ("🔥" if sp == top_p_new else "")
            p_td = (f"<td style='background:{p_bg};text-align:left;padding:3px 6px;color:#555'>"
                    f"<small>{p['avg_cost']:.0f}</small></td>"
                    f"<td style='background:{p_bg};text-align:left;padding:3px 6px'>"
                    f"<b>{int(p['open_interest']):,}</b>&nbsp;"
                    f"<small style='color:#555'>{p['total_fund']/10000:.1f}萬 {p_ann}</small><br>"
                    f"<small style='color:#888'>新:{p['new_fund']/10000:.1f}萬({p['new_fund_pct']*100:.0f}%)</small>"
                    f"</td>")
        else:
            p_td = "<td>─</td><td>─</td>"

        sp_td = f"<td style='text-align:center;font-weight:bold;background:#ECEFF1;padding:3px 6px'>{sp:,.0f}{atm_tag}</td>"
        rows_html.append(f"<tr>{c_td}{sp_td}{p_td}</tr>")

    table_html = f"""
<style>
.tt{{font-size:12px;border-collapse:collapse;width:100%}}
.tt td,.tt th{{border:1px solid #ddd}}
.tt th{{padding:5px 8px;background:#37474F;color:white;text-align:center}}
</style>
<table class='tt'><thead>
<tr><th colspan='2'>◀ CALL 買權</th><th>履約價</th><th colspan='2'>PUT 賣權 ▶</th></tr>
<tr><th>OI / 資金量</th><th>均成本</th><th></th><th>均成本</th><th>OI / 資金量</th></tr>
</thead><tbody>{''.join(rows_html)}</tbody></table>
<p style='font-size:11px;color:#666;margin-top:4px'>
★ 累積最大留倉 &nbsp;|&nbsp; 🔥 今日最多新增 &nbsp;|&nbsp;
<span style='background:#FFD0A0;padding:1px 4px'>■ 橙色 = 今日新增 &gt;30%</span> &nbsp;
<span style='background:#C0C0FF;padding:1px 4px'>■ 藍色 = 舊有留倉</span>
{"&nbsp;|&nbsp; F選已×0.25合併" if show_f_overlay and f_months else ""}
</p>"""
    st.markdown(table_html, unsafe_allow_html=True)

    # monthly reference
    if monthly:
        m_cost = fetch("/options/strike-cost", {"trade_date": selected_date, "contract_month": "202604"})
        if not m_cost.empty:
            m_cost["open_interest"] = pd.to_numeric(m_cost["open_interest"], errors="coerce").fillna(0)
            mc = int(m_cost[m_cost["call_put"]=="C"]["open_interest"].sum())
            mp = int(m_cost[m_cost["call_put"]=="P"]["open_interest"].sum())
            st.info(f"月選 202604（供參考）— Call OI: {mc:,} 口 / Put OI: {mp:,} 口　｜月選部位較大，可作長線方向參考")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: BC / BP / SC / SP 今日變化
# ═══════════════════════════════════════════════════════════════════════════════

st.header("二、各群體 BC / BP / SC / SP 今日變化")

inst_today = fetch("/institutional/options", {"start": selected_date, "end": selected_date})
inst_prev  = fetch("/institutional/options", {"start": prev_date,     "end": prev_date})
ret_today  = fetch("/retail/options",        {"start": selected_date, "end": selected_date})
ret_prev   = fetch("/retail/options",        {"start": prev_date,     "end": prev_date})

KEYS = [
    ("BC 買Call", "call_buy_oi"),
    ("SC 賣Call", "call_sell_oi"),
    ("BP 買Put",  "put_buy_oi"),
    ("SP 賣Put",  "put_sell_oi"),
]

def build_change_df(today_d: dict, prev_d: dict) -> pd.DataFrame:
    rows = []
    for label, key in KEYS:
        t = safe_int(today_d.get(key)); p = safe_int(prev_d.get(key))
        chg = t - p
        pct = chg / p * 100 if p else 0
        rows.append({"操作": label, "今日": t, "昨日": p,
                     "變化": chg, "變化%": pct})
    return pd.DataFrame(rows)

def show_change_table(df: pd.DataFrame, title: str):
    """用純 HTML 渲染，完全避免 pandas Styler 與字串/整數的型別衝突"""
    rows_html = []
    for _, row in df.iterrows():
        chg = int(row["變化"])
        pct = float(row["變化%"])
        bg = "#E8F5E9" if chg > 0 else ("#FFEBEE" if chg < 0 else "#FFFFFF")
        arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "─")
        chg_str = f"{arrow}{abs(chg):,}"
        pct_str = f"{pct:+.1f}%"
        rows_html.append(
            f"<tr style='background:{bg}'>"
            f"<td style='padding:4px 8px'>{row['操作']}</td>"
            f"<td style='padding:4px 8px;text-align:right'>{int(row['今日']):,}</td>"
            f"<td style='padding:4px 8px;text-align:right'>{int(row['昨日']):,}</td>"
            f"<td style='padding:4px 8px;text-align:right;font-weight:bold'>{chg_str}</td>"
            f"<td style='padding:4px 8px;text-align:right'>{pct_str}</td>"
            f"</tr>"
        )
    html = (
        f"<p style='font-size:13px;font-weight:bold;margin:8px 0 2px'>{title}</p>"
        "<table style='font-size:12px;border-collapse:collapse;width:100%'>"
        "<thead><tr style='background:#37474F;color:white'>"
        "<th style='padding:4px 8px'>操作</th>"
        "<th style='padding:4px 8px;text-align:right'>今日</th>"
        "<th style='padding:4px 8px;text-align:right'>昨日</th>"
        "<th style='padding:4px 8px;text-align:right'>變化</th>"
        "<th style='padding:4px 8px;text-align:right'>變化%</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody></table>"
    )
    st.markdown(html, unsafe_allow_html=True)

def get_inst_row(df, inst_type):
    if df.empty or "institution_type" not in df.columns:
        return {}
    sub = df[df["institution_type"]==inst_type]
    return sub.iloc[0].to_dict() if not sub.empty else {}

def agg_inst(df):
    if df.empty:
        return {}
    return {key: safe_int(df[key].sum()) for _, key in KEYS if key in df.columns}

if not inst_today.empty:
    col1, col2 = st.columns(2)

    with col1:
        for inst in ["外資及陸資", "自營商"]:
            t = get_inst_row(inst_today, inst)
            p = get_inst_row(inst_prev,  inst)
            if t:
                show_change_table(build_change_df(t, p), inst)

    with col2:
        if not ret_today.empty:
            t = ret_today.iloc[0].to_dict()
            p = ret_prev.iloc[0].to_dict() if not ret_prev.empty else {}
            show_change_table(build_change_df(t, p), "散戶")

        agg_t = agg_inst(inst_today)
        agg_p = agg_inst(inst_prev)
        if agg_t:
            show_change_table(build_change_df(agg_t, agg_p), "三大法人合計")

    with st.expander("投信（口數極少）"):
        t = get_inst_row(inst_today, "投信")
        p = get_inst_row(inst_prev,  "投信")
        if t:
            show_change_table(build_change_df(t, p), "投信")
else:
    st.info("無三大法人選擇權資料")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: 持倉結構圓餅圖
# ═══════════════════════════════════════════════════════════════════════════════

st.header("三、各群體持倉結構（圓餅圖）")

GROUPS  = ["外資及陸資","投信","自營商","散戶"]
COLORS  = ["#2196F3","#9C27B0","#FF9800","#4CAF50"]

pie_data = {}
if not inst_today.empty:
    for g in ["外資及陸資","投信","自營商"]:
        row = get_inst_row(inst_today, g)
        if row:
            pie_data[g] = {k: safe_int(row.get(key)) for _, key in KEYS for k in [_[:2]]}
            # rebuild cleanly
            pie_data[g] = {lbl[:2]: safe_int(row.get(key)) for lbl, key in KEYS}

if not ret_today.empty:
    r = ret_today.iloc[0]
    pie_data["散戶"] = {lbl[:2]: safe_int(r.get(key)) for lbl, key in KEYS}

if pie_data:
    pie_positions = [
        ("BC 買Call", "BC"),
        ("SC 賣Call", "SC"),
        ("BP 買Put",  "BP"),
        ("SP 賣Put",  "SP"),
    ]
    pie_cols = st.columns(4)
    for i, (title, key) in enumerate(pie_positions):
        labels = [g for g in GROUPS if g in pie_data]
        values = [pie_data[g].get(key, 0) for g in labels]
        if sum(values) == 0:
            continue
        fig = go.Figure(go.Pie(
            labels=labels, values=values,
            marker_colors=COLORS[:len(labels)],
            textinfo="label+percent",
            hovertemplate="%{label}: %{value:,}口<br>%{percent}<extra></extra>",
        ))
        fig.update_layout(title=title, height=300,
                          margin=dict(t=40,b=0,l=0,r=0), showlegend=False)
        with pie_cols[i]:
            st.plotly_chart(fig, use_container_width=True)

    # bar summary
    bar_rows = []
    for g in GROUPS:
        if g not in pie_data:
            continue
        for lbl, _ in KEYS:
            bar_rows.append({"群體": g, "操作": lbl, "口數": pie_data[g].get(lbl[:2], 0)})
    if bar_rows:
        bar_df = pd.DataFrame(bar_rows)
        fig_bar = px.bar(bar_df, x="口數", y="操作", color="群體",
                         orientation="h", barmode="group",
                         color_discrete_map=dict(zip(GROUPS, COLORS)),
                         title="各群體 BC/SC/BP/SP 留倉口數（橫條比較）")
        fig_bar.update_layout(height=380, margin=dict(l=90))
        st.plotly_chart(fig_bar, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: ITM / OTM 分布
# ═══════════════════════════════════════════════════════════════════════════════

st.header("四、ITM / ATM / OTM 未平倉分布")

itm_df = fetch("/market/itm-otm", {
    "start": selected_date - timedelta(days=14),
    "end": selected_date
})

if not itm_df.empty:
    itm_df["trade_date"] = pd.to_datetime(itm_df["trade_date"])
    itm_df = itm_df.sort_values("trade_date")
    today_row = itm_df[itm_df["trade_date"] == pd.Timestamp(selected_date)]

    if not today_row.empty:
        r = today_row.iloc[0]
        col1, col2 = st.columns(2)
        with col1:
            c_vals = [safe_int(r["call_itm_oi"]), safe_int(r["call_atm_oi"]), safe_int(r["call_otm_oi"])]
            fig = go.Figure(go.Bar(
                y=["Call ITM","Call ATM","Call OTM"], x=c_vals, orientation="h",
                marker_color=["#1565C0","#42A5F5","#BBDEFB"],
                text=[f"{v:,}" for v in c_vals], textposition="outside",
            ))
            fig.update_layout(title="Call OI ITM/ATM/OTM", height=260,
                               margin=dict(l=80,r=60,t=40,b=10))
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            p_vals = [safe_int(r["put_itm_oi"]), safe_int(r["put_atm_oi"]), safe_int(r["put_otm_oi"])]
            fig = go.Figure(go.Bar(
                y=["Put ITM","Put ATM","Put OTM"], x=p_vals, orientation="h",
                marker_color=["#B71C1C","#EF5350","#FFCDD2"],
                text=[f"{v:,}" for v in p_vals], textposition="outside",
            ))
            fig.update_layout(title="Put OI ITM/ATM/OTM", height=260,
                               margin=dict(l=80,r=60,t=40,b=10))
            st.plotly_chart(fig, use_container_width=True)

    # ITM ratio trend
    if len(itm_df) > 1:
        for cp in ["call","put"]:
            denom = itm_df[f"{cp}_itm_oi"] + itm_df[f"{cp}_atm_oi"] + itm_df[f"{cp}_otm_oi"]
            itm_df[f"{cp}_itm_ratio"] = (
                itm_df[f"{cp}_itm_oi"] / denom.replace(0, float("nan"))
            )
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=itm_df["trade_date"], y=itm_df["call_itm_ratio"],
                                  name="Call ITM%", line=dict(color="#1565C0")))
        fig.add_trace(go.Scatter(x=itm_df["trade_date"], y=itm_df["put_itm_ratio"],
                                  name="Put ITM%", line=dict(color="#B71C1C")))
        fig.update_layout(title="近期 ITM 比率趨勢", height=280,
                           yaxis_tickformat=".0%", margin=dict(t=40,b=20))
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("無 ITM/OTM 資料")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: 盤勢研判
# ═══════════════════════════════════════════════════════════════════════════════

st.header("五、市場數據觀察指標")

if not inst_today.empty and not ret_today.empty:
    ret_r   = ret_today.iloc[0]
    agg_t   = agg_inst(inst_today)
    ext_r   = get_inst_row(inst_today, "外資及陸資")

    retail_pcr = safe_int(ret_r.get("put_buy_oi")) / max(safe_int(ret_r.get("call_buy_oi")), 1)
    inst_pcr   = safe_int(agg_t.get("put_buy_oi")) / max(safe_int(agg_t.get("call_buy_oi")), 1)

    def net_score(d):
        return (safe_int(d.get("call_buy_oi")) + safe_int(d.get("put_sell_oi"))) - \
               (safe_int(d.get("call_sell_oi")) + safe_int(d.get("put_buy_oi")))

    ext_score    = net_score(ext_r)
    retail_score = net_score(ret_r.to_dict())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("散戶 BP/BC 比值", f"{retail_pcr:.2f}",
              help="比值>1 代表散戶持有 Put 多於 Call；<1 代表 Call 多於 Put（歷史統計觀察，不代表未來走勢）")
    m2.metric("三大法人 BP/BC 比值", f"{inst_pcr:.2f}",
              help="比值>1 代表法人 Put 持倉大於 Call，可能作為避險用途（資料呈現，不構成建議）")
    m3.metric("外資 選擇權淨部位（口）", f"{ext_score:+,}",
              help="BC+SP−SC−BP；正值代表多方部位口數較多（歷史統計，不代表未來）")
    m4.metric("散戶 選擇權淨部位（口）", f"{retail_score:+,}",
              help="散戶整體選擇權持倉方向統計（歷史觀察，不構成操作建議）")

    # Max Pain（從 pipeline 預計算結果讀取）
    mp_today = fetch("/market/max-pain", {"start": selected_date, "end": selected_date, "limit": 1})
    if not mp_today.empty:
        st.subheader("最大痛苦點（Max Pain）")
        mp_r = mp_today.iloc[0]
        mp_val = float(mp_r["max_pain_strike"]) if mp_r["max_pain_strike"] else None
        delta_mp = float(mp_r["delta_pts"]) if mp_r["delta_pts"] else 0
        if mp_val:
            st.metric("最大痛苦點（Max Pain）", f"{mp_val:,.0f}",
                      delta=f"{delta_mp:+.0f} pts 相對現價",
                      help="使全市場選擇權買方損失最大化的理論結算價，為統計計算結果，不保證指數走向此點位")

    # Key OI levels
    st.subheader("OI 資金集中履約價 Top 5（歷史統計）")
    if not cost_df_plot.empty:
        top5 = (cost_df_plot.groupby("strike_price")["total_fund"]
                .sum().reset_index()
                .sort_values("total_fund", ascending=False).head(5))
        for _, r in top5.iterrows():
            sp_ = r["strike_price"]
            tag = ""
            if underlying:
                if abs(sp_ - underlying) <= 125:
                    tag = "⬛ ATM"
                elif sp_ > underlying:
                    tag = "🔴 現價上方"
                else:
                    tag = "🟢 現價下方"
            st.write(f"　**{sp_:,.0f}** {tag} — OI 加權量 {r['total_fund']/1000:.0f}（均成本×口數，相對比較用，非實際金額）")

    # Divergence observation
    st.subheader("群體部位背離觀察（歷史統計參考）")
    st.caption("以下為各群體持倉方向的統計差異，屬數據呈現，不構成任何投資建議或交易推薦。")
    signals = []
    if retail_pcr > 1.2 and inst_pcr < 1.0:
        signals.append("📊 散戶 Put 持倉較多、法人 Call 持倉較多 — 兩者方向出現統計差異（僅供參考）")
    elif retail_pcr < 0.8 and inst_pcr > 1.0:
        signals.append("📊 散戶 Call 持倉較多、法人 Put 持倉較多 — 兩者方向出現統計差異（僅供參考）")
    if retail_score > 0 and ext_score < 0:
        signals.append("📊 散戶淨部位偏多方、外資淨部位偏空方 — 兩者方向相反（歷史統計，不代表未來）")
    elif retail_score < 0 and ext_score > 0:
        signals.append("📊 散戶淨部位偏空方、外資淨部位偏多方 — 兩者方向相反（歷史統計，不代表未來）")
    if not signals:
        signals.append("─ 目前各群體部位方向無明顯統計差異")
    for s in signals:
        st.markdown(s)

else:
    st.info("需有法人與散戶資料才能顯示市場數據觀察指標")

# ─────────────────────────────────────────────────────────────────────────────
st.divider()
st.caption("資料來源：台灣期貨交易所（TAIFEX）公開資訊  |  本頁所有內容僅供資料呈現，不構成投資建議。期貨交易有風險，請自行評估。")
