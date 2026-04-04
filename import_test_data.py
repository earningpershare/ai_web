"""
將 test_output/ 的 CSV 資料寫入 PostgreSQL
"""

import sys
import io
import os
from datetime import date, timedelta

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

conn = psycopg2.connect(
    host="localhost", port=5432,
    dbname="financial_db", user="admin", password="changeme_strong_password",
)
TARGET = date(2026, 3, 31)


def upsert(table, rows, conflict_cols):
    if not rows:
        return 0
    cols = list(rows[0].keys())
    values = [[r[c] for c in cols] for r in rows]
    update_cols = [c for c in cols if c not in conflict_cols]
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES %s "
        f"ON CONFLICT ({', '.join(conflict_cols)}) DO UPDATE SET {set_clause}"
    )
    with conn.cursor() as cur:
        execute_values(cur, sql, values)
    conn.commit()
    return len(rows)


def safe_int(v):
    try:
        s = str(v).replace(",", "").strip()
        if s in ("-", "", "nan", "None"):
            return None
        return int(float(s))
    except Exception:
        return None


def safe_float(v):
    try:
        s = str(v).replace(",", "").strip()
        if s in ("-", "", "nan", "None", "%"):
            return None
        s = s.rstrip("%")
        return float(s)
    except Exception:
        return None


# ── 1. 台指期貨 ──────────────────────────────────────────────────────────────

print("1. 寫入 tx_futures_daily")
df = pd.read_csv("test_output/1_tx_futures_2026-03-31.csv", encoding="utf-8-sig")
df.columns = [c.strip() for c in df.columns]
# 只保留單純契約（過濾掉價差委託）
df = df[df["契約"].str.strip() == "TX"]
rows = []
for _, row in df.iterrows():
    rows.append({
        "trade_date": TARGET,
        "contract_code": "TX",
        "contract_month": str(row.get("到期月份(週別)", "")).strip(),
        "open_price": safe_float(row.get("開盤價")),
        "high_price": safe_float(row.get("最高價")),
        "low_price": safe_float(row.get("最低價")),
        "close_price": safe_float(row.get("收盤價")),
        "volume": safe_int(row.get("成交量")),
        "open_interest": safe_int(row.get("未沖銷契約數")),
        "settlement_price": safe_float(row.get("結算價")),
        "session": str(row.get("交易時段", "一般")).strip(),
    })
n = upsert("tx_futures_daily", rows, ["trade_date", "contract_code", "contract_month", "session"])
print(f"  -> {n} 筆")


# ── 2. 台指選擇權 ─────────────────────────────────────────────────────────────

print("2. 寫入 txo_options_daily")
df = pd.read_csv("test_output/2_txo_options_2026-03-31.csv", encoding="utf-8-sig")
df.columns = [c.strip() for c in df.columns]
df = df[df["契約"].str.strip() == "TXO"]
rows = []
for _, row in df.iterrows():
    cp_raw = str(row.get("買賣權", "")).strip()
    call_put = "C" if "買" in cp_raw or cp_raw.upper().startswith("C") else "P"
    strike = safe_float(row.get("履約價"))
    if strike is None:
        continue
    rows.append({
        "trade_date": TARGET,
        "contract_code": "TXO",
        "contract_month": str(row.get("到期月份(週別)", "")).strip(),
        "strike_price": strike,
        "call_put": call_put,
        "open_price": safe_float(row.get("開盤價")),
        "high_price": safe_float(row.get("最高價")),
        "low_price": safe_float(row.get("最低價")),
        "close_price": safe_float(row.get("收盤價")),
        "volume": safe_int(row.get("成交量")),
        "open_interest": safe_int(row.get("未沖銷契約數")),
        "settlement_price": safe_float(row.get("結算價")),
        "session": str(row.get("交易時段", "一般")).strip(),
    })
n = upsert("txo_options_daily", rows, ["trade_date", "contract_code", "contract_month", "strike_price", "call_put", "session"])
print(f"  -> {n} 筆")


# ── 3. Put/Call Ratio ─────────────────────────────────────────────────────────

print("3. 寫入 put_call_ratio")
df = pd.read_csv("test_output/3_put_call_ratio_2026-03-31.csv", encoding="utf-8-sig")
df.columns = [c.strip() for c in df.columns]
row = df.iloc[0]
rows = [{
    "trade_date": TARGET,
    "call_oi": safe_int(row.get("買權未平倉量")),
    "put_oi": safe_int(row.get("賣權未平倉量")),
    "pc_oi_ratio": safe_float(row.get("買賣權未平倉量比率%")),
    "call_volume": safe_int(row.get("買權成交量")),
    "put_volume": safe_int(row.get("賣權成交量")),
    "pc_vol_ratio": safe_float(row.get("買賣權成交量比率%")),
}]
n = upsert("put_call_ratio", rows, ["trade_date"])
print(f"  -> {n} 筆")


# ── 4. 三大法人期貨 ───────────────────────────────────────────────────────────

