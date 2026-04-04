"""
將爬蟲測試資料匯出成 CSV，存在 test_output/ 目錄
"""

import sys
import io
import os
from datetime import date, timedelta

import pandas as pd
import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.taifex.com.tw/"}
OUTPUT_DIR = "test_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def last_trading_day() -> date:
    d = date.today() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


TARGET = last_trading_day()
DATE_STR = TARGET.strftime("%Y/%m/%d")
print(f"目標日期: {TARGET}\n")


def save(df: pd.DataFrame, name: str):
    path = os.path.join(OUTPUT_DIR, f"{name}_{TARGET}.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")  # utf-8-sig 讓 Excel 正確顯示中文
    print(f"  ✓ 已儲存 {path}  ({len(df)} 筆)")
    return path


# 1. 台指期貨
print("1. 台指期貨行情")
resp = requests.get("https://www.taifex.com.tw/cht/3/futDataDown",
    params={"down_type": "1", "commodity_id": "TX", "queryStartDate": DATE_STR, "queryEndDate": DATE_STR},
    headers=HEADERS, timeout=30)
df = pd.read_csv(io.StringIO(resp.content.decode("big5", errors="replace")), on_bad_lines="skip", index_col=False)
save(df, "1_tx_futures")

# 2. 台指選擇權
print("2. 台指選擇權行情")
resp = requests.get("https://www.taifex.com.tw/cht/3/optDataDown",
    params={"down_type": "1", "commodity_id": "TXO", "queryStartDate": DATE_STR, "queryEndDate": DATE_STR},
    headers=HEADERS, timeout=60)
df = pd.read_csv(io.StringIO(resp.content.decode("big5", errors="replace")), on_bad_lines="skip", index_col=False)
save(df, "2_txo_options")

# 3. Put/Call Ratio
print("3. Put/Call Ratio")
resp = requests.post("https://www.taifex.com.tw/cht/3/pcRatio",
    data={"queryStartDate": DATE_STR, "queryEndDate": DATE_STR},
    headers=HEADERS, timeout=30)
tables = pd.read_html(io.StringIO(resp.text), header=0)
for t in tables:
    if t.shape[1] >= 5:
        save(t, "3_put_call_ratio")
        break

# 4. 三大法人期貨 (CSV 下載)
print("4. 三大法人期貨")
resp = requests.post("https://www.taifex.com.tw/cht/3/futContractsDateDown",
    data={"queryStartDate": DATE_STR, "queryEndDate": DATE_STR},
    headers=HEADERS, timeout=30)
df = pd.read_csv(io.StringIO(resp.content.decode("cp950", errors="replace")), index_col=False)
save(df, "4_institutional_futures")

# 5. 三大法人選擇權 (CSV 下載)
print("5. 三大法人選擇權")
resp = requests.post("https://www.taifex.com.tw/cht/3/optContractsDateDown",
    data={"queryStartDate": DATE_STR, "queryEndDate": DATE_STR},
    headers=HEADERS, timeout=30)
df = pd.read_csv(io.StringIO(resp.content.decode("cp950", errors="replace")), index_col=False)
save(df, "5_institutional_options")

# 6. 大額交易人期貨（只篩 TX）
print("6. 大額交易人期貨 (TX)")
resp = requests.get("https://www.taifex.com.tw/cht/3/largeTraderFutDown",
    params={"queryStartDate": DATE_STR, "queryEndDate": DATE_STR},
    headers=HEADERS, timeout=30)
df = pd.read_csv(io.StringIO(resp.content.decode("big5", errors="replace")), on_bad_lines="skip", index_col=False)
df["商品(契約)"] = df["商品(契約)"].str.strip()
df_tx = df[df["商品(契約)"] == "TX"]
save(df_tx, "6_large_trader_futures_TX")

# 7. 大額交易人選擇權（只篩 TXO）
print("7. 大額交易人選擇權 (TXO)")
resp = requests.get("https://www.taifex.com.tw/cht/3/largeTraderOptDown",
    params={"queryStartDate": DATE_STR, "queryEndDate": DATE_STR},
    headers=HEADERS, timeout=30)
df = pd.read_csv(io.StringIO(resp.content.decode("big5", errors="replace")), on_bad_lines="skip", index_col=False)
df["商品(契約)"] = df["商品(契約)"].str.strip()
df_txo = df[df["商品(契約)"] == "TXO"]
save(df_txo, "7_large_trader_options_TXO")

print(f"\n全部完成！請開啟 {os.path.abspath(OUTPUT_DIR)} 資料夾查看 CSV 檔案")
