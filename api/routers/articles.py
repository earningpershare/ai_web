"""
研究文章端點

GET    /articles          — 列出已發布文章（分頁）
GET    /articles/{id}     — 取得單篇文章
POST   /articles          — 新增文章（需 admin token）
PUT    /articles/{id}     — 編輯文章（需 admin token）
DELETE /articles/{id}     — 刪除文章（需 admin token）
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel

from .db import get_conn, query
from .auth import _current_user

router = APIRouter(prefix="/articles", tags=["articles"])
log = logging.getLogger(__name__)

ADMIN_EMAIL = "ohmygot65@yahoo.com.tw"


# ── 管理員驗證 ────────────────────────────────────────────────────────────────

def _require_admin(authorization: str):
    """驗證 token 且確認為管理員帳號"""
    user = _current_user(authorization)
    if (user.email or "").lower() != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="此操作僅限管理員")
    return user


# ── Schemas ───────────────────────────────────────────────────────────────────

class ArticleBody(BaseModel):
    title: str
    summary: Optional[str] = None
    content: str
    tags: Optional[list[str]] = None
    author: str = "AI 研究員"
    is_published: bool = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
def list_articles(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
):
    """列出已發布文章（分頁）"""
    return query(
        """
        SELECT id, title, summary, tags, author, published_at, is_published, created_at
        FROM research_articles
        WHERE is_published = TRUE
        ORDER BY published_at DESC
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    )


@router.get("/{article_id}")
def get_article(article_id: int):
    """取得單篇文章（含全文）"""
    rows = query(
        """
        SELECT * FROM research_articles
        WHERE id = %s AND is_published = TRUE
        """,
        (article_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="文章不存在或尚未發布")
    return rows[0]


@router.post("", status_code=201)
def create_article(body: ArticleBody, authorization: str = Header(default="")):
    """新增文章（需 admin token）"""
    _require_admin(authorization)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO research_articles
                    (title, summary, content, tags, author, is_published)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    body.title,
                    body.summary,
                    body.content,
                    body.tags,
                    body.author,
                    body.is_published,
                ),
            )
            row = dict(cur.fetchone())
        conn.commit()
    log.info("管理員新增文章 id=%s title=%s", row["id"], row["title"])
    return row


@router.put("/{article_id}")
def update_article(
    article_id: int,
    body: ArticleBody,
    authorization: str = Header(default=""),
):
    """編輯文章（需 admin token）"""
    _require_admin(authorization)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE research_articles
                SET title=%s, summary=%s, content=%s, tags=%s,
                    author=%s, is_published=%s
                WHERE id = %s
                RETURNING *
                """,
                (
                    body.title,
                    body.summary,
                    body.content,
                    body.tags,
                    body.author,
                    body.is_published,
                    article_id,
                ),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="文章不存在")
            row = dict(row)
        conn.commit()
    log.info("管理員更新文章 id=%s", article_id)
    return row


@router.delete("/{article_id}")
def delete_article(article_id: int, authorization: str = Header(default="")):
    """刪除文章（需 admin token）"""
    _require_admin(authorization)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM research_articles WHERE id = %s RETURNING id",
                (article_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="文章不存在")
        conn.commit()
    log.info("管理員刪除文章 id=%s", article_id)
    return {"ok": True, "deleted_id": article_id}
