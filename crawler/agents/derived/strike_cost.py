"""
選擇權各履約價加權平均持倉成本（逐日遞推）

遞推公式：
  delta_oi = today_oi - prev_oi
  if delta_oi > 0:
      new_avg = (prev_avg * prev_oi + today_price * delta_oi) / today_oi
  else:          # 減倉或持平
      new_avg = prev_avg
  if today_oi == 0:
      new_avg = 0
"""

from datetime import date

from .base import dict_cursor


def compute_strike_avg_cost(conn, trade_date: date) -> list[dict]:
    # ── 今日行情 ──
    with dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT contract_month, strike_price, call_put,
                   open_price, high_price, low_price, close_price,
                   volume, open_interest
            FROM txo_options_daily
            WHERE trade_date = %s AND session = '一般'
              AND contract_month NOT LIKE '%%/%%'
            """,
            (trade_date,),
        )
        today_rows = cur.fetchall()

    if not today_rows:
        return []

    # ── 前一日成本記錄 ──
    with dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT contract_month, strike_price, call_put,
                   avg_cost, open_interest AS prev_oi
            FROM options_strike_avg_cost
            WHERE trade_date = (
                SELECT MAX(trade_date) FROM options_strike_avg_cost
                WHERE trade_date < %s
            )
            """,
            (trade_date,),
        )
        prev = {
            (r["contract_month"], float(r["strike_price"]), r["call_put"]): r
            for r in cur.fetchall()
        }

    records = []
    for row in today_rows:
        cm = row["contract_month"]
        sp = float(row["strike_price"]) if row["strike_price"] is not None else None
        cp = row["call_put"]
        if sp is None:
            continue

        # 今日典型價（高低收均值）
        prices = [float(row[k]) for k in ("high_price", "low_price", "close_price")
                  if row[k] is not None]
        if not prices:
            continue
        daily_price = sum(prices) / len(prices)

        cur_oi = int(row["open_interest"] or 0)
        vol    = int(row["volume"]        or 0)

        p        = prev.get((cm, sp, cp))
        prev_avg = float(p["avg_cost"]) if p and p["avg_cost"] is not None else None
        prev_oi  = int(p["prev_oi"])    if p and p["prev_oi"]  is not None else 0
        delta_oi = cur_oi - prev_oi

        if cur_oi == 0:
            new_avg = 0.0
        elif prev_avg is None or prev_oi == 0:
            new_avg = daily_price
        elif delta_oi > 0:
            new_avg = (prev_avg * prev_oi + daily_price * delta_oi) / cur_oi
        else:
            new_avg = prev_avg

        records.append({
            "trade_date":     trade_date,
            "contract_month": cm,
            "strike_price":   sp,
            "call_put":       cp,
            "daily_price":    round(daily_price, 4),
            "volume":         vol,
            "open_interest":  cur_oi,
            "delta_oi":       delta_oi,
            "avg_cost":       round(new_avg, 4),
        })
    return records
