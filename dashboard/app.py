"""
台指天空 SpaceTFX — 首頁入口
使用 st.navigation() 動態控制頁面清單，確保 admin/tools/shadowrocket
只有管理員登入後才出現在 sidebar。
"""
import os
import requests
import streamlit as st
import streamlit.components.v1 as _components
from auth import (
    auth_sidebar, is_logged_in, has_plan, show_login_modal,
    PLAN_LABEL, _get_saved_token, _set_cookie, _delete_cookie, API_URL,
    _COOKIE_KEY, _COOKIE_MAX_AGE,
)

ADMIN_EMAIL = "ohmygot65@yahoo.com.tw"

st.set_page_config(
    page_title="台指天空 SpaceTFX",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 頂層：消化 dialog 裡留下的 pending cookie 請求 ───────────────────────────
# @st.dialog 內的 components.html 不可靠；改由此處（主流程）執行
if "_pending_set_cookie" in st.session_state:
    _set_cookie(st.session_state.pop("_pending_set_cookie"))

# ── 從 cookie 還原 session（在 navigation 之前執行）──────────────────────────
if not is_logged_in() and not st.session_state.get("_logged_out"):
    restore_token = _get_saved_token()
    if restore_token:
        try:
            r = requests.get(
                f"{API_URL}/auth/me",
                headers={"Authorization": f"Bearer {restore_token}"},
                timeout=10,
            )
            if r.ok:
                data = r.json()
                st.session_state["token"] = restore_token
                st.session_state["email"] = data["email"]
                st.session_state["plan"] = data["plan"]
                st.session_state["email_verified"] = data.get("email_verified", False)
                st.rerun()
            else:
                _delete_cookie()
        except Exception:
            pass

# ── 動態建立頁面清單 ──────────────────────────────────────────────────────────
is_admin = st.session_state.get("email", "").lower() == ADMIN_EMAIL

# 所有人可見的頁面
public_pages = [
    st.Page("_pages/01_market_overview.py", title="市場快照", icon="📊"),
    st.Page("_pages/02_options_map.py",     title="選擇權資金地圖", icon="💹"),
    st.Page("_pages/03_market_analysis.py", title="市場進階分析", icon="🔬"),
    st.Page("_pages/10_research.py",        title="研究報告", icon="📚"),
    st.Page("_pages/11_daily_ops.py",       title="每日操作", icon="📋"),
    st.Page("_pages/05_pricing.py",         title="方案與定價", icon="💎"),
    st.Page("_pages/06_account.py",         title="帳號設定", icon="👤"),
    st.Page("_pages/04_privacy.py",         title="隱私權政策", icon="🔏"),
]

# 只有管理員才看得到
admin_pages = [
    st.Page("_pages/07_tools.py",        title="工具箱", icon="🛠️"),
    st.Page("_pages/08_shadowrocket.py", title="Shadowrocket", icon="🚀"),
    st.Page("_pages/09_admin.py",        title="管理員後台", icon="⚙️"),
] if is_admin else []

pg = st.navigation(public_pages + admin_pages)

# ── Sidebar 登入/登出 UI ──────────────────────────────────────────────────────
with st.sidebar:
    st.divider()
    if is_logged_in():
        from auth import current_plan, PLAN_COLOR
        plan  = current_plan()
        color = PLAN_COLOR.get(plan, "#888")
        label = PLAN_LABEL.get(plan, plan)
        email = st.session_state.get("email", "")
        st.markdown(
            f'<div style="font-size:12px;color:#aaa">{email}</div>'
            f'<div style="font-size:13px;font-weight:bold;color:{color}">● {label}</div>',
            unsafe_allow_html=True,
        )
        if st.button("登出", key="_sidebar_logout", use_container_width=True):
            _delete_cookie()
            for k in ["token", "email", "plan", "email_verified"]:
                st.session_state.pop(k, None)
            st.session_state["_logged_out"] = True
            st.rerun()
    else:
        st.markdown('<div style="font-size:13px;color:#aaa">尚未登入</div>', unsafe_allow_html=True)
        if st.button("登入 / 註冊", key="_sidebar_login", use_container_width=True, type="primary"):
            show_login_modal()

# 從驗證信點擊後 redirect 回首頁（?verified=1），自動清參數並彈出登入框
if st.query_params.get("verified") == "1":
    st.query_params.clear()
    st.toast("✅ 信箱驗證成功！請登入開始使用。", icon="✅")
    if not is_logged_in():
        show_login_modal()

pg.run()
