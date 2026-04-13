"""
研究報告頁面 — 公開可讀，管理員可新增 / 編輯 / 刪除
"""
import os
import streamlit as st
import requests as _requests
from auth import auth_sidebar, is_logged_in

auth_sidebar()

ADMIN_EMAIL = "ohmygot65@yahoo.com.tw"
API_URL = os.getenv("API_URL", "http://localhost:8000")

is_admin = is_logged_in() and st.session_state.get("email", "").lower() == ADMIN_EMAIL
token = st.session_state.get("token", "")
headers = {"Authorization": f"Bearer {token}"}


# ── API 輔助 ──────────────────────────────────────────────────────────────────

def _api(method: str, endpoint: str, **kwargs):
    try:
        r = getattr(_requests, method)(
            f"{API_URL}{endpoint}", headers=headers, timeout=20, **kwargs
        )
        if r.ok:
            return r.json(), None
        return None, r.json().get("detail", r.text)
    except Exception as e:
        return None, str(e)


# ── 管理員：新增文章 Dialog ────────────────────────────────────────────────────

@st.dialog("新增 / 編輯文章", width="large")
def _article_dialog(existing: dict | None = None):
    """existing 為 None 時表示新增，否則為編輯"""
    d = existing or {}
    title = st.text_input("標題", value=d.get("title", ""), key="_art_title")
    summary = st.text_area("摘要", value=d.get("summary", "") or "", height=100, key="_art_summary")
    tags_raw = st.text_input(
        "標籤（逗號分隔）",
        value=", ".join(d.get("tags", []) or []),
        key="_art_tags",
    )
    author = st.text_input("作者", value=d.get("author", "AI 研究員"), key="_art_author")
    content = st.text_area("全文", value=d.get("content", ""), height=400, key="_art_content")

    col_pub, col_cancel = st.columns([1, 1])
    with col_pub:
        if st.button("發布", type="primary", use_container_width=True, key="_art_submit"):
            if not title or not content:
                st.error("標題與全文為必填")
                return
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
            payload = {
                "title": title,
                "summary": summary or None,
                "content": content,
                "tags": tags or None,
                "author": author or "AI 研究員",
                "is_published": True,
            }
            if existing:
                data, err = _api("put", f"/articles/{existing['id']}", json=payload)
            else:
                data, err = _api("post", "/articles", json=payload)

            if err:
                st.error(f"儲存失敗：{err}")
            else:
                st.success("已儲存！")
                st.session_state.pop("_articles_cache", None)
                st.rerun()
    with col_cancel:
        if st.button("取消", use_container_width=True, key="_art_cancel"):
            st.rerun()


# ── 頁面主體 ──────────────────────────────────────────────────────────────────

# 標題列
col_title, col_btn = st.columns([4, 1])
with col_title:
    st.title("📚 研究報告")
with col_btn:
    if is_admin:
        st.write("")  # 對齊間距
        if st.button("＋ 新增文章", type="primary", use_container_width=True, key="_new_article"):
            _article_dialog()

st.caption("AI 研究員針對台指期籌碼、選擇權結構與市場訊號的深度分析")
st.divider()

# 載入文章列表
if "refresh_articles" not in st.session_state:
    st.session_state["refresh_articles"] = False

if "_articles_cache" not in st.session_state or st.session_state.pop("refresh_articles", False):
    with st.spinner("載入中..."):
        data, err = _api("get", "/articles?limit=50&offset=0")
    if err:
        st.error(f"載入失敗：{err}")
        st.stop()
    st.session_state["_articles_cache"] = data or []

articles = st.session_state.get("_articles_cache", [])

if not articles:
    st.info("目前尚無發布的研究文章，敬請期待。")
    st.stop()

# 方向標籤色彩（重用樣式）
TAG_STYLE = (
    "display:inline-block;background:#1e3a5f;color:#7eb8f7;"
    "border-radius:4px;padding:2px 8px;font-size:12px;margin-right:4px;"
)

for art in articles:
    art_id = art["id"]
    published = (art.get("published_at") or art.get("created_at") or "")[:10]
    tags_html = "".join(
        f'<span style="{TAG_STYLE}">{t}</span>' for t in (art.get("tags") or [])
    )
    author_str = art.get("author") or "AI 研究員"
    summary_str = art.get("summary") or ""

    # 標題列
    if is_admin:
        col_art, col_ops = st.columns([5, 1])
    else:
        col_art = st.container()
        col_ops = None

    with col_art:
        with st.expander(f"**{art['title']}**　`{published}`　{author_str}", expanded=False):
            if tags_html:
                st.markdown(tags_html, unsafe_allow_html=True)
                st.write("")
            if summary_str:
                st.markdown(f"> {summary_str}")
                st.divider()
            # 全文（需單獨取得）
            if st.button("載入全文", key=f"_load_{art_id}"):
                detail, err2 = _api("get", f"/articles/{art_id}")
                if err2:
                    st.error(f"載入失敗：{err2}")
                else:
                    st.session_state[f"_art_full_{art_id}"] = detail.get("content", "")

            full_content = st.session_state.get(f"_art_full_{art_id}")
            if full_content:
                st.markdown(full_content)

    if is_admin and col_ops:
        with col_ops:
            st.write("")  # 對齊
            edit_key = f"_edit_{art_id}"
            del_key = f"_del_{art_id}"
            if st.button("編輯", key=edit_key, use_container_width=True):
                # 取得全文再開 dialog
                detail, _ = _api("get", f"/articles/{art_id}")
                if detail:
                    _article_dialog(existing=detail)
            if st.button("刪除", key=del_key, use_container_width=True):
                _, err3 = _api("delete", f"/articles/{art_id}")
                if err3:
                    st.error(f"刪除失敗：{err3}")
                else:
                    st.success("已刪除")
                    st.session_state.pop("_articles_cache", None)
                    st.rerun()
