"""
Payment Router — 綠界科技 (ECPay) 金流串接

POST /payment/create-order          — 建立付款訂單，回傳綠界付款表單 HTML
POST /payment/notify                — 綠界 Server 端回呼（ReturnURL）
POST /payment/period-notify         — 定期定額每期回呼（PeriodReturnURL）
GET  /payment/status/{order_no}     — 查詢訂單狀態
POST /payment/cancel-subscription   — 取消定期定額訂閱
POST /payment/reconcile             — 主動對帳（補抓漏掉的 callback）
"""

import hashlib
import logging
import os
import urllib.parse
from datetime import datetime, timezone, timedelta
from time import time as _time

import httpx

from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

from routers.supabase_client import get_supabase
from routers.auth import _current_user, PLAN_RANK

router = APIRouter(prefix="/payment", tags=["payment"])
log = logging.getLogger(__name__)

# ── 綠界設定 ─────────────────────────────────────────────────────────────────

ECPAY_MERCHANT_ID = os.getenv("ECPAY_MERCHANT_ID", "")
ECPAY_HASH_KEY = os.getenv("ECPAY_HASH_KEY", "")
ECPAY_HASH_IV = os.getenv("ECPAY_HASH_IV", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://16888u.com")

# 綠界回呼用的公網 API URL（不能用 Docker 內部 URL）
API_PUBLIC_URL = os.getenv("API_PUBLIC_URL", "https://api.16888u.com")

# 正式環境
ECPAY_ACTION_URL = "https://payment.ecpay.com.tw/Cashier/AioCheckOut/V5"
ECPAY_PERIOD_QUERY_URL = "https://payment.ecpay.com.tw/Cashier/QueryCreditCardPeriodInfo"
ECPAY_PERIOD_ACTION_URL = "https://payment.ecpay.com.tw/Cashier/CreditCardPeriodAction"
ECPAY_ORDER_QUERY_URL = "https://payment.ecpay.com.tw/Cashier/QueryTradeInfo/V5"
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
    sorted_params = sorted(params.items(), key=lambda x: x[0].lower())
    raw = f"HashKey={ECPAY_HASH_KEY}&" + "&".join(f"{k}={v}" for k, v in sorted_params) + f"&HashIV={ECPAY_HASH_IV}"
    encoded = urllib.parse.quote_plus(raw, safe="").lower()
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest().upper()


def _verify_check_mac_value(params: dict) -> bool:
    """驗證綠界回傳的 CheckMacValue"""
    received = params.get("CheckMacValue", "")
    check_params = {k: v for k, v in params.items() if k != "CheckMacValue"}
    expected = _generate_check_mac_value(check_params)
    return received.upper() == expected.upper()


# ── 訂閱升級（原子化操作）───────────────────────────────────────────────────

def _activate_subscription(sb, user_id: str, plan_key: str, order_no: str,
                           trade_no: str, amount: int, is_periodic: bool):
    """
    將用戶升級到指定方案。所有 DB 操作集中在此函式，
    即使部分失敗也能根據 payment_orders.raw_response 人工補救。
    """
    if is_periodic:
        expires = (datetime.now(timezone.utc) + timedelta(days=35)).isoformat()
    else:
        expires = "2099-12-31T23:59:59+00:00"

    # 1. 先把舊的 active 訂閱標為 superseded（避免重複）
    sb.table("user_subscriptions").update({"status": "superseded"}).eq(
        "user_id", user_id
    ).eq("status", "active").execute()

    # 2. 建立新訂閱
    sb.table("user_subscriptions").insert({
        "user_id": user_id,
        "plan": plan_key,
        "status": "active",
        "expires_at": expires,
        "amount_twd": amount,
        "promo_code": None,
        "metadata": {"ecpay_trade_no": trade_no, "order_no": order_no},
    }).execute()

    # 3. 更新 user_profiles（這是最關鍵的一步）
    sb.table("user_profiles").update({"plan": plan_key}).eq("id", user_id).execute()

    # 4. 記錄事件
    sb.table("subscription_events").insert({
        "user_id": user_id,
        "event_type": "payment_success",
        "to_plan": plan_key,
        "metadata": {"order_no": order_no, "trade_no": trade_no, "amount": amount},
    }).execute()


# ── 建立訂單（內部共用）────────────────────────────────────────────────────

def _build_ecpay_params(user_id: str, plan_key: str) -> tuple[str, dict]:
    """
    建立 payment_orders 記錄並回傳 (order_no, ecpay_params)。
    拋出 HTTPException 表示業務邏輯錯誤。
    """
    if plan_key not in PLANS:
        raise HTTPException(status_code=400, detail="無效的方案")

    plan = PLANS[plan_key]
    sb = get_supabase()

    profile = sb.table("user_profiles").select("plan").eq("id", user_id).single().execute()
    current = (profile.data or {}).get("plan", "free")
    if PLAN_RANK.get(current, 0) >= PLAN_RANK.get(plan_key, 0):
        raise HTTPException(status_code=400, detail="您已經是此方案或更高方案的會員")

    ts = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d%H%M%S")
    order_no = f"TF{ts}{user_id[:4]}"[:20]
    now_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y/%m/%d %H:%M:%S")

    sb.table("payment_orders").insert({
        "order_no": order_no,
        "user_id": user_id,
        "plan": plan_key,
        "amount": plan["amount"],
        "status": "pending",
        "is_periodic": plan.get("is_periodic", False),
    }).execute()

    params = {
        "MerchantID": ECPAY_MERCHANT_ID,
        "MerchantTradeNo": order_no,
        "MerchantTradeDate": now_str,
        "PaymentType": "aio",
        "TotalAmount": plan["amount"],
        "TradeDesc": f"TaifexAI {plan['name']}",
        "ItemName": f"TaifexAI {plan['name']}",
        "ReturnURL": f"{API_PUBLIC_URL}/payment/notify",
        "OrderResultURL": f"{FRONTEND_URL}/05_pricing?payment_result=1",
        "ChoosePayment": "Credit",
        "EncryptType": 1,
        "NeedExtraPaidInfo": "Y",
        "CustomField1": user_id,
        "CustomField2": plan_key,
    }

    if plan.get("is_periodic"):
        params.update({
            "PeriodAmount": plan["amount"],
            "PeriodType": plan["period_type"],
            "Frequency": plan["frequency"],
            "ExecTimes": plan["exec_times"],
            "PeriodReturnURL": f"{API_PUBLIC_URL}/payment/period-notify",
        })

    params["CheckMacValue"] = _generate_check_mac_value(params)
    return order_no, params


def _ecpay_html(params: dict) -> str:
    """產生自動提交到綠界的 HTML 頁面"""
    form_inputs = "\n".join(
        f'    <input type="hidden" name="{k}" value="{v}" />'
        for k, v in params.items()
    )
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>正在跳轉至付款頁面...</title>
  <style>
    body {{ font-family: sans-serif; display:flex; align-items:center;
            justify-content:center; height:100vh; margin:0; background:#0e1117; color:#ccc; }}
    .msg {{ text-align:center; }}
    .spinner {{ width:40px; height:40px; border:4px solid #333;
                border-top-color:#4f8ef7; border-radius:50%;
                animation:spin 0.8s linear infinite; margin:0 auto 16px; }}
    @keyframes spin {{ to {{ transform:rotate(360deg); }} }}
  </style>
</head>
<body>
  <div class="msg">
    <div class="spinner"></div>
    <p>正在跳轉至綠界付款頁面，請稍候...</p>
  </div>
  <form id="ecpay" method="POST" action="{ECPAY_ACTION_URL}">
{form_inputs}
  </form>
  <script>
    window.onload = function() {{
      document.getElementById('ecpay').submit();
    }};
  </script>
</body>
</html>"""


# ── 結帳中介頁（使用者點訂閱按鈕後直接跳轉）────────────────────────────────

@router.get("/checkout", response_class=HTMLResponse)
def payment_checkout(plan: str = "", token: str = ""):
    """
    前端用 st.link_button 跳轉到此頁（帶 plan + token query params）。
    在此建立訂單並立即渲染自動提交至綠界的表單，實現一鍵付款。
    """
    if not token:
        return HTMLResponse("<h2>請先登入</h2>", status_code=401)

    try:
        user = _current_user(f"Bearer {token}")
    except HTTPException as e:
        return HTMLResponse(f"<h2>登入已過期，請重新登入</h2><p>{e.detail}</p>", status_code=401)

    try:
        _, params = _build_ecpay_params(str(user.id), plan)
    except HTTPException as e:
        return HTMLResponse(f"<h2>{e.detail}</h2>", status_code=e.status_code)

    return HTMLResponse(_ecpay_html(params))


# ── 綠界付款結果通知（Server 端回呼）────────────────────────────────────────

@router.post("/notify", response_class=PlainTextResponse)
async def payment_notify(request: Request):
    """
    綠界付款完成後的 Server-to-Server 回呼。
    必須回傳 '1|OK' 字串，否則綠界會重送（最多 3 次）。
    """
    form = await request.form()
    params = dict(form)

    log.info("ECPay notify: order=%s code=%s", params.get("MerchantTradeNo"), params.get("RtnCode"))

    # 驗證 CheckMacValue
    if not _verify_check_mac_value(params):
        log.error("ECPay notify: CheckMacValue verification FAILED for order %s", params.get("MerchantTradeNo"))
        return "0|CheckMacValue Error"

    rtn_code = params.get("RtnCode", "")
    order_no = params.get("MerchantTradeNo", "")
    user_id = params.get("CustomField1", "")
    plan_key = params.get("CustomField2", "")
    trade_no = params.get("TradeNo", "")

    sb = get_supabase()

    # 冪等性檢查：避免重複處理（綠界可能重送）
    existing = sb.table("payment_orders").select("status").eq("order_no", order_no).single().execute()
    if existing.data and existing.data.get("status") == "paid":
        log.info("ECPay notify: order %s already paid, skip", order_no)
        return "1|OK"

    try:
        if rtn_code == "1":
            plan = PLANS.get(plan_key, {})

            # 更新訂單狀態（先存 raw_response，確保有據可查）
            sb.table("payment_orders").update({
                "status": "paid",
                "ecpay_trade_no": trade_no,
                "paid_at": datetime.now(timezone.utc).isoformat(),
                "raw_response": params,
            }).eq("order_no", order_no).execute()

            # 啟動訂閱
            _activate_subscription(
                sb, user_id, plan_key, order_no, trade_no,
                plan.get("amount", 0), plan.get("is_periodic", False),
            )

            log.info("Payment SUCCESS: order=%s user=%s plan=%s", order_no, user_id, plan_key)
        else:
            sb.table("payment_orders").update({
                "status": "failed",
                "ecpay_trade_no": trade_no,
                "raw_response": params,
            }).eq("order_no", order_no).execute()

            log.warning("Payment FAILED: order=%s code=%s msg=%s",
                        order_no, rtn_code, params.get("RtnMsg", ""))
    except Exception:
        # 即使 DB 操作出錯，也要回 1|OK 避免綠界無限重送
        # raw_response 已在前面存入，可事後人工補救
        log.exception("ECPay notify: DB error processing order %s", order_no)

    return "1|OK"


# ── 定期定額每期回呼 ─────────────────────────────────────────────────────────

@router.post("/period-notify", response_class=PlainTextResponse)
async def period_notify(request: Request):
    """
    定期定額每期扣款結果回呼。
    綠界每月自動扣款後 POST 到此端點。
    """
    form = await request.form()
    params = dict(form)

    log.info("ECPay period notify: order=%s code=%s totalSuccessTimes=%s",
             params.get("MerchantTradeNo"), params.get("RtnCode"),
             params.get("TotalSuccessTimes"))

    if not _verify_check_mac_value(params):
        log.error("ECPay period notify: CheckMacValue FAILED for order %s",
                  params.get("MerchantTradeNo"))
        return "0|CheckMacValue Error"

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

    try:
        if rtn_code == "1":
            # 扣款成功 → 延長到期日 35 天（比 30 天多 5 天緩衝）
            new_expires = (datetime.now(timezone.utc) + timedelta(days=35)).isoformat()
            sb.table("user_subscriptions").update({
                "expires_at": new_expires,
                "status": "active",
            }).eq("user_id", user_id).eq("plan", plan_key).eq("status", "active").execute()

            # 確保 user_profiles.plan 也是正確的
            sb.table("user_profiles").update({"plan": plan_key}).eq("id", user_id).execute()

            sb.table("subscription_events").insert({
                "user_id": user_id,
                "event_type": "period_payment_success",
                "to_plan": plan_key,
                "metadata": {
                    "order_no": order_no,
                    "total_success": params.get("TotalSuccessTimes", ""),
                    "exec_status": params.get("ExecStatus", ""),
                },
            }).execute()

            log.info("Period payment SUCCESS: order=%s user=%s success_count=%s",
                     order_no, user_id, params.get("TotalSuccessTimes"))
        else:
            # 扣款失敗 — 記錄但不立即降級（到期日機制會處理）
            sb.table("subscription_events").insert({
                "user_id": user_id,
                "event_type": "period_payment_failed",
                "to_plan": plan_key,
                "metadata": {
                    "order_no": order_no,
                    "rtn_code": rtn_code,
                    "rtn_msg": params.get("RtnMsg", ""),
                    "total_success": params.get("TotalSuccessTimes", ""),
                    "total_fail": params.get("TotalFailTimes", ""),
                },
            }).execute()

            log.warning("Period payment FAILED: order=%s code=%s fail_count=%s",
                        order_no, rtn_code, params.get("TotalFailTimes"))
    except Exception:
        log.exception("ECPay period notify: DB error for order %s", order_no)

    return "1|OK"


# ── 查詢訂單狀態 ─────────────────────────────────────────────────────────────

@router.get("/status/{order_no}")
def payment_status(order_no: str, authorization: str = Header(default="")):
    user = _current_user(authorization)
    user_id = str(user.id)

    sb = get_supabase()
    resp = sb.table("payment_orders").select("*").eq("order_no", order_no).eq("user_id", user_id).maybe_single().execute()
    if not resp or not resp.data:
        raise HTTPException(status_code=404, detail="查無此訂單")

    return resp.data


# ── 取消定期定額訂閱 ─────────────────────────────────────────────────────────

@router.post("/cancel-subscription")
async def cancel_subscription(authorization: str = Header(default="")):
    """
    取消使用者的定期定額訂閱。
    1. 找到最新的 pending/paid 定期訂單，呼叫綠界 CreditCardPeriodAction (Cancel)
    2. 更新 user_subscriptions 狀態為 cancelled
    3. 不立即降級（讓用戶用到期為止）
    """
    user = _current_user(authorization)
    user_id = str(user.id)

    sb = get_supabase()

    # 查找有效的定期訂閱對應的付款訂單
    order_resp = (
        sb.table("payment_orders")
        .select("order_no, ecpay_trade_no, plan, status")
        .eq("user_id", user_id)
        .eq("is_periodic", True)
        .in_("status", ["paid"])
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not order_resp.data:
        raise HTTPException(status_code=404, detail="找不到可取消的定期訂閱")

    order = order_resp.data[0]
    order_no = order["order_no"]

    # 確認用戶目前有 active periodic 訂閱
    sub_resp = (
        sb.table("user_subscriptions")
        .select("id, status")
        .eq("user_id", user_id)
        .eq("status", "active")
        .execute()
    )

    if not sub_resp.data:
        raise HTTPException(status_code=400, detail="您目前沒有有效訂閱")

    # 呼叫綠界 CreditCardPeriodAction Cancel
    ts = str(int(_time()))
    params = {
        "MerchantID": ECPAY_MERCHANT_ID,
        "MerchantTradeNo": order_no,
        "Action": "Cancel",
        "TimeStamp": ts,
    }
    params["CheckMacValue"] = _generate_check_mac_value(params)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                ECPAY_PERIOD_ACTION_URL,
                data=params,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        result = r.text.strip()
        log.info("ECPay CancelPeriod: order=%s result=%s", order_no, result)

        # 綠界回傳 "1|OK" 或含錯誤訊息
        if not result.startswith("1|OK"):
            # 若綠界說已取消（可能已手動取消），也允許繼續
            if "已終止" not in result and "cancel" not in result.lower():
                raise HTTPException(status_code=502, detail=f"綠界取消失敗：{result}")
    except HTTPException:
        raise
    except Exception as e:
        log.error("ECPay CancelPeriod request failed: %s", e)
        raise HTTPException(status_code=502, detail="無法連線綠界，請稍後再試")

    # 更新 DB：訂閱狀態改為 cancelled（保留到期日，讓用戶用到期）
    sb.table("user_subscriptions").update({"status": "cancelled"}).eq(
        "user_id", user_id
    ).eq("status", "active").execute()

    sb.table("payment_orders").update({"status": "cancelled"}).eq(
        "order_no", order_no
    ).execute()

    sb.table("subscription_events").insert({
        "user_id": user_id,
        "event_type": "subscription_cancelled",
        "to_plan": order["plan"],
        "metadata": {"order_no": order_no, "cancelled_by": "user"},
    }).execute()

    log.info("Subscription cancelled: user=%s order=%s", user_id, order_no)
    return {"ok": True, "message": "訂閱已取消，您可繼續使用至當期到期日"}


RECONCILE_SECRET = os.getenv("RECONCILE_SECRET", "")


# ── 主動對帳（補抓漏掉的 callback）─────────────────────────────────────────

@router.post("/reconcile")
async def reconcile_pending_orders(
    authorization: str = Header(default=""),
    x_reconcile_secret: str = Header(default="", alias="X-Reconcile-Secret"),
):
    """
    主動向綠界查詢所有超過 10 分鐘仍 pending 的訂單，
    補處理漏掉的付款成功通知。
    授權方式二擇一：
      - Bearer token（一般用戶/管理員）
      - X-Reconcile-Secret header（Airflow 等內部服務）
    """
    if x_reconcile_secret and RECONCILE_SECRET and x_reconcile_secret == RECONCILE_SECRET:
        pass  # 內部服務授權通過
    else:
        _current_user(authorization)  # 否則驗證 JWT

    sb = get_supabase()

    # 只撈超過 10 分鐘的 pending 訂單
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    pending_resp = (
        sb.table("payment_orders")
        .select("order_no, user_id, plan, amount, is_periodic, created_at")
        .eq("status", "pending")
        .lt("created_at", cutoff)
        .execute()
    )

    orders = pending_resp.data or []
    if not orders:
        return {"checked": 0, "recovered": 0, "message": "沒有需要對帳的訂單"}

    recovered = []
    checked = 0

    async with httpx.AsyncClient(timeout=15) as client:
        for order in orders:
            order_no = order["order_no"]
            ts = str(int(_time()))
            params = {
                "MerchantID": ECPAY_MERCHANT_ID,
                "MerchantTradeNo": order_no,
                "TimeStamp": ts,
                "PlatformID": "",
            }
            params["CheckMacValue"] = _generate_check_mac_value(params)

            try:
                r = await client.post(
                    ECPAY_ORDER_QUERY_URL,
                    data=params,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                # 回傳 URL-encoded 字串，如 TradeStatus=1&PaymentType=Credit&...
                result = dict(urllib.parse.parse_qsl(r.text))
                checked += 1
                log.info("Reconcile query: order=%s status=%s",
                         order_no, result.get("TradeStatus"))

                trade_status = result.get("TradeStatus", "")
                trade_no = result.get("TradeNo", "")

                if trade_status == "1":
                    # 付款成功但 callback 漏掉 → 補處理
                    existing = sb.table("payment_orders").select("status").eq(
                        "order_no", order_no
                    ).maybe_single().execute()
                    if existing and existing.data and existing.data.get("status") == "pending":
                        sb.table("payment_orders").update({
                            "status": "paid",
                            "ecpay_trade_no": trade_no,
                            "paid_at": datetime.now(timezone.utc).isoformat(),
                            "raw_response": result,
                        }).eq("order_no", order_no).execute()

                        plan = PLANS.get(order["plan"], {})
                        _activate_subscription(
                            sb, order["user_id"], order["plan"], order_no,
                            trade_no, order.get("amount", 0), order.get("is_periodic", False),
                        )
                        recovered.append(order_no)
                        log.info("Reconcile RECOVERED: order=%s user=%s", order_no, order["user_id"])

                elif trade_status in ("0", "10200095"):
                    # 付款失敗或取消
                    sb.table("payment_orders").update({
                        "status": "failed",
                        "raw_response": result,
                    }).eq("order_no", order_no).execute()
                    log.info("Reconcile marked FAILED: order=%s", order_no)

            except Exception as e:
                log.error("Reconcile query failed for order %s: %s", order_no, e)

    return {
        "checked": checked,
        "recovered": len(recovered),
        "recovered_orders": recovered,
        "message": f"對帳完成：共檢查 {checked} 筆，補處理 {len(recovered)} 筆",
    }
