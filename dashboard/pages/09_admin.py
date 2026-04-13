"""
管理員後台 — 僅限 ohmygot65@yahoo.com.tw
"""
import os
import streamlit as st
import requests as _requests
from auth import auth_sidebar, is_logged_in


filtered = rows if filter_status == "全部" else [r for r in rows if r["order_status"] == filter_status]

# ── 表格 ──────────────────────────────────────────────────────────────────────

STATUS_ICON = {
    "paid": "✅",
    "pending": "⏳",
    "failed": "❌",
    "cancelled": "🚫",
}
SUB_ICON = {
    "active": "🟢",
    "none": "⚪",
    "cancelled": "🔴",
    "expired": "🟡",
}
PLAN_BADGE = {"free": "免費", "pro": "進階版", "ultimate": "終極版", "?": "?"}

for r in filtered:
    order_icon  = STATUS_ICON.get(r["order_status"], "❓")
    sub_icon    = SUB_ICON.get(r["sub_status"], "⚪")
    plan_badge  = PLAN_BADGE.get(r["current_plan"], r["current_plan"])
    paid_at     = r["paid_at"][:10] if r.get("paid_at") else "—"
    expires     = r["sub_expires"][:10] if r.get("sub_expires") else "—"
    started     = r["sub_started"][:10] if r.get("sub_started") else "—"

    # 訂閱 plan 與訂單 plan 不一致時標警告
    mismatch = r["current_plan"] != r["order_plan"] and r["order_status"] == "paid"
    border = "border-left: 4px solid #f5a623;" if mismatch else ""

    st.markdown(
        f"""
        <div style="background:#111;border-radius:8px;padding:12px 16px;margin-bottom:8px;{border}">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
            <div>
              <span style="font-weight:bold;color:#e0e0e0">{r['display_name'] or '(未設名稱)'}</span>
              <span style="color:#666;font-size:12px;margin-left:8px">{r['user_id'][:8]}…</span>
              {"<span style='color:#f5a623;font-size:12px;margin-left:8px'>⚠️ plan 不一致</span>" if mismatch else ""}
            </div>
            <div style="font-size:13px;color:#aaa">
              訂單 {order_icon} <b style="color:#e0e0e0">{r['order_plan']}</b>
              NT${r['order_amount']} ｜ 訂單號 <code style="font-size:11px">{r['order_no']}</code>
            </div>
          </div>
          <div style="display:flex;gap:24px;margin-top:8px;font-size:12px;color:#888;flex-wrap:wrap;">
            <span>付款時間：<b style="color:#ccc">{paid_at}</b></span>
            <span>當前方案：<b style="color:#ccc">{plan_badge}</b></span>
            <span>訂閱 {sub_icon} <b style="color:#ccc">{r['sub_status']}</b></span>
            <span>訂閱起始：<b style="color:#ccc">{started}</b></span>
            <span>訂閱到期：<b style="color:#ccc">{expires}</b></span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
