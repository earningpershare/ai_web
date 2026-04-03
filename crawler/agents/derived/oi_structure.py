"""
週選 / 月選 OI 結構比

命名規則：
  W 系列（202604W1, 202604W2）= 週選
  F 系列（202604F1, 202604F2）= 彈性到期週選（短週期）
  無後綴（202604, 202605）   = 標準月選
"""

from datetime import date

from .base import dict_cursor, s


def compute_oi_structure(conn, trade_date: date) -> list[dict]:
    with dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT contract_month, call_put, SUM(open_interest) AS oi
            FROM txo_options_daily
            WHERE trade_date = %s AND session = '一般'
            GROUP BY contract_month, call_put
            """,
            (trade_date,),
        )
        rows = cur.fetchall()

    if not rows:
        return []

    weekly_c = weekly_p = monthly_c = monthly_p = 0
    weekly_by_exp: dict[str, int] = {}

    for r in rows:
        cm = r["contract_month"]
        oi = s(r["oi"])
        cp = r["call_put"]
        is_weekly = "W" in cm or "F" in cm

        if is_weekly:
            weekly_by_exp[cm] = weekly_by_exp.get(cm, 0) + oi
            if cp == "C": weekly_c += oi
            else:         weekly_p += oi
        else:
            if cp == "C": monthly_c += oi
            else:         monthly_p += oi

    total        = weekly_c + weekly_p + monthly_c + monthly_p
    weekly_ratio = (weekly_c + weekly_p) / total if total else 0.0
    dominant     = max(weekly_by_exp, key=weekly_by_exp.get) if weekly_by_exp else None

    return [{
        "trade_date":          trade_date,
        "weekly_call_oi":      weekly_c,
        "weekly_put_oi":       weekly_p,
        "monthly_call_oi":     monthly_c,
        "monthly_put_oi":      monthly_p,
        "weekly_oi_ratio":     round(weekly_ratio, 4),
        "weekly_dominant_exp": dominant,
    }]
