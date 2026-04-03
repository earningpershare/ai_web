"""
散戶期貨 / 散戶選擇權
  retail_futures  = tx_futures_daily（全市場）− institutional_futures（三大法人）
  retail_options  = put_call_ratio（全市場）− institutional_options（三大法人）
"""

from datetime import date

from .base import dict_cursor, s, INST_TO_DAILY


def compute_retail_futures(conn, trade_date: date) -> list[dict]:
    # ── 全市場 ──
    with dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT contract_code,
                   SUM(volume) AS total_volume,
                   SUM(CASE WHEN session = '一般' THEN open_interest ELSE 0 END) AS total_oi
            FROM tx_futures_daily
            WHERE trade_date = %s
              AND contract_month NOT LIKE '%%/%%'
            GROUP BY contract_code
            """,
            (trade_date,),
        )
        market = {r["contract_code"]: r for r in cur.fetchall()}

    # ── 三大法人合計 ──
    with dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT contract_code,
                   SUM(long_volume)  AS inst_lv,
                   SUM(short_volume) AS inst_sv,
                   SUM(long_oi)      AS inst_lo,
                   SUM(short_oi)     AS inst_so
            FROM institutional_futures
            WHERE trade_date = %s
            GROUP BY contract_code
            """,
            (trade_date,),
        )
        inst = {r["contract_code"]: r for r in cur.fetchall()}

    records = []
    for inst_code, daily_code in INST_TO_DAILY.items():
        mkt = market.get(daily_code)
        ins = inst.get(inst_code)
        if not mkt or not ins:
            continue
        tv  = s(mkt["total_volume"])
        toi = s(mkt["total_oi"])
        rlv = tv  - s(ins["inst_lv"])
        rsv = tv  - s(ins["inst_sv"])
        rlo = toi - s(ins["inst_lo"])
        rso = toi - s(ins["inst_so"])
        records.append({
            "trade_date":    trade_date,
            "contract_code": inst_code,
            "long_volume":   rlv,
            "short_volume":  rsv,
            "net_volume":    rlv - rsv,
            "long_oi":       rlo,
            "short_oi":      rso,
            "net_oi":        rlo - rso,
        })
    return records


def compute_retail_options(conn, trade_date: date) -> list[dict]:
    with dict_cursor(conn) as cur:
        cur.execute(
            "SELECT call_volume, put_volume, call_oi, put_oi FROM put_call_ratio WHERE trade_date = %s",
            (trade_date,),
        )
        mkt = cur.fetchone()
    if not mkt:
        return []

    with dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT SUM(call_buy_volume)  AS cbv, SUM(call_sell_volume) AS csv,
                   SUM(put_buy_volume)   AS pbv, SUM(put_sell_volume)  AS psv,
                   SUM(call_buy_oi)      AS cbo, SUM(call_sell_oi)     AS cso,
                   SUM(put_buy_oi)       AS pbo, SUM(put_sell_oi)      AS pso
            FROM institutional_options
            WHERE trade_date = %s AND contract_code = '臺指選擇權'
            """,
            (trade_date,),
        )
        ins = cur.fetchone()
    if not ins:
        return []

    cv = s(mkt["call_volume"]); pv = s(mkt["put_volume"])
    co = s(mkt["call_oi"]);     po = s(mkt["put_oi"])

    r_cbv = cv - s(ins["cbv"]); r_csv = cv - s(ins["csv"])
    r_pbv = pv - s(ins["pbv"]); r_psv = pv - s(ins["psv"])
    r_cbo = co - s(ins["cbo"]); r_cso = co - s(ins["cso"])
    r_pbo = po - s(ins["pbo"]); r_pso = po - s(ins["pso"])

    return [{
        "trade_date":       trade_date,
        "call_buy_volume":  r_cbv, "call_sell_volume": r_csv,
        "call_net_volume":  r_cbv - r_csv,
        "call_buy_oi":      r_cbo, "call_sell_oi":     r_cso,
        "call_net_oi":      r_cbo - r_cso,
        "put_buy_volume":   r_pbv, "put_sell_volume":  r_psv,
        "put_net_volume":   r_pbv - r_psv,
        "put_buy_oi":       r_pbo, "put_sell_oi":      r_pso,
        "put_net_oi":       r_pbo - r_pso,
    }]
