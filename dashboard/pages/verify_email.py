"""
Email 驗證落地頁
Supabase 驗證信點擊後 redirect 到此頁

Supabase 使用 hash fragment（#access_token=...）而非 query params，
Streamlit 無法直接讀取 hash，因此用 JavaScript 將 hash 轉為 query params 再 reload。
"""
import streamlit as st

st.set_page_config(page_title="信箱驗證", page_icon="✉️", layout="centered")

st.markdown(
    "<style>[data-testid='stSidebar']{display:none}</style>",
    unsafe_allow_html=True,
)

params = st.query_params

# ── Step 1: 若 URL 含 hash fragment，用 JS 轉為 query params 再 reload ──────
# Supabase redirect: /verify_email#access_token=xxx&type=signup
# 轉換後:           /verify_email?access_token=xxx&type=signup
# 這段 JS 只在有 hash 時執行一次

has_token = params.get("access_token") or params.get("error_description") or params.get("error")

if not has_token:
    # 注入 JS：把 hash fragment 轉成 query string 並 reload
    st.markdown(
        """
        <script>
        (function() {
            var hash = window.location.hash;
            if (hash && hash.length > 1) {
                // #access_token=xxx&type=signup → ?access_token=xxx&type=signup
                var queryString = hash.substring(1);
                var newUrl = window.location.pathname + '?' + queryString;
                window.location.replace(newUrl);
            }
        })();
        </script>
        <noscript>請啟用 JavaScript 以完成驗證</noscript>
        """,
        unsafe_allow_html=True,
    )
    # 顯示載入中（JS 轉換需要一瞬間）
    st.markdown(
        """
        <div style="text-align:center;padding:60px 0;">
          <div style="font-size:48px">⏳</div>
          <p style="color:#aaa;margin-top:16px">正在處理驗證，請稍候...</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# ── Step 2: 現在 query params 已就位，處理結果 ─────────────────────────────────

error = params.get("error_description") or params.get("error") or ""
token_type = params.get("type", "")

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
    st.session_state.pop("_verify_email_sent", None)
    st.session_state.pop("_reg_success_email", None)
    st.session_state["email_verified"] = True
    st.session_state["_auto_show_login"] = True  # 回首頁後自動彈出登入框

    st.markdown(
        """
        <div style="text-align:center;">
          <div style="font-size:64px">✅</div>
          <h2 style="color:#4f8ef7;margin:16px 0 8px">信箱驗證成功！</h2>
          <p style="color:#aaa;line-height:1.8">
            歡迎加入台指天空 SpaceTFX。<br>
            即將自動跳轉至首頁，請登入開始使用。
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # 3 秒後自動跳轉
    st.markdown(
        """
        <script>
        setTimeout(function() {
            window.location.href = "/";
        }, 3000);
        </script>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)
_, col, _ = st.columns([1, 1, 1])
with col:
    label = "返回首頁" if error else "立即登入"
    if st.button(label, use_container_width=True, type="primary"):
        st.switch_page("app.py")
