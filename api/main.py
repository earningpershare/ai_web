"""
Financial Data API — FastAPI 入口

架構：
  main.py          ← 只負責 app 建立、middleware、router 掛載
  routers/
    system.py      ← /health, /crawler-log
    futures.py     ← /futures
    options.py     ← /options, /pcr, /options/strike-cost
    institutional.py ← /institutional/futures, /institutional/options
    positions.py   ← /retail/futures, /retail/options, /large-traders
    market.py      ← /market/direction, /market/itm-otm, /market/max-pain, /market/oi-structure

版本化：
  所有 router 同時掛載在 /v1/ 前綴（建議新前端使用）
  與根路徑（保持向後相容，舊前端 API_URL 無需改動）
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import system, futures, options, institutional, positions, market

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Financial Data API",
    version="1.0.0",
    description="台指期交所資料 REST API",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
# 每個 router 同時掛在根路徑（v0 相容）與 /v1/ 前綴

_ROUTERS = [
    system.router,
    futures.router,
    options.router,
    institutional.router,
    positions.router,
    market.router,
]

for r in _ROUTERS:
    app.include_router(r)                        # legacy: /health, /futures …
    app.include_router(r, prefix="/v1")          # versioned: /v1/health, /v1/futures …
