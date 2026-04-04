"""
Email 驗證落地頁
Supabase 驗證信點擊後 redirect 到此頁
驗證是由 Supabase server 端完成，此頁只需顯示結果
"""
import streamlit as st

st.set_page_config(page_title="信箱驗證", page_icon="✉️", layout="centered")

st.markdown(
    "<style>[data-testid='stSidebar']{display:none}</style>",
    unsafe_allow_html=True,
)

params = st.query_params
error = params.get("error_description") or params.get("error") or ""

st.markdown("<br><br>", unsafe_allow_html=True)

if error:
    st.markdown(
        f"""
        <div style="text-align:center;">
          <div style="font-size:52px">⚠️</div>
          <h2 style="color:#f5a623;margin:16px 0 8px">驗證失敗</h2>
          <p style="color:#aaa;">{error}</p>
          <p style="color:#666;font-size:13px;margin-top:12px">
            連結可能已過期（24 小時有效）<br>請重新登入後從 Sidebar 重送驗證信
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    # Supabase 已在 server 端完成驗證再 redirect 過來
    # 清除 session 中的「等待驗證」狀態
    st.session_state.pop("_verify_email_sent", None)
    st.session_state["email_verified"] = True

    st.markdown(
        """
        <div style="text-align:center;">
          <div style="font-size:64px">✅</div>
          <h2 style="color:#4f8ef7;margin:16px 0 8px">信箱驗證成功！</h2>
          <p style="color:#aaa;line-height:1.8">
            您的帳號已完成驗證，歡迎加入 TaifexAI。<br>
            請點擊下方按鈕登入，開始使用。
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)
_, col, _ = st.columns([1, 1, 1])
with col:
    label = "返回首頁" if error else "前往登入"
    if st.button(label, use_container_width=True, type="primary"):
        st.switch_page("app.py")
