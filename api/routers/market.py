"""
市場衍生指標端點：direction / itm-otm / max-pain / oi-structure / dealer-map
（資料由 derived_metrics pipeline 預計算後存入 DB）
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query

from .db import query

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/direction")
def get_market_direction(
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    group: Optional[str] = Query(default=None),
    limit: int = Query(default=60, le=500),
):
    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(days=90)
    group_filter = " AND group_type = %s" if group else ""
    params: list = [start, end]
    if group:
        params.append(group)
    params.append(limit)
    return query(
        f"""
        SELECT * FROM market_direction
        WHERE trade_date BETWEEN %s AND %s{group_filter}
        ORDER BY trade_date DESC, group_type
        LIMIT %s
        """,
        params,
    )


@router.get("/itm-otm")
def get_itm_otm(
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    limit: int = Query(default=60, le=500),
):
    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(days=90)
    return query(
        """
        SELECT * FROM market_itm_otm
        WHERE trade_date BETWEEN %s AND %s
        ORDER BY trade_date DESC
        LIMIT %s
        """,
        (start, end, limit),
    )


@router.get("/max-pain")
def get_max_pain(
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    limit: int = Query(default=60, le=500),
):
    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(days=90)
    return query(
        """
        SELECT * FROM market_max_pain
        WHERE trade_date BETWEEN %s AND %s
        ORDER BY trade_date DESC
        LIMIT %s
        """,
        (start, end, limit),
    )


@router.get("/dealer-map")
def get_dealer_map(
    trade_date: Optional[date] = Query(default=None),
):
    """
    莊家地圖 — 聚合選擇權賣方壓力/支撐帶、法人方向、現價
    一次回傳所有前端需要的指標，減少多次 API 呼叫。
    """
    # 若未指定日期，取最新有資料的交易日
    if trade_date is None:
        rows = query(
            "SELECT MAX(trade_date) AS d FROM options_strike_avg_cost"
        )
        trade_date = rows[0]["d"] if rows and rows[0]["d"] else date.today() - timedelta(days=1)

    # 取得前一交易日（用於計算法人 OI 變化）
    prev_rows = query(
        "SELECT MAX(trade_date) AS d FROM options_strike_avg_cost WHERE trade_date < %s",
        (trade_date,),
    )
    prev_date = prev_rows[0]["d"] if prev_rows and prev_rows[0]["d"] else None

    # 1. 取得當月（最近到期）的逐履約價 OI + delta_oi + avg_cost
    #    只取 OI > 500 的有意義履約價，避免雜訊
    strikes = query(
        """
        SELECT strike_price, call_put, open_interest, delta_oi, avg_cost, contract_month
        FROM options_strike_avg_cost
        WHERE trade_date = %s AND open_interest > 500
        ORDER BY open_interest DESC
        """,
        (trade_date,),
    )

    # 2. 台指期收盤價（近月合約）
    fut = query(
        """
        SELECT close_price FROM tx_futures_daily
        WHERE trade_date = %s AND session = '一般'
          AND LENGTH(contract_month) = 6
        ORDER BY contract_month LIMIT 1
        """,
        (trade_date,),
    )
    underlying = float(fut[0]["close_price"]) if fut and fut[0].get("close_price") else None

    # 3. 法人選擇權買賣 OI（外資 + 自營商）
    inst = query(
        """
        SELECT institution_type,
               call_buy_oi, call_sell_oi, call_net_oi,
               put_buy_oi, put_sell_oi, put_net_oi
        FROM institutional_options
        WHERE trade_date = %s
        ORDER BY institution_type
        """,
        (trade_date,),
    )

    # 法人前日資料（計算變化量）
    inst_prev = []
    if prev_date:
        inst_prev = query(
            """
            SELECT institution_type,
                   call_buy_oi, call_sell_oi, call_net_oi,
                   put_buy_oi, put_sell_oi, put_net_oi
            FROM institutional_options
            WHERE trade_date = %s
            ORDER BY institution_type
            """,
            (prev_date,),
        )

    # 4. PCR（當日）
    pcr = query(
        "SELECT pc_oi_ratio, pc_vol_ratio FROM put_call_ratio WHERE trade_date = %s",
        (trade_date,),
    )

    # 5. Max Pain（當日）
    mp = query(
        "SELECT max_pain_strike, underlying_price, delta_pts FROM market_max_pain WHERE trade_date = %s",
        (trade_date,),
    )

    return {
        "trade_date": str(trade_date),
        "prev_date": str(prev_date) if prev_date else None,
        "underlying": underlying,
        "strikes": strikes,
        "institutional": inst,
        "institutional_prev": inst_prev,
        "pcr": pcr[0] if pcr else None,
        "max_pain": mp[0] if mp else None,
    }


@router.get("/seller-pnl")
def get_seller_pnl(
    trade_date: Optional[date] = Query(default=None),
    min_oi: int = Query(default=500, ge=100, description="只計算 OI 大於此值的履約價"),
):
    """
    賣方盈虧儀表板 — 以當前現價結算，估算賣方的未實現 P&L。

    公式（每口）：
      Call 賣方 P&L = avg_cost − max(0, 現價 − 履約價)
      Put  賣方 P&L = avg_cost − max(0, 履約價 − 現價)

    正數 = 賣方帳面賺、負數 = 帳面虧。
    """
    if trade_date is None:
        rows = query("SELECT MAX(trade_date) AS d FROM options_strike_avg_cost")
        trade_date = rows[0]["d"] if rows and rows[0]["d"] else date.today() - timedelta(days=1)

    # 期貨近月收盤（作為現價）
    fut = query(
        """
        SELECT close_price FROM tx_futures_daily
        WHERE trade_date = %s AND session = '一般'
          AND LENGTH(contract_month) = 6
        ORDER BY contract_month LIMIT 1
        """,
        (trade_date,),
    )
    underlying = float(fut[0]["close_price"]) if fut and fut[0].get("close_price") else None
    if underlying is None:
        return {"trade_date": str(trade_date), "underlying": None, "strikes": [], "summary": None}

    strikes = query(
        """
        SELECT strike_price, call_put, open_interest, avg_cost, contract_month
        FROM options_strike_avg_cost
        WHERE trade_date = %s AND open_interest >= %s AND avg_cost IS NOT NULL
        """,
        (trade_date, min_oi),
    )

    # 計算每履約價 P&L
    enriched = []
    total_call_premium = 0.0  # 賣方收取權利金總額（口）
    total_put_premium = 0.0
    total_call_pnl = 0.0      # 賣方未實現 P&L 總額（口）
    total_put_pnl = 0.0
    for s in strikes:
        strike = float(s["strike_price"])
        oi = float(s["open_interest"])
        cost = float(s["avg_cost"])
        cp = s["call_put"]
        is_call = cp in ("C", "Call")
        if is_call:
            intrinsic = max(0.0, underlying - strike)
        else:
            intrinsic = max(0.0, strike - underlying)
        pnl_per_unit = cost - intrinsic
        pnl_total = pnl_per_unit * oi
        premium_total = cost * oi
        if is_call:
            total_call_premium += premium_total
            total_call_pnl += pnl_total
        else:
            total_put_premium += premium_total
            total_put_pnl += pnl_total
        enriched.append({
            "strike_price": strike,
            "call_put": "Call" if is_call else "Put",
            "open_interest": oi,
            "avg_cost": cost,
            "intrinsic": intrinsic,
            "pnl_per_unit": pnl_per_unit,
            "pnl_total": pnl_total,
            "premium_total": premium_total,
            "contract_month": s.get("contract_month"),
        })

    # 排序：按 |pnl_total| 降冪，前端取 top N
    enriched.sort(key=lambda x: abs(x["pnl_total"]), reverse=True)

    return {
        "trade_date": str(trade_date),
        "underlying": underlying,
        "summary": {
            "total_call_premium": total_call_premium,
            "total_put_premium": total_put_premium,
            "total_premium": total_call_premium + total_put_premium,
            "total_call_pnl": total_call_pnl,
            "total_put_pnl": total_put_pnl,
            "total_pnl": total_call_pnl + total_put_pnl,
            "call_strike_count": sum(1 for s in enriched if s["call_put"] == "Call"),
            "put_strike_count": sum(1 for s in enriched if s["call_put"] == "Put"),
        },
        "strikes": enriched,
    }


@router.get("/oi-change-ranking")
def get_oi_change_ranking(
    top_n: int = Query(default=10, ge=5, le=30),
    min_oi: int = Query(default=200, ge=0),
):
    """
    OI 變動排行（最新日 vs 前一交易日）。
    - 以最新 trade_date 的 near-monthly 合約為基準
    - 同合約月份下，每個（strike, call_put）計算 OI 變動量與變動率
    - 回傳 Call/Put 各自 Top N 增加 / Top N 減少
    """
    # 找最新日 + 最新日 near-month
    latest_row = query(
        """
        SELECT trade_date, MIN(contract_month) AS near_month
        FROM options_strike_avg_cost
        WHERE LENGTH(contract_month) = 6
          AND trade_date = (SELECT MAX(trade_date) FROM options_strike_avg_cost WHERE LENGTH(contract_month) = 6)
        GROUP BY trade_date
        """
    )
    if not latest_row:
        return {"latest_date": None, "prev_date": None, "near_month": None, "calls": {}, "puts": {}}
    latest_date = latest_row[0]["trade_date"]
    near_month = latest_row[0]["near_month"]

    # 找前一交易日（必須有同 near_month 的資料）
    prev_row = query(
        """
        SELECT MAX(trade_date) AS d
        FROM options_strike_avg_cost
        WHERE contract_month = %s AND trade_date < %s
        """,
        (near_month, latest_date),
    )
    if not prev_row or not prev_row[0]["d"]:
        return {"latest_date": str(latest_date), "prev_date": None, "near_month": near_month, "calls": {}, "puts": {}}
    prev_date = prev_row[0]["d"]

    # 期貨近月收盤（當日 spot 參考）
    fut = query(
        """
        SELECT close_price::FLOAT AS close_price FROM tx_futures_daily
        WHERE trade_date = %s AND session = '一般' AND LENGTH(contract_month) = 6
        ORDER BY contract_month LIMIT 1
        """,
        (latest_date,),
    )
    spot = fut[0]["close_price"] if fut else None

    # 兩日資料
    rows = query(
        """
        SELECT trade_date, strike_price::FLOAT AS strike_price, call_put,
               open_interest::BIGINT AS open_interest
        FROM options_strike_avg_cost
        WHERE contract_month = %s AND trade_date IN (%s, %s)
          AND open_interest IS NOT NULL
        """,
        (near_month, latest_date, prev_date),
    )

    # 建立索引：key=(strike, call_put) → {latest_oi, prev_oi}
    idx: dict[tuple, dict] = {}
    for r in rows:
        key = (r["strike_price"], r["call_put"])
        d = str(r["trade_date"])
        bucket = idx.setdefault(key, {})
        if d == str(latest_date):
            bucket["latest_oi"] = r["open_interest"]
        else:
            bucket["prev_oi"] = r["open_interest"]

    # 計算變動
    deltas: list[dict] = []
    for (strike, cp), v in idx.items():
        curr = v.get("latest_oi") or 0
        prev = v.get("prev_oi") or 0
        if max(curr, prev) < min_oi:
            continue
        delta = curr - prev
        delta_pct = (delta / prev * 100.0) if prev else None
        deltas.append({
            "strike_price": strike,
            "call_put": "Call" if cp in ("C", "Call") else "Put",
            "prev_oi": prev,
            "latest_oi": curr,
            "delta_oi": delta,
            "delta_pct": delta_pct,
            "moneyness": ((strike - spot) / spot * 100.0) if spot else None,  # 正=OTM Call / ITM Put
        })

    def _top(items, key, reverse):
        return sorted(items, key=lambda x: (x[key] is None, x[key]), reverse=reverse)[:top_n]

    calls = [d for d in deltas if d["call_put"] == "Call"]
    puts = [d for d in deltas if d["call_put"] == "Put"]

    return {
        "latest_date": str(latest_date),
        "prev_date": str(prev_date),
        "near_month": near_month,
        "spot": spot,
        "calls": {
            "top_increase": _top(calls, "delta_oi", reverse=True),
            "top_decrease": _top(calls, "delta_oi", reverse=False),
        },
        "puts": {
            "top_increase": _top(puts, "delta_oi", reverse=True),
            "top_decrease": _top(puts, "delta_oi", reverse=False),
        },
        "stats": {
            "total_call_delta": sum(d["delta_oi"] for d in calls),
            "total_put_delta": sum(d["delta_oi"] for d in puts),
            "call_strikes": len(calls),
            "put_strikes": len(puts),
        },
    }


@router.get("/max-pain-history")
def get_max_pain_history(days: int = Query(default=20, ge=10, le=90)):
    """
    Max Pain N 日漂移時序（讀取 market_max_pain 表，pipeline 已預計算）。
    - delta_pts = underlying - max_pain_strike（正：價格在痛點上方 / 負：下方）
    - pressure 分類：bullish_escape / pinning / bearish_escape
    - trend：underlying 與 max_pain 的距離是收斂（pinning）還是發散（breakout）
    """
    rows = query(
        """
        SELECT trade_date,
               max_pain_strike::FLOAT AS max_pain,
               underlying_price::FLOAT AS underlying,
               delta_pts::FLOAT AS delta_pts
        FROM market_max_pain
        WHERE trade_date >= (CURRENT_DATE - %s * INTERVAL '1 day')
          AND max_pain_strike IS NOT NULL
          AND underlying_price IS NOT NULL
        ORDER BY trade_date
        """,
        (days * 2,),
    )

    series: list[dict] = []
    for r in rows:
        mp = r["max_pain"]
        und = r["underlying"]
        # 覆寫：本端點統一採「現價 - 痛點」語意（正 = 價格在痛點上方）
        delta = (und - mp) if (und is not None and mp is not None) else None
        delta_pct = (delta / und * 100.0) if (delta is not None and und) else None
        series.append({
            "trade_date": str(r["trade_date"]),
            "max_pain": mp,
            "underlying": und,
            "delta_pts": delta,
            "delta_pct": delta_pct,
        })
    series = series[-days:]

    summary: dict = {}
    if len(series) >= 5:
        deltas = [s["delta_pts"] for s in series if s["delta_pts"] is not None]
        delta_pcts = [s["delta_pct"] for s in series if s["delta_pct"] is not None]
        abs_deltas = [abs(d) for d in deltas]
        pos = sum(1 for d in deltas if d > 0)
        neg = sum(1 for d in deltas if d < 0)
        avg_delta = sum(deltas) / len(deltas) if deltas else 0.0
        avg_abs_delta = sum(abs_deltas) / len(abs_deltas) if abs_deltas else 0.0

        latest = series[-1]
        latest_abs_pct = abs(latest["delta_pct"] or 0)

        # 當前壓力分類
        if latest_abs_pct < 0.5:
            pressure = "tight_pinning"  # 痛點拉力強
        elif (latest["delta_pct"] or 0) >= 1.5:
            pressure = "bullish_escape"  # 價格脫離痛點上行
        elif (latest["delta_pct"] or 0) <= -1.5:
            pressure = "bearish_escape"  # 價格脫離痛點下行
        elif (latest["delta_pct"] or 0) > 0:
            pressure = "above_pain_mild"
        else:
            pressure = "below_pain_mild"

        # 趨勢：比較前半段 vs 後半段的 |delta|
        mid = len(abs_deltas) // 2
        if mid >= 2:
            first_half_avg = sum(abs_deltas[:mid]) / mid
            last_half_avg = sum(abs_deltas[mid:]) / (len(abs_deltas) - mid)
            if last_half_avg < first_half_avg * 0.7:
                trend = "converging"  # Pin 吸力增強
            elif last_half_avg > first_half_avg * 1.3:
                trend = "diverging"   # 趨勢脫離
            else:
                trend = "stable"
        else:
            trend = "stable"

        summary = {
            "latest_date": latest["trade_date"],
            "latest_max_pain": latest["max_pain"],
            "latest_underlying": latest["underlying"],
            "latest_delta_pts": latest["delta_pts"],
            "latest_delta_pct": latest["delta_pct"],
            "days_above_pain": pos,
            "days_below_pain": neg,
            "avg_delta_pts": avg_delta,
            "avg_abs_delta_pts": avg_abs_delta,
            "pressure": pressure,
            "trend": trend,
        }

    return {"series": series, "summary": summary, "sample_days": len(series)}


@router.get("/atm-vol-proxy")
def get_atm_vol_proxy(days: int = Query(default=20, ge=10, le=90)):
    """
    ATM straddle cost / underlying 當作隱含波動率代理（台指 VIX-like）。
    - 每日取近月 monthly options（LENGTH(contract_month)=6）
    - ATM strike = 距當日近月期貨收盤最近的履約價（有 Call 也有 Put）
    - straddle = call_avg_cost + put_avg_cost
    - vol_ratio = straddle / underlying * 100 （%）
    回傳序列 + 當前百分位（相對近 N 日）+ 擴張/收縮分類
    """
    # 期貨近月收盤（每日最小 contract_month）
    fut_rows = query(
        """
        SELECT trade_date, close_price::FLOAT AS close_price FROM (
            SELECT trade_date, close_price,
                   ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY contract_month) AS rn
            FROM tx_futures_daily
            WHERE session = '一般' AND LENGTH(contract_month) = 6
              AND close_price IS NOT NULL
              AND trade_date >= (CURRENT_DATE - %s * INTERVAL '1 day')
        ) t WHERE rn = 1 ORDER BY trade_date
        """,
        (days * 2,),
    )
    fut_map = {str(r["trade_date"]): r["close_price"] for r in fut_rows}

    # 選擇權近月 monthly（LENGTH=6）所有履約價的 Call/Put avg_cost
    opt_rows = query(
        """
        SELECT trade_date, contract_month, strike_price::FLOAT AS strike_price,
               call_put, avg_cost::FLOAT AS avg_cost
        FROM options_strike_avg_cost
        WHERE LENGTH(contract_month) = 6
          AND avg_cost IS NOT NULL
          AND trade_date >= (CURRENT_DATE - %s * INTERVAL '1 day')
        """,
        (days * 2,),
    )

    # 按日分組；每日選最小 monthly 合約
    by_date: dict[str, dict[str, list[dict]]] = {}
    for r in opt_rows:
        d = str(r["trade_date"])
        m = r["contract_month"]
        by_date.setdefault(d, {}).setdefault(m, []).append(r)

    series: list[dict] = []
    for trade_date in sorted(fut_map.keys()):
        underlying = fut_map.get(trade_date)
        months_dict = by_date.get(trade_date) or {}
        if underlying is None or not months_dict:
            continue
        near_month = min(months_dict.keys())
        strikes_near = months_dict[near_month]

        # 整理 Call/Put 按 strike
        by_strike: dict[float, dict[str, float]] = {}
        for s in strikes_near:
            bucket = by_strike.setdefault(s["strike_price"], {})
            if s["call_put"] in ("C", "Call"):
                bucket["call"] = s["avg_cost"]
            else:
                bucket["put"] = s["avg_cost"]

        # 只保留 Call+Put 同時有的履約價
        pairs = [(k, v) for k, v in by_strike.items() if "call" in v and "put" in v]
        if not pairs:
            continue
        # 找 ATM：距 underlying 最近的 strike
        atm_strike, atm_vals = min(pairs, key=lambda x: abs(x[0] - underlying))
        straddle = atm_vals["call"] + atm_vals["put"]
        vol_ratio = straddle / underlying * 100.0 if underlying else 0.0

        series.append({
            "trade_date": trade_date,
            "underlying": underlying,
            "near_month": near_month,
            "atm_strike": atm_strike,
            "call_cost": atm_vals["call"],
            "put_cost": atm_vals["put"],
            "straddle": straddle,
            "vol_ratio": vol_ratio,
        })

    series = series[-days:]

    summary: dict = {}
    if len(series) >= 5:
        ratios = [s["vol_ratio"] for s in series]
        latest = series[-1]
        prev = series[-2] if len(series) >= 2 else None
        sorted_r = sorted(ratios)
        # 百分位
        rank = sum(1 for v in sorted_r if v <= latest["vol_ratio"])
        pct = rank / len(sorted_r) * 100.0
        # N 日平均
        avg = sum(ratios) / len(ratios)
        min_r = min(ratios)
        max_r = max(ratios)
        # 擴張/收縮
        if prev is not None:
            day_change = latest["vol_ratio"] - prev["vol_ratio"]
        else:
            day_change = 0.0
        if pct >= 85:
            state = "elevated"          # 恐慌區（波動率高）
        elif pct >= 60:
            state = "moderately_elevated"
        elif pct <= 15:
            state = "compressed"        # 極度平靜（盤整末期）
        elif pct <= 40:
            state = "moderately_low"
        else:
            state = "normal"
        summary = {
            "latest_date": latest["trade_date"],
            "latest_vol_ratio": latest["vol_ratio"],
            "latest_straddle": latest["straddle"],
            "latest_atm_strike": latest["atm_strike"],
            "latest_underlying": latest["underlying"],
            "latest_near_month": latest["near_month"],
            "percentile": pct,
            "avg_vol_ratio": avg,
            "min_vol_ratio": min_r,
            "max_vol_ratio": max_r,
            "day_change": day_change,
            "state": state,
        }

    return {"series": series, "summary": summary, "sample_days": len(series)}


@router.get("/night-gap-history")
def get_night_gap_history(days: int = Query(default=10, ge=5, le=60)):
    """
    夜盤 N 日缺口時序（日盤收盤 → 夜盤收盤）。
    - 取 contract_code='TX'、LENGTH(contract_month)=6、每日最小 contract_month（近月）
    - 日盤（一般） / 夜盤（盤後）兩個 session 各取近月收盤
    - gap = night_close - day_close
    - 統計：正/負缺口天數、平均缺口、趨勢、夜盤強度分類
    """
    rows = query(
        """
        WITH day_ranked AS (
            SELECT trade_date, contract_month, close_price,
                   ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY contract_month) AS rn
            FROM tx_futures_daily
            WHERE contract_code = 'TX' AND session = '一般'
              AND LENGTH(contract_month) = 6
              AND close_price IS NOT NULL
              AND trade_date >= (CURRENT_DATE - %s * INTERVAL '1 day')
        ),
        night_ranked AS (
            SELECT trade_date, contract_month, close_price, volume,
                   ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY contract_month) AS rn
            FROM tx_futures_daily
            WHERE contract_code = 'TX' AND session = '盤後'
              AND LENGTH(contract_month) = 6
              AND close_price IS NOT NULL
              AND trade_date >= (CURRENT_DATE - %s * INTERVAL '1 day')
        )
        SELECT d.trade_date,
               d.close_price::FLOAT AS day_close,
               n.close_price::FLOAT AS night_close,
               n.volume::BIGINT      AS night_volume
        FROM day_ranked d
        LEFT JOIN night_ranked n ON d.trade_date = n.trade_date AND n.rn = 1
        WHERE d.rn = 1
        ORDER BY d.trade_date
        """,
        (days * 2, days * 2),
    )

    series: list[dict] = []
    for r in rows:
        dc = r.get("day_close")
        nc = r.get("night_close")
        gap = None
        gap_pct = None
        if dc is not None and nc is not None:
            gap = nc - dc
            gap_pct = (gap / dc * 100.0) if dc else None
        series.append({
            "trade_date": str(r["trade_date"]),
            "day_close": dc,
            "night_close": nc,
            "night_volume": int(r["night_volume"]) if r.get("night_volume") is not None else None,
            "gap": gap,
            "gap_pct": gap_pct,
        })

    # 僅保留同時有日盤 + 夜盤的天數；取最後 N 日
    valid = [s for s in series if s["gap"] is not None]
    valid = valid[-days:]

    summary: dict = {}
    if len(valid) >= 2:
        gaps = [s["gap"] for s in valid]
        pos = sum(1 for g in gaps if g > 0)
        neg = sum(1 for g in gaps if g < 0)
        zero = len(gaps) - pos - neg
        avg_gap = sum(gaps) / len(gaps)
        avg_abs_gap = sum(abs(g) for g in gaps) / len(gaps)
        sum_gap = sum(gaps)

        # 夜盤強度分類：以近 N 日缺口總合 / avg_abs_gap 做標準化
        if avg_abs_gap > 0:
            strength_ratio = sum_gap / (avg_abs_gap * len(gaps))
        else:
            strength_ratio = 0.0
        if strength_ratio > 0.4:
            bias = "night_bullish_persistent"
        elif strength_ratio < -0.4:
            bias = "night_bearish_persistent"
        elif pos >= neg * 2:
            bias = "night_bullish_mild"
        elif neg >= pos * 2:
            bias = "night_bearish_mild"
        else:
            bias = "neutral"

        summary = {
            "latest_date": valid[-1]["trade_date"],
            "latest_gap": valid[-1]["gap"],
            "latest_gap_pct": valid[-1]["gap_pct"],
            "latest_night_volume": valid[-1]["night_volume"],
            "days_positive": pos,
            "days_negative": neg,
            "days_zero": zero,
            "avg_gap": avg_gap,
            "avg_abs_gap": avg_abs_gap,
            "sum_gap": sum_gap,
            "strength_ratio": strength_ratio,
            "bias": bias,
        }

    return {"series": valid, "summary": summary, "sample_days": len(valid)}


@router.get("/seller-pnl-timeseries")
def get_seller_pnl_timeseries(
    days: int = Query(default=7, ge=3, le=30),
    min_oi: int = Query(default=500, ge=100),
):
    """
    賣方 P&L N 日時序。每日以當日近月期貨收盤結算當日所有 OI >= min_oi 的履約價。
    - 拆 Call/Put 分別計算
    - 回傳序列 + summary（趨勢、變動量、盈虧天數）
    """
    fut = query(
        """
        SELECT trade_date, close_price::FLOAT AS close_price FROM (
            SELECT trade_date, close_price,
                   ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY contract_month) AS rn
            FROM tx_futures_daily
            WHERE session = '一般' AND LENGTH(contract_month) = 6
              AND close_price IS NOT NULL
              AND trade_date >= (CURRENT_DATE - %s * INTERVAL '1 day')
        ) t WHERE rn = 1 ORDER BY trade_date
        """,
        (days * 2,),
    )
    strikes = query(
        """
        SELECT trade_date, strike_price, call_put, open_interest, avg_cost
        FROM options_strike_avg_cost
        WHERE trade_date >= (CURRENT_DATE - %s * INTERVAL '1 day')
          AND open_interest >= %s
          AND avg_cost IS NOT NULL
        """,
        (days * 2, min_oi),
    )

    by_date: dict[str, list[dict]] = {}
    for s in strikes:
        by_date.setdefault(str(s["trade_date"]), []).append(s)

    fut_map = {str(r["trade_date"]): r["close_price"] for r in fut}

    series: list[dict] = []
    for trade_date in sorted(fut_map.keys()):
        underlying = fut_map.get(trade_date)
        if underlying is None or trade_date not in by_date:
            continue
        call_pnl = put_pnl = call_prem = put_prem = 0.0
        for s in by_date[trade_date]:
            strike = float(s["strike_price"])
            oi = float(s["open_interest"])
            cost = float(s["avg_cost"])
            is_call = s["call_put"] in ("C", "Call")
            intrinsic = max(0.0, underlying - strike) if is_call else max(0.0, strike - underlying)
            pnl = (cost - intrinsic) * oi
            prem = cost * oi
            if is_call:
                call_pnl += pnl
                call_prem += prem
            else:
                put_pnl += pnl
                put_prem += prem
        series.append({
            "trade_date": trade_date,
            "underlying": underlying,
            "call_pnl": call_pnl,
            "put_pnl": put_pnl,
            "total_pnl": call_pnl + put_pnl,
            "call_premium": call_prem,
            "put_premium": put_prem,
            "total_premium": call_prem + put_prem,
        })

    series = series[-days:]

    summary: dict = {}
    if len(series) >= 2:
        latest = series[-1]
        first = series[0]
        change = latest["total_pnl"] - first["total_pnl"]
        # 趨勢分類
        if change > 100_000:
            trend = "improving"
        elif change < -100_000:
            trend = "deteriorating"
        else:
            trend = "flat"
        summary = {
            "latest_date": latest["trade_date"],
            "latest_underlying": latest["underlying"],
            "latest_total_pnl": latest["total_pnl"],
            "latest_call_pnl": latest["call_pnl"],
            "latest_put_pnl": latest["put_pnl"],
            "first_total_pnl": first["total_pnl"],
            "total_pnl_change": change,
            "days_profit": sum(1 for s in series if s["total_pnl"] > 0),
            "days_loss": sum(1 for s in series if s["total_pnl"] < 0),
            "trend": trend,
            "min_total_pnl": min(s["total_pnl"] for s in series),
            "max_total_pnl": max(s["total_pnl"] for s in series),
        }

    return {
        "series": series,
        "summary": summary,
        "sample_days": len(series),
        "min_oi": min_oi,
    }


@router.get("/dealer-map-history")
def get_dealer_map_history(
    days: int = Query(default=5, ge=2, le=20),
    end_date: Optional[date] = Query(default=None),
):
    """
    莊家地圖 5～20 日時序演化 — 用於觀察賣方壓力/支撐帶的漂移軌跡。

    回傳：每個交易日的 Top OI 履約價（Call/Put 分開），
    前端可依此繪製「氣泡 timeline」顯示壓力帶隨時間的變化。
    """
    if end_date is None:
        rows = query("SELECT MAX(trade_date) AS d FROM options_strike_avg_cost")
        end_date = rows[0]["d"] if rows and rows[0]["d"] else date.today() - timedelta(days=1)

    # 抓近 N 個交易日（由資料決定，不用 calendar day）
    date_rows = query(
        """
        SELECT DISTINCT trade_date FROM options_strike_avg_cost
        WHERE trade_date <= %s
        ORDER BY trade_date DESC LIMIT %s
        """,
        (end_date, days),
    )
    dates = [r["trade_date"] for r in date_rows]
    if not dates:
        return {"dates": [], "strikes": [], "underlying_by_date": {}}

    start_d = min(dates)

    # 每日的 Call/Put Top 履約價（依 OI 排序取前 10，過濾雜訊）
    strikes = query(
        """
        SELECT trade_date, strike_price, call_put, open_interest, delta_oi, avg_cost
        FROM options_strike_avg_cost
        WHERE trade_date BETWEEN %s AND %s
          AND open_interest > 1000
        ORDER BY trade_date, open_interest DESC
        """,
        (start_d, end_date),
    )

    # 每日的期貨現價（近月一般盤收盤）
    fut_rows = query(
        """
        SELECT trade_date, close_price
        FROM tx_futures_daily
        WHERE trade_date BETWEEN %s AND %s
          AND session = '一般'
          AND LENGTH(contract_month) = 6
          AND contract_month = (
            SELECT MIN(contract_month) FROM tx_futures_daily f2
            WHERE f2.trade_date = tx_futures_daily.trade_date
              AND LENGTH(f2.contract_month) = 6
          )
        """,
        (start_d, end_date),
    )
    underlying_by_date = {str(r["trade_date"]): float(r["close_price"]) for r in fut_rows if r.get("close_price")}

    return {
        "dates": [str(d) for d in sorted(dates)],
        "strikes": strikes,
        "underlying_by_date": underlying_by_date,
    }


@router.get("/oi-structure")
def get_oi_structure(
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    limit: int = Query(default=60, le=500),
):
    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(days=90)
    return query(
        """
        SELECT * FROM market_oi_structure
        WHERE trade_date BETWEEN %s AND %s
        ORDER BY trade_date DESC
        LIMIT %s
        """,
        (start, end, limit),
    )


@router.get("/night-session")
def get_night_session(
    trade_date: Optional[date] = Query(default=None),
):
    """
    夜盤狀況 — TAIFEX 夜盤 (session='盤後') 的 TX 近月收盤、成交量、
    與當日日盤收盤的缺口。若未指定日期則取最新有 '盤後' 資料的交易日。
    """
    if trade_date is None:
        rows = query(
            "SELECT MAX(trade_date) AS d FROM tx_futures_daily WHERE session = '盤後'"
        )
        trade_date = rows[0]["d"] if rows and rows[0]["d"] else date.today() - timedelta(days=1)

    # 近月合約（YYYYMM，LENGTH=6、非價差）
    day = query(
        """
        SELECT contract_month, open_price, high_price, low_price, close_price, volume
        FROM tx_futures_daily
        WHERE trade_date = %s AND contract_code = 'TX' AND session = '一般'
          AND LENGTH(contract_month) = 6
        ORDER BY contract_month ASC LIMIT 1
        """,
        (trade_date,),
    )
    night = query(
        """
        SELECT contract_month, open_price, high_price, low_price, close_price, volume
        FROM tx_futures_daily
        WHERE trade_date = %s AND contract_code = 'TX' AND session = '盤後'
          AND LENGTH(contract_month) = 6
        ORDER BY contract_month ASC LIMIT 1
        """,
        (trade_date,),
    )

    # 前一交易日日盤收盤（用來計算『日盤→今日夜盤』整段變化）
    prev_day = query(
        """
        SELECT trade_date, close_price FROM tx_futures_daily
        WHERE trade_date < %s AND contract_code = 'TX' AND session = '一般'
          AND LENGTH(contract_month) = 6
        ORDER BY trade_date DESC, contract_month ASC LIMIT 1
        """,
        (trade_date,),
    )

    # 夜盤選擇權成交量統計（粗略觀察夜盤活躍度）
    opt_night = query(
        """
        SELECT COUNT(*) AS rows_cnt,
               SUM(volume)::BIGINT AS total_volume,
               SUM(CASE WHEN call_put IN ('C','Call') THEN volume ELSE 0 END)::BIGINT AS call_volume,
               SUM(CASE WHEN call_put IN ('P','Put')  THEN volume ELSE 0 END)::BIGINT AS put_volume
        FROM txo_options_daily
        WHERE trade_date = %s AND session = '盤後'
        """,
        (trade_date,),
    )

    def _f(v):
        return float(v) if v is not None else None

    day_close = _f(day[0]["close_price"]) if day else None
    night_close = _f(night[0]["close_price"]) if night else None
    prev_close = _f(prev_day[0]["close_price"]) if prev_day else None

    gap_day_to_night = (night_close - day_close) if (day_close is not None and night_close is not None) else None
    gap_prev_to_night = (night_close - prev_close) if (prev_close is not None and night_close is not None) else None

    return {
        "trade_date": str(trade_date),
        "day_session": {
            "contract_month": day[0]["contract_month"] if day else None,
            "open": _f(day[0]["open_price"]) if day else None,
            "high": _f(day[0]["high_price"]) if day else None,
            "low": _f(day[0]["low_price"]) if day else None,
            "close": day_close,
            "volume": int(day[0]["volume"]) if day and day[0].get("volume") is not None else None,
        } if day else None,
        "night_session": {
            "contract_month": night[0]["contract_month"] if night else None,
            "open": _f(night[0]["open_price"]) if night else None,
            "high": _f(night[0]["high_price"]) if night else None,
            "low": _f(night[0]["low_price"]) if night else None,
            "close": night_close,
            "volume": int(night[0]["volume"]) if night and night[0].get("volume") is not None else None,
        } if night else None,
        "prev_day_close": {
            "trade_date": str(prev_day[0]["trade_date"]) if prev_day else None,
            "close": prev_close,
        } if prev_day else None,
        "gap_day_to_night": gap_day_to_night,
        "gap_day_to_night_pct": (gap_day_to_night / day_close * 100) if (gap_day_to_night is not None and day_close) else None,
        "gap_prev_to_night": gap_prev_to_night,
        "options_night_summary": opt_night[0] if opt_night else None,
    }


@router.get("/pcr-percentile")
def get_pcr_percentile(
    days: int = Query(default=180, ge=30, le=720),
):
    """
    PCR（Put/Call Ratio）歷史區間分位 + 反指標警示。
    - 回傳近 N 日 pc_oi_ratio、pc_vol_ratio 時序
    - 計算最新值在歷史樣本中的百分位
    - 分位 > 85 = 極度悲觀（contrarian 看多）
    - 分位 < 15 = 極度樂觀（contrarian 看空）
    """
    rows = query(
        """
        SELECT trade_date,
               pc_oi_ratio::FLOAT AS pc_oi_ratio,
               pc_vol_ratio::FLOAT AS pc_vol_ratio
        FROM put_call_ratio
        WHERE trade_date >= (CURRENT_DATE - %s * INTERVAL '1 day')
          AND pc_oi_ratio IS NOT NULL
        ORDER BY trade_date
        """,
        (days,),
    )
    if not rows:
        return {"series": [], "stats": {}}

    series = [{
        "trade_date": str(r["trade_date"]),
        "pc_oi_ratio": r["pc_oi_ratio"],
        "pc_vol_ratio": r["pc_vol_ratio"],
    } for r in rows]

    def _percentile_rank(values: list[float], x: float) -> float:
        if not values:
            return 50.0
        s = sorted(values)
        below = sum(1 for v in s if v < x)
        equal = sum(1 for v in s if v == x)
        return (below + 0.5 * equal) / len(s) * 100

    def _classify(p: float) -> str:
        if p >= 85:
            return "extreme_fear"   # 極度悲觀（contrarian 看多）
        if p >= 70:
            return "fear"
        if p <= 15:
            return "extreme_greed"  # 極度樂觀（contrarian 看空）
        if p <= 30:
            return "greed"
        return "neutral"

    oi_vals = [r["pc_oi_ratio"] for r in rows if r["pc_oi_ratio"] is not None]
    vol_vals = [r["pc_vol_ratio"] for r in rows if r["pc_vol_ratio"] is not None]

    latest_oi = rows[-1]["pc_oi_ratio"]
    latest_vol = rows[-1]["pc_vol_ratio"]

    oi_pct = _percentile_rank(oi_vals, latest_oi) if latest_oi is not None else None
    vol_pct = _percentile_rank(vol_vals, latest_vol) if latest_vol is not None else None

    def _band(vals: list[float], q: float) -> float:
        if not vals:
            return 0.0
        s = sorted(vals)
        idx = int(q / 100 * (len(s) - 1))
        return s[idx]

    stats = {
        "latest_date": str(rows[-1]["trade_date"]),
        "latest_pc_oi": latest_oi,
        "latest_pc_vol": latest_vol,
        "pc_oi_percentile": oi_pct,
        "pc_vol_percentile": vol_pct,
        "pc_oi_state": _classify(oi_pct) if oi_pct is not None else None,
        "pc_vol_state": _classify(vol_pct) if vol_pct is not None else None,
        "pc_oi_p10": _band(oi_vals, 10),
        "pc_oi_p50": _band(oi_vals, 50),
        "pc_oi_p90": _band(oi_vals, 90),
        "sample_days": len(series),
    }

    return {"series": series, "stats": stats}


@router.get("/large-trader-watch")
def get_large_trader_watch(
    days: int = Query(default=7, ge=3, le=60),
    month_scope: str = Query(default="近月"),
):
    """
    大額交易人動向 — 特定法人（前 5/10 大戶）net position 時序。
    month_scope='近月' 取近月合約（trader_type 含 YYYYMM 的最小月份 + 特定法人）
    - TX: 近月 net = long - short
    - TXO: 買權 net、賣權 net（近月）
    - 也回傳全體交易人作對照
    """
    # 用近月 contract_month 字串匹配（trader_type 格式 '202605-特定法人' 或 '買權-202605-特定法人'）
    # 先查最新交易日的近月 contract_month
    latest_month_rows = query(
        """
        SELECT MIN(contract_month) AS near_month
        FROM tx_futures_daily
        WHERE session = '一般' AND LENGTH(contract_month) = 6
          AND trade_date = (SELECT MAX(trade_date) FROM tx_futures_daily WHERE session='一般')
        """
    )
    near_month = latest_month_rows[0]["near_month"] if latest_month_rows else None

    if not near_month:
        return {"series": [], "stats": {}, "near_month": None}

    # 查 large_trader_positions，篩含 near_month 的 trader_type
    rows = query(
        """
        SELECT trade_date, contract_code, trader_type,
               long_position, short_position, market_oi
        FROM large_trader_positions
        WHERE trade_date >= (CURRENT_DATE - %s * INTERVAL '1 day')
          AND trader_type LIKE %s
        ORDER BY trade_date
        """,
        (days * 2, f"%{near_month}%"),  # 多查一點防假日
    )

    # 分類：TX 特定法人 / TX 全體 / TXO 買權 特定 / TXO 買權 全體 / TXO 賣權 特定 / TXO 賣權 全體
    by_date: dict[str, dict] = {}
    for r in rows:
        d = str(r["trade_date"])
        tt = r["trader_type"]
        bucket = by_date.setdefault(d, {})
        long_p = int(r["long_position"] or 0)
        short_p = int(r["short_position"] or 0)
        net = long_p - short_p
        if r["contract_code"] == "TX" and "特定法人" in tt:
            bucket["tx_specific_net"] = net
            bucket["tx_specific_long"] = long_p
            bucket["tx_specific_short"] = short_p
        elif r["contract_code"] == "TX" and "全體交易人" in tt:
            bucket["tx_total_net"] = net
        elif r["contract_code"] == "TXO" and "買權" in tt and "特定法人" in tt:
            bucket["txo_call_specific_net"] = net
        elif r["contract_code"] == "TXO" and "買權" in tt and "全體交易人" in tt:
            bucket["txo_call_total_net"] = net
        elif r["contract_code"] == "TXO" and "賣權" in tt and "特定法人" in tt:
            bucket["txo_put_specific_net"] = net
        elif r["contract_code"] == "TXO" and "賣權" in tt and "全體交易人" in tt:
            bucket["txo_put_total_net"] = net

    all_dates = sorted(by_date.keys())[-days:]
    series = [{"trade_date": d, **by_date.get(d, {})} for d in all_dates]

    stats = {}
    if series:
        latest = series[-1]
        stats = {
            "latest_date": latest["trade_date"],
            "tx_specific_net": latest.get("tx_specific_net"),
            "txo_call_specific_net": latest.get("txo_call_specific_net"),
            "txo_put_specific_net": latest.get("txo_put_specific_net"),
            "near_month": near_month,
        }
        # 期權淨多空傾向：特定法人 Put net > 0 且 Call net < 0 = 看空/避險
        c = stats["txo_call_specific_net"]
        p = stats["txo_put_specific_net"]
        if c is not None and p is not None:
            if p > 0 and c < 0:
                stats["options_lean"] = "bearish_hedge"
            elif p < 0 and c > 0:
                stats["options_lean"] = "bullish"
            elif p > 0 and c > 0:
                stats["options_lean"] = "long_vol"
            elif p < 0 and c < 0:
                stats["options_lean"] = "short_vol"
            else:
                stats["options_lean"] = "neutral"

    return {
        "near_month": near_month,
        "series": series,
        "stats": stats,
    }


@router.get("/institutional-divergence")
def get_institutional_divergence(
    days: int = Query(default=30, ge=10, le=120),
):
    """
    法人 net_oi 30 日時序 vs 指數（近月 TX 收盤）走勢 + 背離偵測。
    背離邏輯：取前後 5 日平均變化方向；若方向相反則為背離。
    - index 上升 + 外資 net_oi 下降 = bearish divergence（負背離，派發）
    - index 下降 + 外資 net_oi 上升 = bullish divergence（正背離，接盤）
    - 同向 / 平盤 = neutral
    """
    # 指數近月 TX 收盤（session='一般'，取每日最小 contract_month）
    idx_rows = query(
        """
        WITH ranked AS (
            SELECT trade_date, contract_month, close_price,
                   ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY contract_month ASC) AS rn
            FROM tx_futures_daily
            WHERE contract_code = 'TX' AND session = '一般'
              AND LENGTH(contract_month) = 6
              AND close_price IS NOT NULL
              AND trade_date >= (CURRENT_DATE - %s * INTERVAL '1 day')
        )
        SELECT trade_date, close_price::FLOAT AS close
        FROM ranked WHERE rn = 1
        ORDER BY trade_date
        """,
        (days * 2,),  # 多查一點以防假日間隔
    )
    # 法人 net_oi（臺股期貨）
    inst_rows = query(
        """
        SELECT trade_date, institution_type, net_oi
        FROM institutional_futures
        WHERE contract_code = '臺股期貨'
          AND trade_date >= (CURRENT_DATE - %s * INTERVAL '1 day')
        ORDER BY trade_date
        """,
        (days * 2,),
    )

    # 以指數可用日期為基準，對齊法人資料
    idx_by_date = {str(r["trade_date"]): r["close"] for r in idx_rows}
    inst_by_date: dict[str, dict] = {}
    for r in inst_rows:
        d = str(r["trade_date"])
        bucket = inst_by_date.setdefault(d, {})
        bucket[r["institution_type"]] = int(r["net_oi"]) if r["net_oi"] is not None else None

    # 保留同時有指數 + 三法人資料的日期；取最後 N 日
    common_dates = sorted([d for d in idx_by_date if d in inst_by_date])
    common_dates = common_dates[-days:]

    series = []
    for d in common_dates:
        inst = inst_by_date.get(d, {})
        series.append({
            "trade_date": d,
            "index_close": idx_by_date.get(d),
            "foreign_net_oi": inst.get("外資及陸資"),
            "trust_net_oi": inst.get("投信"),
            "dealer_net_oi": inst.get("自營商"),
        })

    def _divergence(first_half_avg, second_half_avg, first_idx, second_idx):
        if first_half_avg is None or second_half_avg is None or first_idx is None or second_idx is None:
            return "insufficient_data", 0.0
        inst_delta = second_half_avg - first_half_avg
        idx_delta = second_idx - first_idx
        if abs(inst_delta) < 1 or abs(idx_delta) < 1:
            return "neutral", 0.0
        if idx_delta > 0 and inst_delta < 0:
            return "bearish", abs(inst_delta)  # 指數升、法人減 = 派發
        if idx_delta < 0 and inst_delta > 0:
            return "bullish", abs(inst_delta)  # 指數跌、法人加 = 接盤
        return "neutral", 0.0

    # 前 5 日 vs 後 5 日（若樣本夠）
    divergence = {}
    if len(series) >= 10:
        first5 = series[:5]
        last5 = series[-5:]
        idx_first = sum(r["index_close"] for r in first5 if r["index_close"] is not None) / 5
        idx_last = sum(r["index_close"] for r in last5 if r["index_close"] is not None) / 5
        for key, label in [("foreign_net_oi", "foreign"), ("trust_net_oi", "trust"), ("dealer_net_oi", "dealer")]:
            vals_f = [r[key] for r in first5 if r[key] is not None]
            vals_l = [r[key] for r in last5 if r[key] is not None]
            if vals_f and vals_l:
                fa = sum(vals_f) / len(vals_f)
                la = sum(vals_l) / len(vals_l)
                state, mag = _divergence(fa, la, idx_first, idx_last)
                divergence[label] = {
                    "state": state,
                    "first5_avg_net_oi": fa,
                    "last5_avg_net_oi": la,
                    "inst_delta": la - fa,
                    "magnitude": mag,
                }
        divergence["_index"] = {"first5_avg": idx_first, "last5_avg": idx_last, "idx_delta": idx_last - idx_first}

    return {
        "series": series,
        "divergence": divergence,
        "sample_days": len(series),
    }


@router.get("/institutional-momentum")
def get_institutional_momentum(
    days: int = Query(default=10, ge=5, le=30),
):
    """
    三大法人 N 日 net_oi 動能排行。
    - 臺股期貨 contract_code，取最近 N 個交易日
    - 每家機構計算：first / last / net_change / avg_daily_change / std / momentum_z
    - 方向分類：accumulating_long / reducing_long / accumulating_short / reducing_short
                / flipping_to_long / flipping_to_short / neutral
    - 依 abs(net_change) 排名 1-3
    """
    rows = query(
        """
        SELECT trade_date, institution_type, net_oi
        FROM institutional_futures
        WHERE contract_code = '臺股期貨'
          AND trade_date >= (CURRENT_DATE - (%s * 2) * INTERVAL '1 day')
          AND net_oi IS NOT NULL
        ORDER BY trade_date
        """,
        (days,),
    )

    by_inst: dict[str, list[dict]] = {}
    for r in rows:
        by_inst.setdefault(r["institution_type"], []).append({
            "trade_date": str(r["trade_date"]),
            "net_oi": int(r["net_oi"]),
        })

    def _classify(first: int, last: int) -> str:
        if first is None or last is None:
            return "insufficient_data"
        if abs(last - first) < 200:
            return "neutral"
        if first >= 0 and last >= 0:
            return "accumulating_long" if last > first else "reducing_long"
        if first <= 0 and last <= 0:
            return "accumulating_short" if last < first else "reducing_short"
        if first < 0 and last > 0:
            return "flipping_to_long"
        if first > 0 and last < 0:
            return "flipping_to_short"
        return "neutral"

    results: list[dict] = []
    name_map = {"外資及陸資": "foreign", "投信": "trust", "自營商": "dealer"}
    for inst_zh, key in name_map.items():
        raw = by_inst.get(inst_zh, [])
        series = raw[-days:] if len(raw) >= days else raw
        if len(series) < 2:
            results.append({
                "institution": key,
                "institution_zh": inst_zh,
                "series": series,
                "first_net_oi": None, "last_net_oi": None,
                "net_change": 0, "avg_daily_change": 0.0,
                "std_daily_change": 0.0, "momentum_z": 0.0,
                "direction": "insufficient_data",
            })
            continue
        first_v = series[0]["net_oi"]
        last_v = series[-1]["net_oi"]
        deltas = [series[i]["net_oi"] - series[i - 1]["net_oi"] for i in range(1, len(series))]
        avg_d = sum(deltas) / len(deltas) if deltas else 0.0
        if len(deltas) >= 2:
            mean = avg_d
            var = sum((x - mean) ** 2 for x in deltas) / (len(deltas) - 1)
            std = var ** 0.5
        else:
            std = 0.0
        mom_z = (avg_d / std) if std > 0 else 0.0
        results.append({
            "institution": key,
            "institution_zh": inst_zh,
            "series": series,
            "first_net_oi": first_v,
            "last_net_oi": last_v,
            "net_change": last_v - first_v,
            "avg_daily_change": avg_d,
            "std_daily_change": std,
            "momentum_z": mom_z,
            "direction": _classify(first_v, last_v),
        })

    # 依 abs(net_change) 排名
    sorted_by_mag = sorted(results, key=lambda r: abs(r.get("net_change") or 0), reverse=True)
    for i, r in enumerate(sorted_by_mag):
        r["rank"] = i + 1

    # 取得共同最新交易日
    latest_date = None
    for r in results:
        if r["series"]:
            d = r["series"][-1]["trade_date"]
            if latest_date is None or d > latest_date:
                latest_date = d

    return {
        "latest_date": latest_date,
        "window_days": days,
        "institutions": results,
    }


@router.get("/calendar-spread")
def get_calendar_spread(
    days: int = Query(default=30, ge=5, le=180),
):
    """
    台指期貨近月 vs 次月 spread（跨期價差）時序。
    - 取 contract_code='TX'、session='一般'、LENGTH(contract_month)=6
    - 對每個 trade_date 取最小兩個 contract_month → 視為近月/次月
    - spread = near_close - next_close
    - contango (spread < 0，次月高於近月) / backwardation (spread > 0，近月高於次月)
    回傳：近 N 日 spread 時序 + 當前 z-score + 敘述性統計
    """
    rows = query(
        """
        WITH ranked AS (
            SELECT trade_date, contract_month, close_price,
                   ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY contract_month ASC) AS rn
            FROM tx_futures_daily
            WHERE contract_code = 'TX' AND session = '一般'
              AND LENGTH(contract_month) = 6
              AND close_price IS NOT NULL
              AND trade_date >= (CURRENT_DATE - (%s * 2) * INTERVAL '1 day')
        )
        SELECT trade_date,
               MAX(CASE WHEN rn = 1 THEN contract_month END) AS near_month,
               MAX(CASE WHEN rn = 1 THEN close_price END)::FLOAT AS near_close,
               MAX(CASE WHEN rn = 2 THEN contract_month END) AS next_month,
               MAX(CASE WHEN rn = 2 THEN close_price END)::FLOAT AS next_close
        FROM ranked
        WHERE rn <= 2
        GROUP BY trade_date
        HAVING MAX(CASE WHEN rn = 2 THEN close_price END) IS NOT NULL
        ORDER BY trade_date DESC
        LIMIT %s
        """,
        (days, days),
    )
    # 反轉為時間順序
    series = list(reversed(rows))
    spreads = []
    for r in series:
        nc = r.get("near_close")
        nx = r.get("next_close")
        if nc is None or nx is None:
            continue
        spread = nc - nx
        spreads.append({
            "trade_date": str(r["trade_date"]),
            "near_month": r["near_month"],
            "near_close": nc,
            "next_month": r["next_month"],
            "next_close": nx,
            "spread": spread,
            "spread_pct": (spread / nc * 100) if nc else None,
        })

    # 統計（z-score）
    stats = None
    if spreads:
        vals = [s["spread"] for s in spreads]
        n = len(vals)
        mean = sum(vals) / n
        var = sum((v - mean) ** 2 for v in vals) / n if n > 0 else 0
        std = var ** 0.5
        latest = vals[-1]
        z = ((latest - mean) / std) if std > 0 else 0
        state = "contango" if latest < 0 else ("backwardation" if latest > 0 else "flat")
        stats = {
            "latest_spread": latest,
            "mean": mean,
            "std": std,
            "z_score": z,
            "state": state,
            "samples": n,
            "min": min(vals),
            "max": max(vals),
        }

    return {
        "series": spreads,
        "stats": stats,
    }


def _third_wednesday(year: int, month: int) -> date:
    """回傳該月第三個星期三（台指月選擇權結算日）。"""
    first = date(year, month, 1)
    # weekday(): Mon=0, Wed=2
    offset = (2 - first.weekday()) % 7
    return date(year, month, 1 + offset + 14)


@router.get("/settlement-history")
def get_settlement_history(
    lookback_months: int = Query(default=12, ge=2, le=24),
):
    """
    結算日 pinning 歷史分析 — 驗證「台指收斂到大倉位履約價」假說。

    對過去 N 個月的第三個星期三（月結算日），回傳：
      - underlying_close：當日台指近月期貨收盤
      - max_pain_strike：當日 Max Pain 履約價
      - top_call_oi_strike / top_put_oi_strike：當月到期合約最大 OI 履約價
      - 各類距離（絕對點數 + %）

    前端可用來計算 Max Pain 預測準確度、Top OI pinning 強度。
    """
    today = date.today()
    # 產生最近 N 個月的第三個星期三
    candidates: list[date] = []
    y, m = today.year, today.month
    for _ in range(lookback_months + 1):
        t = _third_wednesday(y, m)
        if t <= today:
            candidates.append(t)
        # 退一個月
        if m == 1:
            y -= 1
            m = 12
        else:
            m -= 1
    candidates.sort()

    if not candidates:
        return {"settlements": [], "summary": None}

    results = []
    for t in candidates:
        expiring_month = f"{t.year}{t.month:02d}"  # YYYYMM，6 字元 = 月選

        # 1. 當日期貨收盤（若該日非交易日，退到最近一個有資料的交易日）
        fut = query(
            """
            SELECT trade_date, close_price FROM tx_futures_daily
            WHERE trade_date <= %s AND session = '一般'
              AND LENGTH(contract_month) = 6
            ORDER BY trade_date DESC, contract_month ASC
            LIMIT 1
            """,
            (t,),
        )
        if not fut or not fut[0].get("close_price"):
            continue
        actual_trade_date = fut[0]["trade_date"]
        # 差距 > 5 天視為無效資料（避免日期錯位）
        if (t - actual_trade_date).days > 5:
            continue
        underlying_close = float(fut[0]["close_price"])

        # 2. Max Pain
        mp = query(
            "SELECT max_pain_strike FROM market_max_pain WHERE trade_date = %s",
            (actual_trade_date,),
        )
        max_pain_strike = float(mp[0]["max_pain_strike"]) if mp and mp[0].get("max_pain_strike") else None

        # 3. 到期合約的 Top OI Call / Put（只看該月合約，非週選）
        strikes = query(
            """
            SELECT strike_price, call_put, open_interest
            FROM options_strike_avg_cost
            WHERE trade_date = %s AND contract_month = %s AND open_interest > 0
            ORDER BY open_interest DESC
            """,
            (actual_trade_date, expiring_month),
        )
        top_call = None
        top_put = None
        for s in strikes:
            cp = s["call_put"]
            if cp in ("C", "Call") and top_call is None:
                top_call = float(s["strike_price"])
            elif cp in ("P", "Put") and top_put is None:
                top_put = float(s["strike_price"])
            if top_call is not None and top_put is not None:
                break

        def _delta(a, b):
            if a is None or b is None:
                return None, None
            d = a - b
            pct = (d / b * 100.0) if b else None
            return d, pct

        d_mp, pct_mp = _delta(underlying_close, max_pain_strike)
        d_c, pct_c = _delta(underlying_close, top_call)
        d_p, pct_p = _delta(underlying_close, top_put)

        results.append({
            "settlement_date": str(t),
            "trade_date": str(actual_trade_date),
            "expiring_month": expiring_month,
            "underlying_close": underlying_close,
            "max_pain_strike": max_pain_strike,
            "top_call_oi_strike": top_call,
            "top_put_oi_strike": top_put,
            "delta_vs_max_pain": d_mp,
            "delta_vs_max_pain_pct": pct_mp,
            "delta_vs_top_call": d_c,
            "delta_vs_top_call_pct": pct_c,
            "delta_vs_top_put": d_p,
            "delta_vs_top_put_pct": pct_p,
        })

    # 統計摘要
    mp_deltas = [abs(r["delta_vs_max_pain"]) for r in results if r["delta_vs_max_pain"] is not None]
    mp_pcts = [abs(r["delta_vs_max_pain_pct"]) for r in results if r["delta_vs_max_pain_pct"] is not None]
    summary = None
    if results:
        summary = {
            "count": len(results),
            "avg_abs_delta_vs_max_pain": sum(mp_deltas) / len(mp_deltas) if mp_deltas else None,
            "avg_abs_pct_vs_max_pain": sum(mp_pcts) / len(mp_pcts) if mp_pcts else None,
            "max_abs_delta_vs_max_pain": max(mp_deltas) if mp_deltas else None,
            "hit_within_1pct": sum(1 for p in mp_pcts if p <= 1.0),
            "hit_within_2pct": sum(1 for p in mp_pcts if p <= 2.0),
        }

    return {
        "settlements": results,
        "summary": summary,
    }


@router.get("/seller-exposure-bucketed")
def get_seller_exposure_bucketed():
    """
    賣方 ATM/OTM 分層壓力 — 近月月選當日依 moneyness 分五格匯總 Call/Put 賣方敞口。
    - 分格：deep_itm (|m|>=3% ITM) / itm / atm (|m|<0.5%) / otm / deep_otm
    - 每格：total_oi、sum_premium_received (OI×avg_cost)、sum_mark_cost (OI×daily_price)、unrealized_pnl_points
    - 一單位 P&L = (avg_cost - daily_price)，× 50 元/點 為實際金額
    """
    # 取最新交易日
    latest = query(
        "SELECT MAX(trade_date) AS d FROM options_strike_avg_cost",
        (),
    )
    if not latest or not latest[0].get("d"):
        return {"error": "no_data"}
    td = latest[0]["d"]

    # 找近月月選（LENGTH=6，最高 OI 者）
    near = query(
        """
        SELECT contract_month, SUM(open_interest) AS tot_oi
        FROM options_strike_avg_cost
        WHERE trade_date = %s AND LENGTH(contract_month) = 6
        GROUP BY contract_month
        ORDER BY tot_oi DESC
        LIMIT 1
        """,
        (td,),
    )
    if not near:
        return {"error": "no_monthly_contract"}
    contract_month = near[0]["contract_month"]

    # 取該日期貨近月收盤作為 spot
    fut = query(
        """
        SELECT close_price FROM tx_futures_daily
        WHERE trade_date = %s AND session = '一般' AND contract_code = 'TX'
          AND LENGTH(contract_month) = 6
        ORDER BY volume DESC NULLS LAST
        LIMIT 1
        """,
        (td,),
    )
    if not fut or not fut[0].get("close_price"):
        return {"error": "no_spot"}
    spot = float(fut[0]["close_price"])

    # 拿所有該月合約的 strike + OI + avg_cost + daily_price
    rows = query(
        """
        SELECT strike_price, call_put, open_interest, avg_cost, daily_price
        FROM options_strike_avg_cost
        WHERE trade_date = %s AND contract_month = %s
          AND open_interest > 0
        """,
        (td, contract_month),
    )
    if not rows:
        return {"error": "no_options_data"}

    bucket_order = ["deep_itm", "itm", "atm", "otm", "deep_otm"]
    # 初始化容器
    def _empty():
        return {
            "total_oi": 0,
            "sum_premium_received": 0.0,
            "sum_mark_cost": 0.0,
            "unrealized_pnl_points": 0.0,
            "strikes_count": 0,
        }
    buckets = {b: {"call": _empty(), "put": _empty()} for b in bucket_order}

    for r in rows:
        strike = float(r["strike_price"])
        cp = r["call_put"]
        oi = int(r["open_interest"]) if r["open_interest"] else 0
        avg_cost = float(r["avg_cost"]) if r["avg_cost"] is not None else None
        daily_px = float(r["daily_price"]) if r["daily_price"] is not None else None
        if oi <= 0 or avg_cost is None or daily_px is None:
            continue

        m_pct = (strike - spot) / spot * 100.0 if spot else 0.0
        abs_m = abs(m_pct)

        # 決定 ITM/OTM
        if cp == "C":
            itm = strike < spot
        else:
            itm = strike > spot

        if abs_m < 0.5:
            bucket = "atm"
        elif abs_m < 3.0:
            bucket = "itm" if itm else "otm"
        else:
            bucket = "deep_itm" if itm else "deep_otm"

        side = "call" if cp == "C" else "put"
        b = buckets[bucket][side]
        b["total_oi"] += oi
        b["sum_premium_received"] += oi * avg_cost
        b["sum_mark_cost"] += oi * daily_px
        b["unrealized_pnl_points"] += oi * (avg_cost - daily_px)
        b["strikes_count"] += 1

    # 匯總 + 四捨五入
    result_buckets = []
    totals = {"call_oi": 0, "put_oi": 0, "call_pnl": 0.0, "put_pnl": 0.0}
    for b in bucket_order:
        call = buckets[b]["call"]
        put = buckets[b]["put"]
        for d in (call, put):
            d["sum_premium_received"] = round(d["sum_premium_received"], 0)
            d["sum_mark_cost"] = round(d["sum_mark_cost"], 0)
            d["unrealized_pnl_points"] = round(d["unrealized_pnl_points"], 0)
        totals["call_oi"] += call["total_oi"]
        totals["put_oi"] += put["total_oi"]
        totals["call_pnl"] += call["unrealized_pnl_points"]
        totals["put_pnl"] += put["unrealized_pnl_points"]
        result_buckets.append({
            "bucket": b,
            "call": call,
            "put": put,
        })

    # 判讀：哪格 P&L 最差（賣方最痛），哪格 OI 最大
    worst_call = min(result_buckets, key=lambda x: x["call"]["unrealized_pnl_points"])
    worst_put = min(result_buckets, key=lambda x: x["put"]["unrealized_pnl_points"])
    max_oi_call = max(result_buckets, key=lambda x: x["call"]["total_oi"])
    max_oi_put = max(result_buckets, key=lambda x: x["put"]["total_oi"])

    return {
        "trade_date": str(td),
        "contract_month": contract_month,
        "spot": spot,
        "buckets": result_buckets,
        "totals": {
            "call_oi": totals["call_oi"],
            "put_oi": totals["put_oi"],
            "call_pnl_points": round(totals["call_pnl"], 0),
            "put_pnl_points": round(totals["put_pnl"], 0),
            "net_pnl_points": round(totals["call_pnl"] + totals["put_pnl"], 0),
        },
        "highlights": {
            "worst_call_bucket": worst_call["bucket"],
            "worst_call_pnl": worst_call["call"]["unrealized_pnl_points"],
            "worst_put_bucket": worst_put["bucket"],
            "worst_put_pnl": worst_put["put"]["unrealized_pnl_points"],
            "max_oi_call_bucket": max_oi_call["bucket"],
            "max_oi_put_bucket": max_oi_put["bucket"],
        },
    }


@router.get("/futures-oi-momentum")
def get_futures_oi_momentum(
    days: int = Query(default=10, ge=5, le=30),
):
    """
    期貨未平倉動能 — 過去 N 個交易日總 TX OI + 近月收盤；四象限動能分類。
    - 漲+OI擴 = 多方建倉（bull_build）、漲+OI縮 = 空頭回補（bear_cover）
    - 跌+OI擴 = 空方建倉（bear_build）、跌+OI縮 = 多頭認賠（bull_cover）
    """
    rows = query(
        """
        WITH daily AS (
          SELECT
            trade_date,
            SUM(open_interest) AS total_oi
          FROM tx_futures_daily
          WHERE session = '一般' AND contract_code = 'TX'
          GROUP BY trade_date
        ),
        near_month AS (
          SELECT DISTINCT ON (trade_date)
            trade_date, close_price, volume
          FROM tx_futures_daily
          WHERE session = '一般' AND contract_code = 'TX'
            AND LENGTH(contract_month) = 6
          ORDER BY trade_date, volume DESC NULLS LAST
        )
        SELECT d.trade_date, d.total_oi, n.close_price
        FROM daily d
        JOIN near_month n USING (trade_date)
        ORDER BY d.trade_date DESC
        LIMIT %s
        """,
        (days,),
    )
    if not rows or len(rows) < 2:
        return {"series": [], "stats": None, "error": "no_data"}

    rows_asc = sorted(rows, key=lambda r: r["trade_date"])  # ASC

    series = []
    prev_oi = None
    prev_price = None
    for r in rows_asc:
        td = r["trade_date"]
        oi = int(r["total_oi"]) if r["total_oi"] is not None else None
        px = float(r["close_price"]) if r["close_price"] is not None else None
        if oi is None or px is None:
            continue

        oi_delta = None
        px_delta = None
        state = None
        if prev_oi is not None and prev_price is not None:
            oi_delta = oi - prev_oi
            px_delta = round(px - prev_price, 2)
            if px_delta >= 0 and oi_delta >= 0:
                state = "bull_build"        # 漲 + OI 擴張：多方建倉
            elif px_delta >= 0 and oi_delta < 0:
                state = "bear_cover"        # 漲 + OI 收縮：空頭回補
            elif px_delta < 0 and oi_delta >= 0:
                state = "bear_build"        # 跌 + OI 擴張：空方建倉
            else:
                state = "bull_cover"        # 跌 + OI 收縮：多頭認賠

        series.append({
            "trade_date": str(td),
            "total_oi": oi,
            "close_price": px,
            "oi_delta": oi_delta,
            "px_delta": px_delta,
            "state": state,
        })
        prev_oi, prev_price = oi, px

    if len(series) < 2:
        return {"series": [], "stats": None, "error": "insufficient_days"}

    # 累積變化（從首日到末日）
    first = series[0]
    last = series[-1]
    cum_oi_delta = last["total_oi"] - first["total_oi"]
    cum_oi_pct = round(cum_oi_delta / first["total_oi"] * 100.0, 2) if first["total_oi"] else 0.0
    cum_px_delta = round(last["close_price"] - first["close_price"], 2)
    cum_px_pct = round(cum_px_delta / first["close_price"] * 100.0, 2) if first["close_price"] else 0.0

    # 累積動能狀態
    if cum_px_pct >= 0 and cum_oi_pct >= 0:
        cum_state = "bull_build"
    elif cum_px_pct >= 0 and cum_oi_pct < 0:
        cum_state = "bear_cover"
    elif cum_px_pct < 0 and cum_oi_pct >= 0:
        cum_state = "bear_build"
    else:
        cum_state = "bull_cover"

    # 單日狀態分布
    state_counts: dict[str, int] = {}
    for s in series[1:]:
        k = s.get("state")
        if k:
            state_counts[k] = state_counts.get(k, 0) + 1

    return {
        "series": series,
        "stats": {
            "days_covered": len(series),
            "cum_oi_delta": cum_oi_delta,
            "cum_oi_pct": cum_oi_pct,
            "cum_px_delta": cum_px_delta,
            "cum_px_pct": cum_px_pct,
            "cum_state": cum_state,
            "state_counts": state_counts,
            "latest_state": last.get("state"),
        },
    }


@router.get("/volume-concentration")
def get_volume_concentration(
    days: int = Query(default=10, ge=5, le=30),
    top_n: int = Query(default=3, ge=2, le=5),
):
    """
    選擇權成交量集中度 — 過去 N 個交易日，主力合約月份的 top-N (strike, call_put) 成交量佔當日總成交量比例。
    - 主力月份 = 當日最高成交量的 TXO 合約月份（月選或週選皆可）
    - concentrated (>=40%)、balanced (20~40%)、dispersed (<20%)
    - 散戶分散下單則比例低，機構集中下注於少數關鍵履約價則比例高
    """
    # 取得最近 N 個交易日
    date_rows = query(
        """
        SELECT DISTINCT trade_date FROM txo_options_daily
        WHERE session = '一般'
        ORDER BY trade_date DESC
        LIMIT %s
        """,
        (days,),
    )
    if not date_rows:
        return {"series": [], "current_top": [], "stats": None, "error": "no_data"}

    trade_dates = [r["trade_date"] for r in date_rows]
    trade_dates.sort()  # ASC for series

    series = []
    current_top_detail = None
    for td in trade_dates:
        # 找當日主力月份（最高成交量的 contract_month）
        dom_rows = query(
            """
            SELECT contract_month, SUM(volume) AS total_vol
            FROM txo_options_daily
            WHERE trade_date = %s AND session = '一般' AND volume > 0
            GROUP BY contract_month
            ORDER BY total_vol DESC
            LIMIT 1
            """,
            (td,),
        )
        if not dom_rows or not dom_rows[0].get("total_vol"):
            continue
        dominant_month = dom_rows[0]["contract_month"]
        total_vol = int(dom_rows[0]["total_vol"])
        if total_vol <= 0:
            continue

        # 抓該主力月份所有 (strike, call_put) 成交量
        rows = query(
            """
            SELECT strike_price, call_put, volume
            FROM txo_options_daily
            WHERE trade_date = %s AND contract_month = %s AND session = '一般'
              AND volume > 0
            ORDER BY volume DESC
            LIMIT %s
            """,
            (td, dominant_month, top_n),
        )
        if not rows:
            continue

        top_entries = []
        top_sum = 0
        for r in rows:
            v = int(r["volume"])
            top_entries.append({
                "strike": float(r["strike_price"]),
                "call_put": r["call_put"],
                "volume": v,
            })
            top_sum += v
        concentration_pct = round(top_sum / total_vol * 100.0, 2) if total_vol else 0.0

        if concentration_pct >= 40:
            state = "concentrated"
        elif concentration_pct >= 20:
            state = "balanced"
        else:
            state = "dispersed"

        series.append({
            "trade_date": str(td),
            "dominant_month": dominant_month,
            "total_volume": total_vol,
            "top_volume": top_sum,
            "concentration_pct": concentration_pct,
            "state": state,
        })
        current_top_detail = {
            "trade_date": str(td),
            "dominant_month": dominant_month,
            "top_strikes": top_entries,
        }

    if not series:
        return {"series": [], "current_top": None, "stats": None, "error": "no_data"}

    # 統計
    pcts = [s["concentration_pct"] for s in series]
    avg = sum(pcts) / len(pcts)
    latest = series[-1]["concentration_pct"]
    delta = round(latest - avg, 2)
    trend_state = "rising" if delta > 3 else ("falling" if delta < -3 else "stable")

    return {
        "series": series,
        "current_top": current_top_detail,
        "stats": {
            "days_covered": len(series),
            "avg_concentration_pct": round(avg, 2),
            "latest_concentration_pct": latest,
            "delta_vs_avg": delta,
            "trend_state": trend_state,
            "current_state": series[-1]["state"],
        },
    }
