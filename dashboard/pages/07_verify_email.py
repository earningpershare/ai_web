"""
Email 驗證落地頁 — 用戶點擊信件連結後到達此頁
URL 格式：/verify_email?token=xxxxxxxx
"""
import os
import streamlit as st
import requests

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="信箱驗證", page_icon="✉️", layout="centered")

# 隱藏 sidebar（驗證頁不需要）
st.markdown(
    "<style>[data-testid='stSidebar']{display:none}</style>",
    unsafe_allow_html=True,
)

token = st.query_params.get("token", "")

st.markdown("<br><br>", unsafe_allow_html=True)

if not token:
    st.markdown(
        """
        <div style="text-align:center;">
          <div style="font-size:52px">❓</div>
          <h2 style="color:#aaa;margin:16px 0 8px">無效的驗證連結</h2>
          <p style="color:#666;">連結缺少驗證碼，請確認信件中的連結是否完整。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    with st.spinner("驗證中…"):
        try:
            r = requests.get(
                f"{API_URL}/auth/verify",
                params={"token": token},
                timeout=15,
            )
            if r.ok:
                data = r.json()
                st.markdown(
                    f"""
                    <div style="text-align:center;">
                      <div style="font-size:60px">✅</div>
                      <h2 style="color:#4f8ef7;margin:16px 0 8px">驗證成功！</h2>
                      <p style="color:#aaa;">{data.get('message', '信箱驗證完成，歡迎使用 TaifexAI！')}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                # 更新 session 中的驗證狀態
                if st.session_state.get("token"):
                    st.session_state["email_verified"] = True
            else:
                detail = r.json().get("detail", "驗證失敗，請稍後再試") if r.headers.get(
                    "content-type", "").startswith("application/json") else r.text
                st.markdown(
                    f"""
                    <div style="text-align:center;">
                      <div style="font-size:52px">⚠️</div>
                      <h2 style="color:#f5a623;margin:16px 0 8px">驗證失敗</h2>
                      <p style="color:#aaa;">{detail}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        except Exception as e:
            st.error(f"連線錯誤：{e}")

st.markdown("<br>", unsafe_allow_html=True)
_, col, _ = st.columns([1, 1, 1])
with col:
    if st.button("返回首頁", use_container_width=True, type="primary"):
        st.switch_page("app.py")
