"""
帳號管理 — 個人資料 / 訂閱狀態 / 取消訂閱 / 登出
"""
import streamlit as st
from auth import auth_sidebar, is_logged_in, show_login_modal, current_plan, _api_get, _api_post_auth, PLAN_LABEL, PLAN_COLOR


@st.experimental_dialog("確認取消訂閱")
def _cancel_confirm_dialog(sub_plan: str, expires: str):
    st.warning(f"確定要取消 **{sub_plan}** 訂閱嗎？")
    st.markdown(
        f"取消後您仍可使用至到期日 **{expires}**，到期後自動降回免費方案。"
        "<br>此操作無法復原，若需繼續訂閱請重新付款。",
        unsafe_allow_html=True,
    )
    col_ok, col_no = st.columns(2)
    with col_ok:
        if st.button("確認取消", key="_cancel_ok", type="primary", use_container_width=True):
            try:
                _api_post_auth("/payment/cancel-subscription")
                st.session_state["_cancel_success"] = True
            except ValueError as e:
                st.session_state["_cancel_error"] = str(e)
            st.rerun()
    with col_no:
        if st.button("保留訂閱", key="_cancel_no", use_container_width=True):
            st.rerun()

auth_sidebar()

st.title("👤 帳號管理")
st.divider()

if not is_logged_in():
    st.markdown(
        """
        <div style="text-align:center;padding:60px 20px;">
          <div style="font-size:52px">🔒</div>
          <h3 style="color:#aaa;margin:16px 0">請先登入</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("登入 / 註冊", key="_acc_login", use_container_width=True, type="primary"):
            show_login_modal()
    st.stop()

# ── 載入個人資料 ──────────────────────────────────────────────────────────────

try:
    me = _api_get("/auth/me")
except ValueError as e:
    st.error(f"無法載入帳號資料：{e}")
    st.stop()

plan = me.get("plan", "free")
color = PLAN_COLOR.get(plan, "#888")
label = PLAN_LABEL.get(plan, plan)
sub = me.get("subscription")

# ── 帳號資訊卡 ────────────────────────────────────────────────────────────────

c1, c2 = st.columns([2, 1])

with c1:
    st.markdown(
        f"""
        <div style="
            background:#111; border:1px solid #222;
            border-radius:10px; padding:24px 28px;
        ">
          <div style="font-size:13px;color:#888;margin-bottom:4px">帳號</div>
          <div style="font-size:18px;color:#e0e0e0;margin-bottom:16px">{me.get('email', '')}</div>

          <div style="font-size:13px;color:#888;margin-bottom:4px">暱稱</div>
          <div style="font-size:16px;color:#e0e0e0;margin-bottom:16px">{me.get('display_name', '')}</div>

          <div style="font-size:13px;color:#888;margin-bottom:4px">目前方案</div>
          <div style="font-size:20px;font-weight:bold;color:{color};margin-bottom:16px">
            ● {label}
          </div>

          <div style="display:flex;gap:32px">
            <div>
              <div style="font-size:12px;color:#888">註冊日期</div>
              <div style="font-size:14px;color:#ccc">{me.get('created_at', '—')}</div>
            </div>
            <div>
              <div style="font-size:12px;color:#888">上次登入</div>
              <div style="font-size:14px;color:#ccc">{me.get('last_login_at', '—') or '—'}</div>
            </div>
            <div>
              <div style="font-size:12px;color:#888">登入次數</div>
              <div style="font-size:14px;color:#ccc">{me.get('login_count', 0)}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:
    # 取消/成功/失敗提示
    if st.session_state.pop("_cancel_success", False):
        st.success("訂閱已取消，可繼續使用至到期日。")
    if err := st.session_state.pop("_cancel_error", None):
        st.error(f"取消失敗：{err}")

    # 訂閱狀態
    if sub:
        expires = str(sub.get("expires_at", ""))[:10] if sub.get("expires_at") else "無到期日"
        sub_plan = PLAN_LABEL.get(sub.get("plan", ""), sub.get("plan", ""))
        status_map = {"active": "有效", "cancelled": "已取消（到期前仍可使用）", "expired": "已到期", "trial": "試用中"}
        sub_status = status_map.get(sub.get("status", ""), sub.get("status", ""))
        st.markdown(
            f"""
            <div style="
                background:#0d1a2e; border:1px solid #1e3a5f;
                border-radius:10px; padding:20px;
            ">
              <div style="font-size:13px;color:#888;margin-bottom:8px">訂閱資訊</div>
              <div style="font-size:15px;color:#4f8ef7;font-weight:bold;margin-bottom:8px">{sub_plan}</div>
              <div style="font-size:12px;color:#888">狀態：<span style="color:#ccc">{sub_status}</span></div>
              <div style="font-size:12px;color:#888;margin-top:4px">到期日：<span style="color:#ccc">{expires}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # 只在 active 狀態才顯示取消按鈕
        if sub.get("status") == "active":
            st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
            if st.button("取消訂閱", key="_cancel_sub_btn", use_container_width=True):
                _cancel_confirm_dialog(sub_plan, expires)
    else:
        st.markdown(
            """
            <div style="
                background:#111; border:1px solid #333;
                border-radius:10px; padding:20px; text-align:center;
            ">
              <div style="font-size:13px;color:#888">目前使用免費方案</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("升級方案", key="_acc_upgrade", use_container_width=True, type="primary"):
            st.switch_page("_pages/05_pricing.py")

st.divider()

# ── 危險操作區 ────────────────────────────────────────────────────────────────

col_a, col_b = st.columns([1, 3])
with col_a:
    if st.button("🚪 登出", key="_logout_btn", use_container_width=True):
        for k in ["token", "email", "plan"]:
            st.session_state.pop(k, None)
        st.success("已登出")
        st.rerun()
