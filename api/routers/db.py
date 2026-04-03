"""
資料庫連線工具 — API 層共用
"""

import os
import psycopg2
import psycopg2.extras


def get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "financial_db"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def query(sql: str, params=None) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
