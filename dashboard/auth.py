"""
Auth helper — 供所有 Streamlit 頁面共用

使用方式：
  from auth import require_plan, show_login_modal, auth_sidebar

方案等級：free(0) < pro(1) < ultimate(2)
"""

import os
import streamlit as st
import requests as _requests
import extra_streamlit_components as stx

API_URL = os.getenv("API_URL", "http://localhost:8000")
_COOKIE_KEY = "auth_token"
_COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 天


def _cookie_manager():
    return stx.CookieManager(key="_auth_cookies")

PLAN_RANK = {"free": 0, "pro": 1, "ultimate": 2}
PLAN_LABEL = {"free": "基礎版（免費）", "pro": "進階版", "ultimate": "終極版"}
PLAN_COLOR = {"free": "#888", "pro": "#4f8ef7", "ultimate": "#f5a623"}


# ── API 呼叫 ──────────────────────────────────────────────────────────────────

def _api_post(endpoint: str, body: dict) -> dict:
    r = _requests.post(f"{API_URL}{endpoint}", json=body, timeout=15)
    if not r.ok:
        detail = r.json().get("detail", "未知錯誤") if r.headers.get("content-type", "").startswith("application/json") else r.text
        raise ValueError(detail)
    return r.json()


def _api_get(endpoint: str) -> dict:
    token = st.session_state.get("token", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = _requests.get(f"{API_URL}{endpoint}", headers=headers, timeout=15)
    if not r.ok:
        raise ValueError(r.json().get("detail", "未知錯誤"))
    return r.json()


# ── Session 工具 ──────────────────────────────────────────────────────────────

def _save_session(token: str, email: str, plan: str, email_verified: bool = False):
    st.session_state["token"] = token
    st.session_state["email"] = email
    st.session_state["plan"] = plan
    st.session_state["email_verified"] = email_verified


def is_logged_in() -> bool:
    return bool(st.session_state.get("token"))


def current_plan() -> str:
    return st.session_state.get("plan", "free")


def has_plan(min_plan: str) -> bool:
    return PLAN_RANK.get(current_plan(), 0) >= PLAN_RANK.get(min_plan, 0)


# ── 登入 / 註冊 Modal ─────────────────────────────────────────────────────────

@st.experimental_dialog("登入 / 註冊")
def show_login_modal():
    # ── 剛完成註冊、等待 email 驗證 ──────────────────────────────
    pending_email = st.session_state.get("_verify_email_sent")
    if pending_email:
        st.markdown(
            f"""
            <div style="text-align:center;padding:20px 0 12px;">
              <div style="font-size:48px">✉️</div>
              <h3 style="color:#e0e0e0;margin:12px 0 8px">驗證信已寄出</h3>
              <p style="color:#aaa;font-size:14px;line-height:1.7">
                我們已將驗證連結寄至<br>
                <strong style="color:#4f8ef7">{pending_email}</strong><br>
                請點擊信件中的連結完成驗證，<br>
                驗證後回到此頁面登入即可。
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.info("⚠️ 若未收到信件，請檢查垃圾郵件匣")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("重送驗證信", key="_modal_resend", use_container_width=True):
                _resend_by_email(pending_email)
        with col_b:
            if st.button("前往登入", key="_modal_goto_login", use_container_width=True, type="primary"):
                del st.session_state["_verify_email_sent"]
                st.rerun()
        return

    # ── 正常登入 / 註冊 tabs ──────────────────────────────────────
    tab_login, tab_reg = st.tabs(["登入", "註冊"])

    with tab_login:
        email = st.text_input("Email", key="_login_email")
        password = st.text_input("密碼", type="password", key="_login_pw")

        # 若登入時偵測到未驗證，顯示驗證提示
        if st.session_state.get("_login_need_verify"):
            unverified_email = st.session_state["_login_need_verify"]
            st.warning("⚠️ 此帳號尚未完成信箱驗證，請至信箱點擊驗證連結後再登入。")
            col_r, col_l = st.columns(2)
            with col_r:
                if st.button("重送驗證信", key="_login_resend", use_container_width=True):
                    _resend_by_email(unverified_email)
            with col_l:
                if st.button("我已驗證，重新登入", key="_login_retry", use_container_width=True, type="primary"):
                    st.session_state.pop("_login_need_verify", None)
                    st.rerun()
        elif st.button("登入", key="_btn_login", use_container_width=True, type="primary"):
            if not email or not password:
                st.error("請填寫 Email 和密碼")
            else:
                try:
                    data = _api_post("/auth/login", {"email": email, "password": password})
                    _save_session(data["token"], data["email"], data["plan"],
                                  data.get("email_verified", False))
                    st.session_state.pop("_login_need_verify", None)
                    st.rerun()
                except ValueError as e:
                    err_msg = str(e)
                    if "尚未驗證" in err_msg or "not confirmed" in err_msg.lower():
                        st.session_state["_login_need_verify"] = email
                        st.rerun()
                    else:
                        st.error(err_msg)

    with tab_reg:
        r_email = st.text_input("Email", key="_reg_email")
        r_name = st.text_input("暱稱（選填）", key="_reg_name")
        r_pw = st.text_input("密碼（至少 6 碼）", type="password", key="_reg_pw")
        r_pw2 = st.text_input("確認密碼", type="password", key="_reg_pw2")
        r_promo = st.text_input("優惠碼（選填）", key="_reg_promo")

        # 註冊成功後在 dialog 內直接顯示驗證提示（不能 st.rerun，會關掉 dialog）
        if st.session_state.get("_reg_success_email"):
            _show_verify_prompt_in_dialog(st.session_state["_reg_success_email"])
        elif st.button("建立帳號", key="_btn_reg", use_container_width=True, type="primary"):
            if not r_email or not r_pw:
                st.error("請填寫 Email 和密碼")
            elif r_pw != r_pw2:
                st.error("兩次密碼不一致")
            elif len(r_pw) < 6:
                st.error("密碼至少 6 個字元")
            else:
                try:
                    data = _api_post("/auth/register", {
                        "email": r_email,
                        "password": r_pw,
                        "display_name": r_name,
                        "promo_code": r_promo,
                    })
                    if data.get("status") == "verification_sent":
                        st.session_state["_reg_success_email"] = data["email"]
                        st.session_state["_verify_email_sent"] = data["email"]
                        st.rerun()
                    else:
                        _save_session(data["token"], data["email"], data["plan"], True)
                        st.rerun()
                except ValueError as e:
                    st.error(str(e))


def _show_verify_prompt_in_dialog(email: str):
    """在 dialog 內顯示驗證信提示（不使用 st.rerun 避免關掉 dialog）"""
    st.markdown(
        f"""
        <div style="text-align:center;padding:16px 0 8px;">
          <div style="font-size:48px">✉️</div>
          <h3 style="color:#e0e0e0;margin:12px 0 8px">驗證信已寄出</h3>
          <p style="color:#aaa;font-size:14px;line-height:1.7">
            我們已將驗證連結寄至<br>
            <strong style="color:#4f8ef7">{email}</strong><br>
            請點擊信件中的連結完成驗證，<br>
            驗證後回到此頁面登入即可。
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info("⚠️ 若未收到信件，請檢查垃圾郵件匣")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("重送驗證信", key="_reg_resend", use_container_width=True):
            _resend_by_email(email)
    with col_b:
        if st.button("前往登入", key="_reg_goto_login", use_container_width=True, type="primary"):
            st.session_state.pop("_reg_success_email", None)
            st.session_state.pop("_verify_email_sent", None)
            st.rerun()


# ── 功能鎖定牆 ────────────────────────────────────────────────────────────────

def require_plan(min_plan: str = "pro"):
    """
    在頁面頂端呼叫。若未登入或方案不足，顯示鎖定訊息並 st.stop()。
    必須在 st.set_page_config() 之後、任何其他 widget 之前呼叫。
    """
    if not is_logged_in():
        _show_locked_wall(reason="login")
        st.stop()
    if not has_plan(min_plan):
        _show_locked_wall(reason="upgrade", required=min_plan)
        st.stop()


def _show_locked_wall(reason: str, required: str = "pro"):
    plan_label = PLAN_LABEL.get(required, required)
    if reason == "login":
        st.markdown(
            """
            <div style="text-align:center;padding:80px 20px;">
              <div style="font-size:56px">🔒</div>
              <h2 style="color:#4f8ef7;margin:16px 0 8px">此功能需要登入</h2>
              <p style="color:#aaa;margin-bottom:32px">請登入或建立帳號以繼續使用</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        _, col2, _ = st.columns([1, 1, 1])
        with col2:
            if st.button("登入 / 註冊", key="_wall_login_btn", use_container_width=True, type="primary"):
                show_login_modal()
    else:
        st.markdown(
            f"""
            <div style="text-align:center;padding:80px 20px;">
              <div style="font-size:56px">🔐</div>
              <h2 style="color:#f5a623;margin:16px 0 8px">此功能需要 {plan_label}</h2>
              <p style="color:#aaa;margin-bottom:32px">升級方案即可解鎖所有進階功能</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        _, col2, _ = st.columns([1, 1, 1])
        with col2:
            if st.button("查看方案", key="_wall_upgrade_btn", use_container_width=True, type="primary"):
                st.switch_page("pages/05_pricing.py")


# ── Sidebar 使用者狀態 ────────────────────────────────────────────────────────

def auth_sidebar():
    """在 sidebar 顯示登入狀態，每頁呼叫一次。"""
    cm = _cookie_manager()

    # 若尚未登入，嘗試從 cookie 還原 session
    if not is_logged_in():
        token = cm.get(_COOKIE_KEY)
        if token and token != "None":
            try:
                r = _requests.get(
                    f"{API_URL}/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
                if r.ok:
                    data = r.json()
                    st.session_state["token"] = token
                    st.session_state["email"] = data["email"]
                    st.session_state["plan"] = data["plan"]
                    st.session_state["email_verified"] = data.get("email_verified", False)
                    st.rerun()
                else:
                    cm.delete(_COOKIE_KEY)
            except Exception:
                pass

    with st.sidebar:
        st.divider()
        if is_logged_in():
            plan = current_plan()
            color = PLAN_COLOR.get(plan, "#888")
            label = PLAN_LABEL.get(plan, plan)
            email = st.session_state.get("email", "")

            # 每次頁面載入時更新 cookie 到期時間
            cm.set(_COOKIE_KEY, st.session_state["token"], max_age=_COOKIE_MAX_AGE)

            st.markdown(
                f'<div style="font-size:12px;color:#aaa">{email}</div>'
                f'<div style="font-size:13px;font-weight:bold;color:{color}">● {label}</div>',
                unsafe_allow_html=True,
            )

            if st.button("登出", key="_sidebar_logout", use_container_width=True):
                cm.delete(_COOKIE_KEY)
                for k in ["token", "email", "plan", "email_verified"]:
                    st.session_state.pop(k, None)
                st.rerun()
        else:
            st.markdown('<div style="font-size:13px;color:#aaa">尚未登入</div>', unsafe_allow_html=True)
            if st.button("登入 / 註冊", key="_sidebar_login", use_container_width=True, type="primary"):
                show_login_modal()


def _resend_by_email(email: str):
    """Modal 用：尚未登入，只用 email 重送"""
    try:
        r = _requests.post(
            f"{API_URL}/auth/resend-by-email",
            json={"email": email},
            timeout=20,
        )
        if r.ok:
            st.success("驗證信已重新寄出！")
        else:
            st.error(r.json().get("detail", "寄送失敗"))
    except Exception as e:
        st.error(f"寄送失敗：{e}")
