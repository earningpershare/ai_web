"""
爬蟲乾跑測試 - 不需要 DB，只驗證資料能否正確爬取與解析
"""

import sys
import io
from datetime import date, timedelta

import pandas as pd
import requests

# 強制 stdout 使用 utf-8，避免 Windows cp950 印出亂碼
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 取最近一個交易日（昨天若是週一則取上週五）
def last_trading_day() -> date:
    d = date.today() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d

TARGET = last_trading_day()
DATE_STR = TARGET.strftime("%Y/%m/%d")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.taifex.com.tw/",
}

SEP = "-" * 60


def section(title):
    print(f"\n{SEP}\n  {title}\n{SEP}")


def safe_float(v):
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return None


def safe_int(v):
    try:
        return int(float(str(v).replace(",", "")))
    except Exception:
        return None


# ── 1. 台指期貨 ───────────────────────────────────────────────────────────────

section(f"1. 台指期貨行情 ({DATE_STR})")
try:
    resp = requests.get(
        "https://www.taifex.com.tw/cht/3/futDataDown",
        params={"down_type": "1", "commodity_id": "TX",
                "queryStartDate": DATE_STR, "queryEndDate": DATE_STR},
        headers=HEADERS, timeout=30,
    )
    df = pd.read_csv(io.BytesIO(resp.content), encoding="big5", on_bad_lines="skip")
    print(f"  欄位: {list(df.columns)}")
    print(f"  筆數: {len(df)}")
    if not df.empty:
        print(df.to_string(index=False))
except Exception as e:
    print(f"  [ERROR] {e}")


# ── 2. 台指選擇權 ─────────────────────────────────────────────────────────────

section(f"2. 台指選擇權行情 ({DATE_STR})  -- 只顯示前 10 筆")
try:
    resp = requests.get(
        "https://www.taifex.com.tw/cht/3/optDataDown",
        params={"down_type": "1", "commodity_id": "TXO",
                "queryStartDate": DATE_STR, "queryEndDate": DATE_STR},
        headers=HEADERS, timeout=60,
    )
    df = pd.read_csv(io.BytesIO(resp.content), encoding="big5", on_bad_lines="skip")
    print(f"  欄位: {list(df.columns)}")
    print(f"  總筆數: {len(df)}")
    print(df.head(10).to_string(index=False))
except Exception as e:
    print(f"  [ERROR] {e}")


# ── 3. Put/Call Ratio ─────────────────────────────────────────────────────────

section(f"3. Put/Call Ratio ({DATE_STR})")
try:
    resp = requests.get(
        "https://www.taifex.com.tw/cht/3/pcRatio",
        params={"queryStartDate": DATE_STR, "queryEndDate": DATE_STR},
        headers=HEADERS, timeout=30,
    )
    resp.encoding = "utf-8-sig"
    tables = pd.read_html(resp.text, header=0)
    for i, t in enumerate(tables):
        if t.shape[1] >= 5:
            print(f"  欄位: {list(t.columns)}")
            print(t.head(3).to_string(index=False))
            break
except Exception as e:
    print(f"  [ERROR] {e}")


# ── 4. 三大法人 - 期貨 ────────────────────────────────────────────────────────

section(f"4. 三大法人期貨 ({DATE_STR})")
try:
    resp = requests.get(
        "https://www.taifex.com.tw/cht/3/futContractsDate",
        params={"queryStartDate": DATE_STR, "queryEndDate": DATE_STR},
        headers=HEADERS, timeout=30,
    )
    resp.encoding = "utf-8-sig"
    tables = pd.read_html(resp.text, header=0)
    for t in tables:
        if t.shape[1] >= 8:
            print(f"  欄位: {list(t.columns)}")
            print(f"  筆數: {len(t)}")
            print(t.to_string(index=False))
            break
except Exception as e:
    print(f"  [ERROR] {e}")


# ── 5. 三大法人 - 選擇權 ──────────────────────────────────────────────────────

section(f"5. 三大法人選擇權 ({DATE_STR})")
try:
    resp = requests.get(
        "https://www.taifex.com.tw/cht/3/optContractsDate",
        params={"queryStartDate": DATE_STR, "queryEndDate": DATE_STR},
        headers=HEADERS, timeout=30,
    )
    resp.encoding = "utf-8-sig"
    tables = pd.read_html(resp.text, header=0)
    for t in tables:
        if t.shape[1] >= 10:
            print(f"  欄位: {list(t.columns)}")
            print(f"  筆數: {len(t)}")
            print(t.to_string(index=False))
            break
except Exception as e:
    print(f"  [ERROR] {e}")


# ── 6. 大額交易人 - 期貨 ──────────────────────────────────────────────────────

section(f"6. 大額交易人期貨 ({DATE_STR})")
try:
    resp = requests.get(
        "https://www.taifex.com.tw/cht/3/largeTraderFutDown",
        params={"queryStartDate": DATE_STR, "queryEndDate": DATE_STR, "commodity_id": "TX"},
        headers=HEADERS, timeout=30,
    )
    df = pd.read_csv(io.StringIO(resp.content.decode("big5", errors="replace")), on_bad_lines="skip")
    print(f"  欄位: {list(df.columns)}")
    print(f"  筆數: {len(df)}")
    if not df.empty:
        print(df.to_string(index=False))
except Exception as e:
    print(f"  [ERROR] {e}")


# ── 7. 大額交易人 - 選擇權 ────────────────────────────────────────────────────

section(f"7. 大額交易人選擇權 ({DATE_STR})")
try:
    resp = requests.get(
        "https://www.taifex.com.tw/cht/3/largeTraderOptDown",
        params={"queryStartDate": DATE_STR, "queryEndDate": DATE_STR, "commodity_id": "TXO"},
        headers=HEADERS, timeout=30,
    )
    df = pd.read_csv(io.StringIO(resp.content.decode("big5", errors="replace")), on_bad_lines="skip")
    print(f"  欄位: {list(df.columns)}")
    print(f"  筆數: {len(df)}")
    if not df.empty:
        print(df.head(10).to_string(index=False))
except Exception as e:
    print(f"  [ERROR] {e}")


print(f"\n{SEP}")
print(f"  測試完成，目標日期: {TARGET}")
print(SEP)
