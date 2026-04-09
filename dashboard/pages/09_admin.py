"""
管理員後台 — 僅限 ohmygot65@yahoo.com.tw
"""
import os
import streamlit as st
import requests as _requests
from auth import auth_sidebar, is_logged_in

st.set_page_config(page_title="管理後台", page_icon="🔧", layout="wide")
auth_sidebar()

ADMIN_EMAIL = "ohmygot65@yahoo.com.tw"
API_URL = os.getenv("API_URL", "http://localhost:8000")

# ── 權限檢查 ──────────────────────────────────────────────────────────────────

if not is_logged_in():
    st.error("請先登入")
    st.stop()

if st.session_state.get("email", "").lower() != ADMIN_EMAIL:
    st.error("此頁面僅限管理員使用")
    st.stop()

# ── 頁面內容 ──────────────────────────────────────────────────────────────────

st.title("🔧 管理後台")

token = st.session_state.get("token", "")
headers = {"Authorization": f"Bearer {token}"}


def _api(method, endpoint, **kwargs):
    try:
        r = getattr(_requests, method)(f"{API_URL}{endpoint}", headers=headers, timeout=20, **kwargs)
        if r.ok:
            return r.json(), None
        return None, r.json().get("detail", r.text)
    except Exception as e:
        return None, str(e)


# ── 訂閱同步區塊 ─────────────────────────────────────────────────────────────

st.subheader("訂閱狀態同步")
st.caption("掃描所有 paid 訂單，補建或修正不一致的訂閱記錄與會員等級")

col_btn, col_msg = st.columns([1, 3])
with col_btn:
    sync_clicked = st.button("手動同步訂閱", type="primary", use_container_width=True)

if sync_clicked:
    with st.spinner("同步中..."):
        data, err = _api("post", "/payment/admin/sync-subscriptions")
    if err:
        st.error(f"同步失敗：{err}")
    else:
        if data["fixed"] == 0:
            st.success(f"✅ {data['message']}，全部正常，無需修正")
        else:
            st.warning(f"⚠️ {data['message']}")
            fix_rows = data.get("fixed_list", [])
            if fix_rows:
                st.markdown("**已修正的用戶：**")
                for r in fix_rows:
                    st.markdown(
                        f"- **{r['display_name']}** (`{r['user_id'][:8]}...`) "
                        f"→ `{r['plan']}` 到期：`{r['expires'][:10]}` ｜ 原因：{r['reason']}"
                    )

st.divider()

# ── 付款與訂閱總覽 ────────────────────────────────────────────────────────────

st.subheader("付款與訂閱總覽")

refresh = st.button("重新載入", key="_refresh")

if "admin_rows" not in st.session_state or refresh:
    with st.spinner("載入中..."):
        data, err = _api("get", "/payment/admin/overview")
    if err:
        st.error(f"載入失敗：{err}")
        st.stop()
    st.session_state["admin_rows"] = data.get("rows", [])

rows = st.session_state.get("admin_rows", [])

if not rows:
    st.info("目前沒有任何付款記錄")
    st.stop()

# ── 統計摘要 ──────────────────────────────────────────────────────────────────

paid_rows  = [r for r in rows if r["order_status"] == "paid"]
total_amt  = sum(r["order_amount"] for r in paid_rows)
pro_count  = sum(1 for r in paid_rows if r["order_plan"] == "pro")
ult_count  = sum(1 for r in paid_rows if r["order_plan"] == "ultimate")

c1, c2, c3, c4 = st.columns(4)
c1.metric("付款成功筆數", len(paid_rows))
c2.metric("進階版訂單", pro_count)
c3.metric("終極版訂單", ult_count)
c4.metric("總收款 (TWD)", f"${total_amt:,}")

st.divider()

# ── 篩選 ──────────────────────────────────────────────────────────────────────

filter_status = st.selectbox(
    "篩選訂單狀態",
    ["全部", "paid", "pending", "failed", "cancelled"],
    key="_filter_status",
)

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
