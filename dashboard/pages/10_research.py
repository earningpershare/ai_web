"""
研究報告頁面 — 公開可讀，管理員可新增 / 編輯 / 刪除
"""
import os
import streamlit as st
import requests as _requests
from auth import auth_sidebar, is_logged_in


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