print("4. 寫入 institutional_futures")
df = pd.read_csv("test_output/4_institutional_futures_2026-03-31.csv", encoding="utf-8-sig")
df.columns = [c.strip() for c in df.columns]
df["商品名稱"] = df["商品名稱"].str.strip()
df["身份別"] = df["身份別"].str.strip()
target_contracts = {"臺股期貨", "小型臺指期貨", "微型臺指期貨"}
df = df[df["商品名稱"].isin(target_contracts)]
rows = []
for _, row in df.iterrows():
    rows.append({
        "trade_date": TARGET,
        "contract_code": row["商品名稱"],
        "institution_type": row["身份別"],
        "long_volume": safe_int(row.get("多方交易口數")),
        "long_amount": safe_int(row.get("多方交易契約金額(千元)")),
        "short_volume": safe_int(row.get("空方交易口數")),
        "short_amount": safe_int(row.get("空方交易契約金額(千元)")),
        "net_volume": safe_int(row.get("多空交易口數淨額")),
        "net_amount": safe_int(row.get("多空交易契約金額淨額(千元)")),
        "long_oi": safe_int(row.get("多方未平倉口數")),
        "short_oi": safe_int(row.get("空方未平倉口數")),
        "net_oi": safe_int(row.get("多空未平倉口數淨額")),
    })
n = upsert("institutional_futures", rows, ["trade_date", "contract_code", "institution_type"])
print(f"  -> {n} 筆")


# ── 5. 三大法人選擇權 ─────────────────────────────────────────────────────────

print("5. 寫入 institutional_options")
df = pd.read_csv("test_output/5_institutional_options_2026-03-31.csv", encoding="utf-8-sig")
df.columns = [c.strip() for c in df.columns]
df["商品名稱"] = df["商品名稱"].str.strip()
df["身份別"] = df["身份別"].str.strip()
df = df[df["商品名稱"] == "臺指選擇權"]
rows = []
for _, row in df.iterrows():
    rows.append({
        "trade_date": TARGET,
        "contract_code": "TXO",
        "institution_type": row["身份別"],
        "call_long_volume": safe_int(row.get("多方交易口數")),
        "call_long_amount": safe_int(row.get("多方交易契約金額(千元)")),
        "call_short_volume": safe_int(row.get("空方交易口數")),
        "call_short_amount": safe_int(row.get("空方交易契約金額(千元)")),
        "call_net_volume": safe_int(row.get("多空交易口數淨額")),
        "call_net_amount": safe_int(row.get("多空交易契約金額淨額(千元)")),
        "put_long_volume": None, "put_long_amount": None,
        "put_short_volume": None, "put_short_amount": None,
        "put_net_volume": None, "put_net_amount": None,
    })
n = upsert("institutional_options", rows, ["trade_date", "contract_code", "institution_type"])
print(f"  -> {n} 筆")


# ── 6. 大額交易人 ─────────────────────────────────────────────────────────────

print("6. 寫入 large_trader_positions (TX)")
df = pd.read_csv("test_output/6_large_trader_futures_TX_2026-03-31.csv", encoding="utf-8-sig")
df.columns = [c.strip() for c in df.columns]
rows = []
for _, row in df.iterrows():
    month_raw = str(row.get("到期月份(週別)", "")).strip().split(".")[0]
    trader_raw = str(row.get("交易人類別", "")).strip().split(".")[0]
    month_label = {"666666": "近二個月", "999999": "全部月份"}.get(month_raw, month_raw)
    trader_label = {"0": "全體交易人", "1": "特定法人"}.get(trader_raw, trader_raw)
    rows.append({
        "trade_date": TARGET,
        "contract_code": "TX",
        "trader_type": f"{month_label}-{trader_label}",
        "long_position": safe_int(row.get("前十大交易人買方")),
        "short_position": safe_int(row.get("前十大交易人賣方")),
        "market_oi": safe_int(row.get("全市場未沖銷部位數")),
    })
n = upsert("large_trader_positions", rows, ["trade_date", "contract_code", "trader_type"])
print(f"  -> {n} 筆")

print("7. 寫入 large_trader_positions (TXO)")
df = pd.read_csv("test_output/7_large_trader_options_TXO_2026-03-31.csv", encoding="utf-8-sig")
df.columns = [c.strip() for c in df.columns]
rows = []
for _, row in df.iterrows():
    month_raw = str(row.get("到期月份(週別)", "")).strip().split(".")[0]
    trader_raw = str(row.get("交易人類別", "")).strip().split(".")[0]
    cp_raw = str(row.get("買賣權", "")).strip()
    month_label = {"666666": "近二個月", "999999": "全部月份"}.get(month_raw, month_raw)
    trader_label = {"0": "全體交易人", "1": "特定法人"}.get(trader_raw, trader_raw)
    rows.append({
        "trade_date": TARGET,
        "contract_code": "TXO",
        "trader_type": f"{cp_raw}-{month_label}-{trader_label}",
        "long_position": safe_int(row.get("前十大交易人買方")),
        "short_position": safe_int(row.get("前十大交易人賣方")),
        "market_oi": safe_int(row.get("全市場未沖銷部位數")),
    })
n = upsert("large_trader_positions", rows, ["trade_date", "contract_code", "trader_type"])
print(f"  -> {n} 筆")


# ── 確認結果 ──────────────────────────────────────────────────────────────────

print("\n=== 各表筆數確認 ===")
tables = [
    "tx_futures_daily", "txo_options_daily", "put_call_ratio",
    "institutional_futures", "institutional_options", "large_trader_positions",
]
with conn.cursor() as cur:
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"  {t}: {cur.fetchone()[0]} 筆")

conn.close()
print("\n完成！")
