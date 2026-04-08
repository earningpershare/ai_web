"""
Payment Router — 綠界科技 (ECPay) 金流串接

POST /payment/create-order     — 建立付款訂單，回傳綠界付款表單 HTML
POST /payment/notify           — 綠界 Server 端回呼（ReturnURL）
POST /payment/period-notify    — 定期定額每期回呼（PeriodReturnURL）
GET  /payment/result           — 付款完成後導回前端
GET  /payment/status/{order_no} — 查詢訂單狀態
"""

import hashlib
import logging
import os
import time
import urllib.parse
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Header, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from routers.supabase_client import get_supabase
from routers.auth import _current_user, vless_uuid_for, PLAN_RANK

router = APIRouter(prefix="/payment", tags=["payment"])
log = logging.getLogger(__name__)

# ── 綠界設定 ─────────────────────────────────────────────────────────────────

ECPAY_MERCHANT_ID = os.getenv("ECPAY_MERCHANT_ID", "")
ECPAY_HASH_KEY = os.getenv("ECPAY_HASH_KEY", "")
ECPAY_HASH_IV = os.getenv("ECPAY_HASH_IV", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://16888u.com")

# 正式環境
ECPAY_ACTION_URL = "https://payment.ecpay.com.tw/Cashier/AioCheckOut/V5"
# 測試環境（開發時切換）
# ECPAY_ACTION_URL = "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5"

# ── 方案定義 ─────────────────────────────────────────────────────────────────

PLANS = {
    "pro": {
        "name": "進階版",
        "amount": 88,
        "period_type": "M",       # Monthly
        "frequency": 1,           # 每 1 個月
        "exec_times": 99,         # 最多 99 期（可隨時取消）
        "is_periodic": True,
    },
    "ultimate": {
        "name": "終極版",
        "amount": 1688,
        "is_periodic": False,     # 一次買斷
    },
}


# ── CheckMacValue 生成 ──────────────────────────────────────────────────────

def _generate_check_mac_value(params: dict) -> str:
    """依照綠界規格產生 CheckMacValue (SHA256)"""
    # 1. 按 key 排序（不分大小寫）
    sorted_params = sorted(params.items(), key=lambda x: x[0].lower())
    # 2. 組成 query string，前後加 HashKey/HashIV
    raw = f"HashKey={ECPAY_HASH_KEY}&" + "&".join(f"{k}={v}" for k, v in sorted_params) + f"&HashIV={ECPAY_HASH_IV}"
    # 3. URL encode（小寫）
    encoded = urllib.parse.quote_plus(raw, safe="").lower()
    # 4. SHA256 → 大寫
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest().upper()


def _verify_check_mac_value(params: dict) -> bool:
    """驗證綠界回傳的 CheckMacValue"""
    received = params.get("CheckMacValue", "")
    check_params = {k: v for k, v in params.items() if k != "CheckMacValue"}
    expected = _generate_check_mac_value(check_params)
    return received.upper() == expected.upper()


# ── Schemas ──────────────────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    plan: str  # "pro" or "ultimate"


# ── 建立訂單 ─────────────────────────────────────────────────────────────────

@router.post("/create-order")
def create_order(body: CreateOrderRequest, request: Request, authorization: str = Header(default="")):
    user = _current_user(authorization)
    user_id = str(user.id)

    plan_key = body.plan
    if plan_key not in PLANS:
        raise HTTPException(status_code=400, detail="無效的方案")

    plan = PLANS[plan_key]

    # 檢查是否已經是該方案或更高
    sb = get_supabase()
    profile = sb.table("user_profiles").select("plan").eq("id", user_id).single().execute()
    current = (profile.data or {}).get("plan", "free")
    if PLAN_RANK.get(current, 0) >= PLAN_RANK.get(plan_key, 0):
        raise HTTPException(status_code=400, detail="您已經是此方案或更高方案的會員")

    # 生成訂單編號：TF + 時間戳 + user_id 前 4 碼（確保唯一且 <= 20 字元）
    ts = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d%H%M%S")
    order_no = f"TF{ts}{user_id[:4]}"[:20]

    now_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y/%m/%d %H:%M:%S")

    # 寫入 payment_orders
    sb.table("payment_orders").insert({
        "order_no": order_no,
        "user_id": user_id,
        "plan": plan_key,
        "amount": plan["amount"],
        "status": "pending",
        "is_periodic": plan.get("is_periodic", False),
    }).execute()

    # 組綠界參數
    api_base = str(request.base_url).rstrip("/")
    params = {
        "MerchantID": ECPAY_MERCHANT_ID,
        "MerchantTradeNo": order_no,
        "MerchantTradeDate": now_str,
        "PaymentType": "aio",
        "TotalAmount": plan["amount"],
        "TradeDesc": f"TaifexAI {plan['name']}",
        "ItemName": f"TaifexAI {plan['name']}",
        "ReturnURL": f"{api_base}/payment/notify",
        "OrderResultURL": f"{FRONTEND_URL}/05_pricing?payment_result=1",
        "ChoosePayment": "Credit",
        "EncryptType": 1,
        "NeedExtraPaidInfo": "Y",
        "CustomField1": user_id,
        "CustomField2": plan_key,
    }

    # 定期定額參數
    if plan.get("is_periodic"):
        params.update({
            "PeriodAmount": plan["amount"],
            "PeriodType": plan["period_type"],
            "Frequency": plan["frequency"],
            "ExecTimes": plan["exec_times"],
            "PeriodReturnURL": f"{api_base}/payment/period-notify",
        })

    params["CheckMacValue"] = _generate_check_mac_value(params)

    # 回傳自動提交的 HTML 表單
    form_inputs = "\n".join(
        f'<input type="hidden" name="{k}" value="{v}" />'
        for k, v in params.items()
    )
    html = f"""
    <html><body>
    <form id="ecpay" method="POST" action="{ECPAY_ACTION_URL}">
        {form_inputs}
    </form>
    <script>document.getElementById('ecpay').submit();</script>
    </body></html>
    """
    return {"order_no": order_no, "html": html}


# ── 綠界付款結果通知（Server 端回呼）────────────────────────────────────────

@router.post("/notify")
async def payment_notify(request: Request):
    """綠界付款完成後的 Server-to-Server 回呼"""
    form = await request.form()
    params = dict(form)

    log.info("ECPay notify: %s", params)

    # 驗證 CheckMacValue
    if not _verify_check_mac_value(params):
        log.warning("ECPay notify: CheckMacValue 驗證失敗")
        return "0|ErrorMessage"

    rtn_code = params.get("RtnCode", "")
    order_no = params.get("MerchantTradeNo", "")
    user_id = params.get("CustomField1", "")
    plan_key = params.get("CustomField2", "")
    trade_no = params.get("TradeNo", "")  # 綠界交易編號

    sb = get_supabase()

    if rtn_code == "1":
        # 付款成功
        plan = PLANS.get(plan_key, {})
        is_periodic = plan.get("is_periodic", False)

        # 更新訂單狀態
        sb.table("payment_orders").update({
            "status": "paid",
            "ecpay_trade_no": trade_no,
            "paid_at": datetime.now(timezone.utc).isoformat(),
            "raw_response": params,
        }).eq("order_no", order_no).execute()

        # 計算到期日
        if is_periodic:
            # 月訂閱：每期回呼會延長，先設一個月
            expires = (datetime.now(timezone.utc) + timedelta(days=35)).isoformat()
        else:
            # 一次買斷：永久
            expires = "2099-12-31T23:59:59+00:00"

        # 建立/更新訂閱
        sb.table("user_subscriptions").insert({
            "user_id": user_id,
            "plan": plan_key,
            "status": "active",
            "expires_at": expires,
            "amount_twd": plan.get("amount", 0),
            "promo_code": None,
            "metadata": {"ecpay_trade_no": trade_no, "order_no": order_no},
        }).execute()

        # 更新 user_profiles
        sb.table("user_profiles").update({
            "plan": plan_key,
        }).eq("id", user_id).execute()

        # 記錄事件
        sb.table("subscription_events").insert({
            "user_id": user_id,
            "event_type": "payment_success",
            "to_plan": plan_key,
            "metadata": {"order_no": order_no, "trade_no": trade_no, "amount": plan.get("amount", 0)},
        }).execute()

        log.info("Payment success: order=%s user=%s plan=%s", order_no, user_id, plan_key)
    else:
        # 付款失敗
        sb.table("payment_orders").update({
            "status": "failed",
            "ecpay_trade_no": trade_no,
            "raw_response": params,
        }).eq("order_no", order_no).execute()

        log.warning("Payment failed: order=%s code=%s msg=%s", order_no, rtn_code, params.get("RtnMsg", ""))

    return "1|OK"


# ── 定期定額每期回呼 ─────────────────────────────────────────────────────────

@router.post("/period-notify")
async def period_notify(request: Request):
    """定期定額每期扣款結果回呼"""
    form = await request.form()
    params = dict(form)

    log.info("ECPay period notify: %s", params)

    if not _verify_check_mac_value(params):
        log.warning("ECPay period notify: CheckMacValue 驗證失敗")
        return "0|ErrorMessage"

    rtn_code = params.get("RtnCode", "")
    order_no = params.get("MerchantTradeNo", "")

    sb = get_supabase()

    # 查找原始訂單
    order_resp = sb.table("payment_orders").select("user_id, plan").eq("order_no", order_no).single().execute()
    if not order_resp.data:
        log.warning("Period notify: order %s not found", order_no)
        return "1|OK"

    user_id = order_resp.data["user_id"]
    plan_key = order_resp.data["plan"]

    if rtn_code == "1":
        # 扣款成功 → 延長到期日
        new_expires = (datetime.now(timezone.utc) + timedelta(days=35)).isoformat()
        sb.table("user_subscriptions").update({
            "expires_at": new_expires,
            "status": "active",
        }).eq("user_id", user_id).eq("plan", plan_key).eq("status", "active").execute()

        sb.table("subscription_events").insert({
            "user_id": user_id,
            "event_type": "period_payment_success",
            "to_plan": plan_key,
            "metadata": {"order_no": order_no, "period_params": params},
        }).execute()

        log.info("Period payment success: order=%s user=%s", order_no, user_id)
    else:
        # 扣款失敗
        sb.table("subscription_events").insert({
            "user_id": user_id,
            "event_type": "period_payment_failed",
            "to_plan": plan_key,
            "metadata": {"order_no": order_no, "rtn_code": rtn_code, "rtn_msg": params.get("RtnMsg", "")},
        }).execute()

        log.warning("Period payment failed: order=%s code=%s", order_no, rtn_code)

    return "1|OK"


# ── 查詢訂單狀態 ─────────────────────────────────────────────────────────────

@router.get("/status/{order_no}")
def payment_status(order_no: str, authorization: str = Header(default="")):
    user = _current_user(authorization)
    user_id = str(user.id)

    sb = get_supabase()
    resp = sb.table("payment_orders").select("*").eq("order_no", order_no).eq("user_id", user_id).single().execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="查無此訂單")

    return resp.data
