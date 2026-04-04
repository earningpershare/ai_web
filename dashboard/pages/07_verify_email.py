"""
Email 驗證落地頁
Supabase 驗證信點擊後會 redirect 到此頁，URL 帶有 access_token 或 error
"""
import streamlit as st

st.set_page_config(page_title="信箱驗證", page_icon="✉️", layout="centered")

# 隱藏 sidebar
st.markdown(
    "<style>[data-testid='stSidebar']{display:none}</style>",
    unsafe_allow_html=True,
)

st.markdown("<br><br>", unsafe_allow_html=True)

# Supabase 驗證成功時帶 access_token；失敗時帶 error_description
params = st.query_params
error = params.get("error_description", "") or params.get("error", "")
token = params.get("access_token", "")

if error:
    st.markdown(
        f"""
        <div style="text-align:center;">
          <div style="font-size:52px">⚠️</div>
          <h2 style="color:#f5a623;margin:16px 0 8px">驗證失敗</h2>
          <p style="color:#aaa;">{error}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
elif token:
    # 把 token 存入 session 讓使用者不需重新登入
    st.session_state["_verify_token"] = token
    st.session_state["email_verified"] = True
    st.markdown(
        """
        <div style="text-align:center;">
          <div style="font-size:60px">✅</div>
          <h2 style="color:#4f8ef7;margin:16px 0 8px">信箱驗證成功！</h2>
          <p style="color:#aaa;">歡迎加入 TaifexAI，您的帳號已完成驗證。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
        <div style="text-align:center;">
          <div style="font-size:52px">✉️</div>
          <h2 style="color:#e0e0e0;margin:16px 0 8px">等待驗證</h2>
          <p style="color:#aaa;">請前往信箱點擊驗證連結以完成帳號設定。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)
_, col, _ = st.columns([1, 1, 1])
with col:
    if st.button("返回首頁", use_container_width=True, type="primary"):
        st.switch_page("app.py")
