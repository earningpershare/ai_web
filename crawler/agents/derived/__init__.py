"""
derived 套件 — 統一入口

每個 metric 以 (name, compute_fn, table, conflict_cols) 描述，
新增指標只需在 METRICS 清單加一行，不需修改 run()。
"""

import logging
from datetime import date

from ..db import get_connection, upsert, log_crawl
from .retail          import compute_retail_futures, compute_retail_options
from .strike_cost     import compute_strike_avg_cost
from .market_direction import compute_market_direction
from .itm_otm         import compute_itm_otm
from .max_pain        import compute_max_pain
from .oi_structure    import compute_oi_structure

logger = logging.getLogger(__name__)

# ── Metric 清單 ───────────────────────────────────────────────────────────────
# 格式：(agent_name, compute_fn, db_table, conflict_cols)
# 執行順序：retail 必須先於 market_direction（因後者依賴 retail_futures/options）

METRICS = [
    (
        "retail_futures",
        compute_retail_futures,
        "retail_futures",
        ["trade_date", "contract_code"],
    ),
    (
        "retail_options",
        compute_retail_options,
        "retail_options",
        ["trade_date"],
    ),
    (
        "strike_avg_cost",
        compute_strike_avg_cost,
        "options_strike_avg_cost",
        ["trade_date", "contract_month", "strike_price", "call_put"],
    ),
    (
        "market_direction",
        compute_market_direction,
        "market_direction",
        ["trade_date", "group_type"],
    ),
    (
        "market_itm_otm",
        compute_itm_otm,
        "market_itm_otm",
        ["trade_date"],
    ),
    (
        "market_max_pain",
        compute_max_pain,
        "market_max_pain",
        ["trade_date"],
    ),
    (
        "market_oi_structure",
        compute_oi_structure,
        "market_oi_structure",
        ["trade_date"],
    ),
]


# ── 公開 API ──────────────────────────────────────────────────────────────────

def run(trade_date: date, metrics: list[str] | None = None):
    """
    執行所有（或指定）derived metrics 並寫入 DB。

    :param trade_date: 交易日
    :param metrics:    若指定，只執行名稱在列表內的 metric（None = 全部）
    """
    conn = get_connection()
    total = 0
    errors = []
    try:
        for name, fn, table, conflict_cols in METRICS:
            if metrics is not None and name not in metrics:
                continue
            try:
                rows = fn(conn, trade_date)
                cnt  = upsert(conn, table, rows, conflict_cols)
                total += cnt
                logger.info("derived/%s: %s → %d rows", name, trade_date, cnt)
            except Exception as e:
                logger.error("derived/%s: %s FAILED: %s", name, trade_date, e)
                errors.append(f"{name}: {e}")

        status  = "failed" if errors else "success"
        message = "; ".join(errors) if errors else ""
        log_crawl(conn, "derived_metrics", str(trade_date), status, total, message)

        if errors:
            raise RuntimeError(f"derived_metrics 部分失敗: {message}")

        logger.info("derived_metrics total: %s → %d rows", trade_date, total)
    finally:
        conn.close()
