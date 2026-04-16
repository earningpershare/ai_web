#!/usr/bin/env python3
"""
部署後煙霧測試 (Post-deploy Smoke Tests)

驗證前端頁面與後端 API 是否正常運作。
僅做 HTTP 狀態碼檢查，不需要瀏覽器。

用法：
    python tests/smoke_test.py                          # 預設測試 https://16888u.com
    python tests/smoke_test.py --url http://localhost    # 測試本地環境
    python tests/smoke_test.py --timeout 10              # 自訂超時秒數
"""

from __future__ import annotations

import argparse
import io
import sys
import time
from urllib.parse import urljoin

import requests

# 確保 Windows 終端機能正確輸出 UTF-8
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── 顏色輸出 ─────────────────────────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def passed(label: str, detail: str = "") -> None:
    """印出 PASS 結果"""
    suffix = f"  ({detail})" if detail else ""
    print(f"  {GREEN}PASS{RESET}  {label}{suffix}")


def failed(label: str, detail: str = "") -> None:
    """印出 FAIL 結果"""
    suffix = f"  ({detail})" if detail else ""
    print(f"  {RED}FAIL{RESET}  {label}{suffix}")


# ── 測試項目 ─────────────────────────────────────────────────────────────────

# Dashboard 頁面路徑（Streamlit 前端）
DASHBOARD_PAGES = [
    "/about",
    "/market",
    "/options-map",
    "/analysis",
    "/research",
    "/daily-ops",
    "/pricing",
    "/account",
    "/privacy",
]

# API 端點（FastAPI 後端）
API_ENDPOINTS = [
    {"path": "/health", "description": "API 健康檢查"},
    {"path": "/v1/market/latest", "description": "最新行情資料"},
    {"path": "/v1/articles?limit=1", "description": "文章列表"},
]


def check_api(base_url: str, timeout: int) -> list[bool]:
    """
    測試後端 API 端點。
    回傳每個端點的測試結果（True=通過, False=失敗）。
    """
    # API 基礎 URL：如果前端是 https://16888u.com，API 在 https://api.16888u.com
    # 如果是自訂 URL（如 localhost），假設 API 在同一 host 的 :8000 port
    if "16888u.com" in base_url:
        api_base = "https://api.16888u.com"
    else:
        # 本地開發：假設 API 在 port 8000
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        api_base = f"{parsed.scheme}://{parsed.hostname}:8000"

    print(f"\n{'='*60}")
    print(f"後端 API 測試 ({api_base})")
    print(f"{'='*60}")

    results = []
    for ep in API_ENDPOINTS:
        url = urljoin(api_base + "/", ep["path"].lstrip("/"))
        label = f"API {ep['path']}"
        try:
            resp = requests.get(url, timeout=timeout, allow_redirects=True)
            if resp.status_code < 500:
                passed(label, f"HTTP {resp.status_code} — {ep['description']}")
                results.append(True)
            else:
                failed(label, f"HTTP {resp.status_code} — {ep['description']}")
                results.append(False)
        except requests.RequestException as e:
            failed(label, f"連線失敗: {e}")
            results.append(False)

    return results


def check_dashboard(base_url: str, timeout: int) -> list[bool]:
    """
    測試前端 Dashboard 頁面。
    Streamlit 頁面只要不回 5xx 就算通過。
    """
    print(f"\n{'='*60}")
    print(f"前端 Dashboard 測試 ({base_url})")
    print(f"{'='*60}")

    results = []
    for page in DASHBOARD_PAGES:
        url = urljoin(base_url.rstrip("/") + "/", page.lstrip("/"))
        label = f"Dashboard {page}"
        try:
            resp = requests.get(url, timeout=timeout, allow_redirects=True)
            if resp.status_code < 500:
                passed(label, f"HTTP {resp.status_code}")
                results.append(True)
            else:
                failed(label, f"HTTP {resp.status_code}")
                results.append(False)
        except requests.RequestException as e:
            failed(label, f"連線失敗: {e}")
            results.append(False)

    return results


def main() -> int:
    """主程式入口，回傳 exit code（0=全部通過, 1=有失敗）"""
    parser = argparse.ArgumentParser(description="部署後煙霧測試")
    parser.add_argument(
        "--url",
        default="https://16888u.com",
        help="前端基礎 URL（預設：https://16888u.com）",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="每個請求的超時秒數（預設：10）",
    )
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    print(f"\n[Smoke Test] TaifexAI 煙霧測試")
    print(f"   目標: {base_url}")
    print(f"   超時: {args.timeout}s")

    start = time.time()

    # 執行所有測試
    api_results = check_api(base_url, args.timeout)
    dashboard_results = check_dashboard(base_url, args.timeout)

    elapsed = time.time() - start
    all_results = api_results + dashboard_results
    total = len(all_results)
    pass_count = sum(all_results)
    fail_count = total - pass_count

    # 印出總結
    print(f"\n{'='*60}")
    print(f"測試結果總結")
    print(f"{'='*60}")
    print(f"  總共: {total} 項")
    print(f"  通過: {GREEN}{pass_count}{RESET}")
    if fail_count:
        print(f"  失敗: {RED}{fail_count}{RESET}")
    print(f"  耗時: {elapsed:.1f}s")

    if fail_count:
        print(f"\n{RED}FAILED: 有 {fail_count} 項測試失敗{RESET}\n")
        return 1
    else:
        print(f"\n{GREEN}ALL PASSED: 所有測試通過{RESET}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
