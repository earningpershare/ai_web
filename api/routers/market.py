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
