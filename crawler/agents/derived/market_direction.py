"""
各群體市場方向分析（折算小台口數）

groups: 外資及陸資 / 投信 / 自營商 / 三大法人 / 散戶
期貨 delta = TX_net×4 + MTX_net×1 + MXF_net×0.4
選擇權 bull = call_buy_oi + put_sell_oi  （BC + SP）
選擇權 bear = put_buy_oi  + call_sell_oi （BP + SC）
options_delta = (bull - bear) × 4  (TXO→小台)
"""

from datetime import date

from .base import dict_cursor, s, FUT_MULTIPLIER, TXO_TO_MTX


def _futures_delta(code_oi_map: dict) -> float:
    return round(sum(code_oi_map.get(c, 0) * m for c, m in FUT_MULTIPLIER.items()), 2)


def _opt_stats(cbo, cso, pbo, pso):
    bull = s(cbo) + s(pso)
    bear = s(pbo) + s(cso)
    net  = bull - bear
    return bull, bear, net, round(net * TXO_TO_MTX, 2)


def compute_market_direction(conn, trade_date: date) -> list[dict]:
    # ── 期貨 per institution ──
    with dict_cursor(conn) as cur:
        cur.execute(
            "SELECT institution_type, contract_code, net_oi FROM institutional_futures WHERE trade_date = %s",
            (trade_date,),
        )
        inst_fut_rows = cur.fetchall()

    # ── 期貨 散戶 ──
    with dict_cursor(conn) as cur:
        cur.execute(
            "SELECT contract_code, net_oi FROM retail_futures WHERE trade_date = %s",
            (trade_date,),
        )
        retail_fut = {r["contract_code"]: s(r["net_oi"]) for r in cur.fetchall()}

    # ── 選擇權 per institution ──
    with dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT institution_type,
                   call_buy_oi, call_sell_oi, put_buy_oi, put_sell_oi
            FROM institutional_options
            WHERE trade_date = %s AND contract_code = '臺指選擇權'
            """,
            (trade_date,),
        )
        inst_opt = {r["institution_type"]: r for r in cur.fetchall()}

    # ── 選擇權 散戶 ──
    with dict_cursor(conn) as cur:
        cur.execute(
            "SELECT call_buy_oi, call_sell_oi, put_buy_oi, put_sell_oi FROM retail_options WHERE trade_date = %s",
            (trade_date,),
        )
        retail_opt = cur.fetchone()

    # 整理期貨 per institution
    inst_fut: dict[str, dict] = {}
    for r in inst_fut_rows:
        it = r["institution_type"]
        if it not in inst_fut:
            inst_fut[it] = {}
        inst_fut[it][r["contract_code"]] = s(r["net_oi"])

    def _build_record(group: str, fut_map: dict, opt_row) -> dict:
        fd   = _futures_delta(fut_map)
        cbo  = s(opt_row.get("call_buy_oi")  if opt_row else 0)
        cso  = s(opt_row.get("call_sell_oi") if opt_row else 0)
        pbo  = s(opt_row.get("put_buy_oi")   if opt_row else 0)
        pso  = s(opt_row.get("put_sell_oi")  if opt_row else 0)
        bull, bear, o_net, od = _opt_stats(cbo, cso, pbo, pso)
        return {
            "trade_date":          trade_date,
            "group_type":          group,
            "tx_net_oi":           fut_map.get("臺股期貨",    0),
            "mtx_net_oi":          fut_map.get("小型臺指期貨", 0),
            "mxf_net_oi":          fut_map.get("微型臺指期貨", 0),
            "futures_delta_mtx":   fd,
            "call_buy_oi":         cbo, "call_sell_oi": cso,
            "put_buy_oi":          pbo, "put_sell_oi":  pso,
            "options_bull_oi":     bull, "options_bear_oi": bear,
            "options_net_oi":      o_net, "options_delta_mtx": od,
            "total_delta_mtx":     round(fd + od, 2),
        }

    records = []

    # 三大法人各別
    for inst in ("外資及陸資", "投信", "自營商"):
        records.append(_build_record(inst, inst_fut.get(inst, {}), inst_opt.get(inst)))

    # 三大法人合計
    agg_fut: dict = {}
    for fm in inst_fut.values():
        for code, v in fm.items():
            agg_fut[code] = agg_fut.get(code, 0) + v
    agg_opt = {
        "call_buy_oi":  sum(s(inst_opt.get(t, {}).get("call_buy_oi"))  for t in inst_opt),
        "call_sell_oi": sum(s(inst_opt.get(t, {}).get("call_sell_oi")) for t in inst_opt),
        "put_buy_oi":   sum(s(inst_opt.get(t, {}).get("put_buy_oi"))   for t in inst_opt),
        "put_sell_oi":  sum(s(inst_opt.get(t, {}).get("put_sell_oi"))  for t in inst_opt),
    }
    records.append(_build_record("三大法人", agg_fut, agg_opt))

    # 散戶
    if retail_opt:
        records.append(_build_record("散戶", retail_fut, dict(retail_opt)))

    return records
