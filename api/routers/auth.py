"""
Auth Router — 使用者註冊 / 登入 / 個人資料
後端使用 Supabase Auth，個資與金融資料物理隔離

POST /auth/register
POST /auth/login
GET  /auth/me
POST /auth/resend-verification
"""

import logging
import os
import uuid as _uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, EmailStr

from routers.supabase_client import get_supabase

# 用固定 namespace + user_id 確定性生成 VLESS UUID，不需要 DB 欄位
_VLESS_NAMESPACE = _uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def vless_uuid_for(user_id: str) -> str:
    """從 user_id 確定性產生唯一的 VLESS UUID"""
    return str(_uuid.uuid5(_VLESS_NAMESPACE, user_id))

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger(__name__)

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://16888u.com")
PLAN_RANK = {"free": 0, "pro": 1, "ultimate": 2}


# ── helpers ───────────────────────────────────────────────────────────────────

def _current_user(authorization: str) -> dict:
    """驗證 Supabase JWT，回傳 user dict"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="請先登入")
    token = authorization[7:]
    try:
        sb = get_supabase()
        resp = sb.auth.get_user(token)
        if not resp or not resp.user:
            raise HTTPException(status_code=401, detail="無效 Token")
        return resp.user
    except HTTPException:
        raise
    except Exception as e:
        log.warning("Token 驗證失敗: %s", e)
        raise HTTPException(status_code=401, detail="Token 已過期或無效，請重新登入")


def _get_profile(user_id: str) -> dict:
    sb = get_supabase()
    resp = sb.table("user_profiles").select("*").eq("id", user_id).single().execute()
    return resp.data or {}


def _get_active_subscription(user_id: str) -> dict | None:
    """取得有效訂閱；若已過期則自動降級為 free"""
    sb = get_supabase()
    resp = (
        sb.table("user_subscriptions")
        .select("plan, status, started_at, expires_at")
        .eq("user_id", user_id)
        .eq("status", "active")
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
            # 訂閱已過期 → 降級
            sb.table("user_subscriptions").update({"status": "expired"}).eq(
                "user_id", user_id
            ).eq("status", "active").execute()
            sb.table("user_profiles").update({"plan": "free"}).eq("id", user_id).execute()
            sb.table("subscription_events").insert({
                "user_id": user_id,
                "event_type": "subscription_expired",
                "to_plan": "free",
            }).execute()
            log.info("Subscription expired for user %s, downgraded to free", user_id)
            return None
    return sub


# ── schemas ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str = ""
    promo_code: str = ""
    utm_source: str = ""
    utm_medium: str = ""
    utm_campaign: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register")
def register(body: RegisterRequest, request: Request):
    email = body.email.lower().strip()

    if len(body.password) < 6:
        raise HTTPException(status_code=422, detail="密碼至少 6 個字元")

    sb = get_supabase()

    # 驗證優惠碼
    promo = None
    promo_code = body.promo_code.strip().upper() if body.promo_code else ""
    if promo_code:
        resp = (
            sb.table("promo_codes")
            .select("id, target_plan, discount_type, discount_value, max_uses, used_count")
            .eq("code", promo_code)
            .eq("is_active", True)
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=400, detail="優惠碼無效或已過期")
        promo = resp.data[0]
        if promo["max_uses"] and promo["used_count"] >= promo["max_uses"]:
            raise HTTPException(status_code=400, detail="優惠碼使用次數已達上限")

    initial_plan = promo["target_plan"] if promo else "free"

    # Supabase Auth 註冊（自動寄驗證信）
    try:
        sign_up_resp = sb.auth.sign_up({
            "email": email,
            "password": body.password,
            "options": {
                "email_redirect_to": f"{FRONTEND_URL}/?verified=1",
                "data": {"display_name": body.display_name or email.split("@")[0]},
            },
        })
    except Exception as e:
        err = str(e).lower()
        if "already registered" in err or "already been registered" in err:
            raise HTTPException(status_code=409, detail="此 Email 已註冊")
        if "rate limit" in err or "over_email_send_rate_limit" in err:
            now = datetime.now(timezone.utc)
            minutes_until_reset = 60 - now.minute
            log.warning("Supabase email rate limit hit: %s", e)
            raise HTTPException(
                status_code=429,
                detail=(
                    f"驗證信發送次數已達上限（每小時最多 4 封），"
                    f"系統暫時無法寄出驗證信。"
                    f"請約 {minutes_until_reset} 分鐘後再試。"
                ),
            )
        if "confirmation email" in err or "sending" in err or "smtp" in err:
            log.error("Supabase email delivery error: %s", e)
            raise HTTPException(
                status_code=503,
                detail="驗證信發送失敗（郵件服務暫時異常），帳號可能已建立，請稍後使用相同 Email 重新嘗試，或聯絡管理員。",
            )
        log.error("Supabase sign_up error: %s", e)
        raise HTTPException(status_code=500, detail="註冊失敗，請稍後再試")

    user = sign_up_resp.user
    if not user:
        raise HTTPException(status_code=500, detail="註冊失敗，請稍後再試")

    # sign_up 會觸發 auth state change，導致 postgrest 切換成 user token，還原 service_role
    sb.postgrest.auth(os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))

    user_id = str(user.id)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")

    # 建立 user_profiles
    sb.table("user_profiles").insert({
        "id": user_id,
        "display_name": body.display_name or email.split("@")[0],
        "plan": initial_plan,
        "referral_source": "promo_code" if promo_code else "organic",
        "promo_code_used": promo_code or None,
        "utm_source": body.utm_source or None,
        "utm_medium": body.utm_medium or None,
        "utm_campaign": body.utm_campaign or None,
    }).execute()

    # 若有優惠碼 → 建立訂閱
    if promo:
        months = promo["discount_value"] if promo["discount_type"] == "free_month" else 1
        expires = (datetime.now(timezone.utc) + timedelta(days=30 * months)).isoformat()
        sb.table("user_subscriptions").insert({
            "user_id": user_id,
            "plan": initial_plan,
            "status": "active",
            "expires_at": expires,
            "amount_twd": 0,
            "promo_code": promo_code,
        }).execute()
        sb.table("promo_codes").update(
            {"used_count": promo["used_count"] + 1}
        ).eq("id", promo["id"]).execute()

    # 記錄事件
    sb.table("subscription_events").insert({
        "user_id": user_id,
        "event_type": "registered",
        "to_plan": initial_plan,
        "promo_code": promo_code or None,
        "ip_address": ip,
        "user_agent": ua,
    }).execute()

    # Supabase 開啟 email 確認時 session 為 None（正常行為）
    session = sign_up_resp.session
    if session:
        # email 確認已關閉，直接回 token（不建議在 production 使用）
        return {
            "token": session.access_token,
            "plan": initial_plan,
            "email": email,
            "email_verified": True,
            "status": "logged_in",
        }
    else:
        # 正常流程：email 待驗證，不回 token
        return {
            "token": "",
            "plan": initial_plan,
            "email": email,
            "email_verified": False,
            "status": "verification_sent",
        }


@router.post("/login")
def login(body: LoginRequest, request: Request):
    email = body.email.lower().strip()
    sb = get_supabase()

    try:
        resp = sb.auth.sign_in_with_password({"email": email, "password": body.password})
    except Exception as e:
        err = str(e).lower()
        if "email not confirmed" in err or "not confirmed" in err:
            raise HTTPException(status_code=403, detail="此帳號信箱尚未驗證，請至信箱點擊驗證連結")
        if "invalid" in err or "credentials" in err or "password" in err:
            raise HTTPException(status_code=401, detail="Email 或密碼錯誤")
        log.error("Supabase login error: %s", e)
        raise HTTPException(status_code=401, detail="登入失敗，請稍後再試")

    user = resp.user
    session = resp.session
    if not user or not session:
        raise HTTPException(status_code=401, detail="Email 或密碼錯誤")

    # sign_in_with_password 會觸發 auth state change，導致 postgrest 切換成 user token，還原 service_role
    sb.postgrest.auth(os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))

    user_id = str(user.id)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")

    # 更新登入紀錄
    profile = _get_profile(user_id)
    sb.table("user_profiles").update({
        "last_login_at": datetime.now(timezone.utc).isoformat(),
        "login_count": (profile.get("login_count") or 0) + 1,
    }).eq("id", user_id).execute()

    sb.table("subscription_events").insert({
        "user_id": user_id,
        "event_type": "login",
        "ip_address": ip,
        "user_agent": ua,
    }).execute()

    # 檢查訂閱是否過期（會自動降級）
    _get_active_subscription(user_id)
    # 重新讀取 plan（可能已被降級）
    profile = _get_profile(user_id)
    plan = (profile.get("plan") or "free")
    email_verified = bool(user.email_confirmed_at)

    return {
        "token": session.access_token,
        "plan": plan,
        "email": email,
        "email_verified": email_verified,
    }


@router.get("/me")
def me(authorization: str = Header(default="")):
    user = _current_user(authorization)
    user_id = str(user.id)

    profile = _get_profile(user_id)
    sub = _get_active_subscription(user_id)

    plan = profile.get("plan", "free")
    return {
        "id": user_id,
        "email": user.email,
        "display_name": profile.get("display_name", ""),
        "plan": plan,
        "email_verified": bool(user.email_confirmed_at),
        "created_at": str(user.created_at)[:10] if user.created_at else None,
        "last_login_at": str(profile.get("last_login_at", ""))[:10] or None,
        "login_count": profile.get("login_count", 0),
        "subscription": sub,
        "vless_uuid": vless_uuid_for(user_id) if PLAN_RANK.get(plan, 0) >= PLAN_RANK["pro"] else None,
    }


XRAY_SYNC_SECRET = os.getenv("XRAY_SYNC_SECRET", "change-me-in-production")


@router.get("/vless-clients")
def vless_clients(secret: str = ""):
    """供 Xray 同步腳本呼叫，回傳所有 pro+ 用戶的 VLESS UUID 與 email"""
    if secret != XRAY_SYNC_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    sb = get_supabase()
    resp = (
        sb.table("user_profiles")
        .select("id, display_name, plan")
        .in_("plan", ["pro", "ultimate"])
        .execute()
    )

    clients = []
    for row in resp.data or []:
        clients.append({
            "id": vless_uuid_for(row["id"]),
            "email": row.get("display_name", row["id"]),
            "level": 0,
        })
    return {"clients": clients}


class ResendByEmailRequest(BaseModel):
    email: EmailStr


@router.post("/resend-by-email")
def resend_by_email(body: ResendByEmailRequest):
    """不需要 token — 供尚未登入的新用戶重送驗證信"""
    sb = get_supabase()
    try:
        sb.auth.resend({
            "type": "signup",
            "email": body.email.lower().strip(),
            "options": {"email_redirect_to": f"{FRONTEND_URL}/07_verify_email"},
        })
    except Exception as e:
        log.error("Resend by email error: %s", e)
        raise HTTPException(status_code=503, detail="今日驗證信額度已滿，請明天再試")
    return {"ok": True, "message": "驗證信已重新寄出"}


@router.post("/resend-verification")
def resend_verification(authorization: str = Header(default="")):
    user = _current_user(authorization)
    if user.email_confirmed_at:
        raise HTTPException(status_code=400, detail="信箱已完成驗證")

    sb = get_supabase()
    try:
        sb.auth.resend({"type": "signup", "email": user.email,
                        "options": {"email_redirect_to": f"{FRONTEND_URL}/07_verify_email"}})
    except Exception as e:
        log.error("Resend verification error: %s", e)
        raise HTTPException(status_code=503, detail="今日驗證信額度已滿，請明天再試")

    return {"ok": True, "message": "驗證信已重新寄出"}
