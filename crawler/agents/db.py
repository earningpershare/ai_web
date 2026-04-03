import os
import psycopg2
from psycopg2.extras import execute_values


def get_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "financial_db"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def upsert(conn, table: str, rows: list[dict], conflict_cols: list[str]) -> int:
    """Generic upsert. Always refreshes last_edit_time = NOW() on update."""
    if not rows:
        return 0
    # 批次去重：相同 conflict key 只保留最後一筆，避免同批次衝突
    seen: dict = {}
    for row in rows:
        key = tuple(row[c] for c in conflict_cols)
        seen[key] = row
    rows = list(seen.values())
    cols = list(rows[0].keys())
    values = [[r[c] for c in cols] for r in rows]
    update_cols = [c for c in cols if c not in conflict_cols]
    set_parts = [f"{c} = EXCLUDED.{c}" for c in update_cols]
    set_parts.append("last_edit_time = NOW()")
    conflict_clause = ", ".join(conflict_cols)
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES %s "
        f"ON CONFLICT ({conflict_clause}) DO UPDATE SET {', '.join(set_parts)}"
    )
    with conn.cursor() as cur:
        execute_values(cur, sql, values)
    conn.commit()
    return len(rows)


def log_crawl(conn, agent_name: str, trade_date: str, status: str,
              records: int = 0, message: str = ""):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO crawler_log (agent_name, trade_date, status, records, message)"
            " VALUES (%s, %s, %s, %s, %s)",
            (agent_name, trade_date, status, records, message),
        )
    conn.commit()
