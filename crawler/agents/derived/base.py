"""
共用常數、型別轉換 helper、cursor factory。
所有 derived 子模組都從這裡 import，避免重複定義。
"""

import psycopg2.extras

# ── 期貨折算小台係數 ──────────────────────────────────────────────────────────
# key = institutional_futures.contract_code
FUT_MULTIPLIER: dict[str, float] = {
    "臺股期貨":    4.0,   # TX  大台
    "小型臺指期貨": 1.0,   # MTX 小台
    "微型臺指期貨": 0.4,   # MXF 微台 (1/10 大台)
}

# TXO 每口 = 1 大台 = 4 小台
TXO_TO_MTX: float = 4.0

# institutional_futures.contract_code → tx_futures_daily.contract_code
INST_TO_DAILY: dict[str, str] = {
    "臺股期貨":    "TX",
    "小型臺指期貨": "MTX",
    "微型臺指期貨": "MXF",
}


# ── helpers ───────────────────────────────────────────────────────────────────

def dict_cursor(conn):
    """回傳 RealDictCursor context manager"""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def s(v, default: int = 0) -> int:
    """安全轉 int，None / 空值一律回傳 default"""
    try:
        return int(v or default)
    except (TypeError, ValueError):
        return default


def sf(v, default: float = 0.0) -> float:
    """安全轉 float"""
    try:
        return float(v or default)
    except (TypeError, ValueError):
        return default
