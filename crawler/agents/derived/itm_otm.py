"""
全市場 ITM / ATM / OTM 未平倉分布
ATM 定義：履約價與 underlying 差距 ≤ 0.3%
"""

from datetime import date

from .base import dict_cursor, s


def compute_itm_otm(conn, trade_date: date) -> list[dict]:
    # underlying = 近月 TX 一般盤收盤價
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
    if not r or not r["close_price"]:
        return []
    underlying = float(r["close_price"])

    with dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT call_put, strike_price,
                   SUM(volume) AS vol, SUM(open_interest) AS oi
            FROM txo_options_daily
            WHERE trade_date = %s AND session = '一般'
              AND contract_month NOT LIKE '%%/%%'
              AND strike_price IS NOT NULL
            GROUP BY call_put, strike_price
            """,
            (trade_date,),
        )
        rows = cur.fetchall()

    call_itm_oi = call_otm_oi = call_atm_oi = 0
    put_itm_oi  = put_otm_oi  = put_atm_oi  = 0
    call_itm_vol = call_otm_vol = 0
    put_itm_vol  = put_otm_vol  = 0

    for row in rows:
        sp  = float(row["strike_price"])
        oi  = s(row["oi"])
        vol = s(row["vol"])
        atm = abs(sp - underlying) / underlying < 0.003

        if row["call_put"] == "C":
            if atm:          call_atm_oi  += oi
            elif sp < underlying: call_itm_oi += oi; call_itm_vol += vol
            else:            call_otm_oi  += oi; call_otm_vol += vol
        else:
            if atm:          put_atm_oi   += oi
            elif sp > underlying: put_itm_oi  += oi; put_itm_vol  += vol
            else:            put_otm_oi   += oi; put_otm_vol  += vol

    return [{
        "trade_date":       trade_date,
        "underlying_price": underlying,
        "call_itm_oi":      call_itm_oi,  "call_otm_oi": call_otm_oi,
        "call_atm_oi":      call_atm_oi,
        "put_itm_oi":       put_itm_oi,   "put_otm_oi":  put_otm_oi,
        "put_atm_oi":       put_atm_oi,
        "call_itm_volume":  call_itm_vol, "call_otm_volume": call_otm_vol,
        "put_itm_volume":   put_itm_vol,  "put_otm_volume":  put_otm_vol,
    }]
