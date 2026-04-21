"""
訂閱核心邏輯 — 不依賴 FastAPI，方便單元測試。
auth.py / payment.py 的 router 呼叫這裡的函式。
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

log = logging.getLogger(__name__)

PLAN_RANK = {"free": 0, "pro": 1, "ultimate": 2}


def get_active_subscription(sb, user_id: str) -> Optional[dict]:
    """
    取得有效訂閱；若已過期則自動降級為 free；
    若 profile.plan 落後於訂閱則 self-heal。
    回傳訂閱 dict 或 None（無訂閱 / 已過期）。
    """
    resp = (
        sb.table("user_subscriptions")
        .select("plan, status, started_at, expires_at")
        .eq("user_id", user_id)
        .in_("status", ["active", "cancelled", "superseded"])
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None

    sub = resp.data[0]
    expires = sub.get("expires_at")
    if expires:
        expires_dt = datetime.fromisoformat(expires)
        if expires_dt < datetime.now(timezone.utc):
            sb.table("user_subscriptions").update({"status": "expired"}).eq(
                "user_id", user_id
            ).in_("status", ["active", "cancelled", "superseded"]).execute()
            sb.table("user_profiles").update({"plan": "free"}).eq("id", user_id).execute()
            sb.table("subscription_events").insert({
                "user_id": user_id,
                "event_type": "subscription_expired",
                "to_plan": "free",
            }).execute()
            log.info("Subscription expired for user %s, downgraded to free", user_id)
            return None

    # Self-heal：profile.plan 落後訂閱時自動補正
    try:
        prof = (
            sb.table("user_profiles")
            .select("plan")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        if prof.data and PLAN_RANK.get(sub["plan"], 0) > PLAN_RANK.get(prof.data.get("plan", "free"), 0):
            log.warning("plan self-heal: user=%s profile=%s → sub=%s",
                        user_id, prof.data.get("plan"), sub["plan"])
            sb.table("user_profiles").update({"plan": sub["plan"]}).eq("id", user_id).execute()
    except Exception as e:
        log.warning("plan self-heal failed (non-critical): %s", e)

    return sub


def activate_subscription(sb, user_id: str, plan_key: str, order_no: str,
                          trade_no: str, amount: int, is_periodic: bool) -> None:
    """
    付款成功後升級訂閱。
    1. 舊的 active/cancelled 記錄標為 superseded
    2. 建立新 active 訂閱
    3. 更新 user_profiles.plan
    4. 插入 subscription_events
    """
    if is_periodic:
        expires = (datetime.now(timezone.utc) + timedelta(days=35)).isoformat()
    else:
        expires = "2099-12-31T23:59:59+00:00"

    sb.table("user_subscriptions").update({"status": "superseded"}).eq(
        "user_id", user_id
    ).in_("status", ["active", "cancelled"]).execute()

    sb.table("user_subscriptions").insert({
        "user_id": user_id,
        "plan": plan_key,
        "status": "active",
        "expires_at": expires,
        "amount_twd": amount,
        "promo_code": None,
        "metadata": {"ecpay_trade_no": trade_no, "order_no": order_no},
    }).execute()

    sb.table("user_profiles").update({"plan": plan_key}).eq("id", user_id).execute()

    sb.table("subscription_events").insert({
        "user_id": user_id,
        "event_type": "payment_success",
        "to_plan": plan_key,
        "metadata": {"order_no": order_no, "trade_no": trade_no, "amount": amount},
    }).execute()


def check_can_purchase(sb, user_id: str, plan_key: str) -> Tuple[bool, str]:
    """
    檢查用戶是否可以購買 plan_key。
    回傳 (allowed: bool, reason: str)。
    reason 在 allowed=False 時說明原因。
    """
    if plan_key not in PLAN_RANK:
        return False, "無效的方案"

    profile = (
        sb.table("user_profiles")
        .select("plan")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    if not profile.data:
        return False, "找不到用戶資料，請重新登入"

    current = profile.data.get("plan", "free")

    # 查最新訂閱狀態
    active_sub = (
        sb.table("user_subscriptions")
        .select("status")
        .eq("user_id", user_id)
        .in_("status", ["active", "cancelled", "superseded"])
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )
    is_cancelled = bool(active_sub.data) and active_sub.data[0]["status"] == "cancelled"

    if PLAN_RANK.get(current, 0) >= PLAN_RANK.get(plan_key, 0) and not is_cancelled:
        return False, "您已經是此方案或更高方案的會員"

    return True, ""
