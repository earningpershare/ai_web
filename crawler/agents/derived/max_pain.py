"""
Max Pain — 使 全市場選擇權買方損失最大 的結算履約價

total_loss(K) = Σ_C max(K - strike, 0) × C_OI
              + Σ_P max(strike - K, 0) × P_OI
使 total_loss 最小的 K = Max Pain
"""

from datetime import date

from .base import dict_cursor, s


def compute_max_pain(conn, trade_date: date) -> list[dict]:
    with dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT strike_price, call_put, SUM(open_interest) AS oi
            FROM options_strike_avg_cost
            WHERE trade_date = %s AND open_interest > 0
            GROUP BY strike_price, call_put
            """,
            (trade_date,),
        )
        rows = cur.fetchall()

    if not rows:
        return []

    strikes = sorted({float(r["strike_price"]) for r in rows})
    call_oi = {float(r["strike_price"]): s(r["oi"]) for r in rows if r["call_put"] == "C"}
    put_oi  = {float(r["strike_price"]): s(r["oi"]) for r in rows if r["call_put"] == "P"}

    pain: dict[float, float] = {}
    for k in strikes:
        loss  = sum(max(k - sp, 0) * oi for sp, oi in call_oi.items())
        loss += sum(max(sp - k, 0) * oi for sp, oi in put_oi.items())
        pain[k] = loss

    mp = min(pain, key=pain.get)

    # underlying
    with dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT close_price FROM tx_futures_daily
            WHERE trade_date = %s AND contract_code = 'TX'
              AND session = '一般' AND contract_month NOT LIKE '%%/%%'
            ORDER BY contract_month ASC LIMIT 1
            """,
            (trade_date,),
        )
        r = cur.fetchone()
    underlying = float(r["close_price"]) if r and r["close_price"] else None

    return [{
        "trade_date":       trade_date,
        "max_pain_strike":  mp,
        "underlying_price": underlying,
        "delta_pts":        round(mp - underlying, 2) if underlying is not None else None,
    }]
