"""
Auth Router — 使用者註冊 / 登入 / 個人資料
POST /auth/register
POST /auth/login
GET  /auth/me
"""

import hashlib
import os
import secrets
from datetime import datetime, timezone, timedelta

import jwt
from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, EmailStr

from routers.db import get_conn

router = APIRouter(prefix="/auth", tags=["auth"])

JWT_SECRET = os.getenv("JWT_SECRET", "changeme")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

PLAN_RANK = {"free": 0, "pro": 1, "ultimate": 2}


# ── helpers ───────────────────────────────────────────────────────────────────

def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 260_000
    ).hex()


def _make_token(user_id: int, email: str, plan: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "plan": plan,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已過期，請重新登入")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="無效 Token")


def _current_user(authorization: str) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="請先登入")
    return _decode_token(authorization[7:])


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
    password = body.password

    if len(password) < 6:
        raise HTTPException(status_code=422, detail="密碼至少 6 個字元")

    with get_conn() as conn:
        with conn.cursor() as cur:
            # 檢查 email 是否已存在
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="此 Email 已註冊")

            # 驗證優惠碼
            promo = None
            promo_code = body.promo_code.strip().upper() if body.promo_code else ""
            if promo_code:
                cur.execute(
                    """SELECT id, target_plan, discount_type, discount_value, max_uses, used_count
                       FROM promo_codes
                       WHERE code = %s AND is_active = TRUE
                         AND (expires_at IS NULL OR expires_at > NOW())""",
                    (promo_code,),
                )
                promo = cur.fetchone()
                if not promo:
                    raise HTTPException(status_code=400, detail="優惠碼無效或已過期")
                if promo["max_uses"] and promo["used_count"] >= promo["max_uses"]:
                    raise HTTPException(status_code=400, detail="優惠碼使用次數已達上限")

            # 建立使用者
            salt = secrets.token_hex(32)
            pw_hash = _hash_password(password, salt)
            initial_plan = promo["target_plan"] if promo else "free"
            referral_source = "promo_code" if promo_code else "organic"

            cur.execute(
                """INSERT INTO users
                     (email, password_hash, password_salt, display_name, plan,
                      referral_source, promo_code_used,
                      utm_source, utm_medium, utm_campaign)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (
                    email, pw_hash, salt,
                    body.display_name or email.split("@")[0],
                    initial_plan, referral_source, promo_code or None,
                    body.utm_source or None, body.utm_medium or None,
                    body.utm_campaign or None,
                ),
            )
            user_id = cur.fetchone()["id"]

            # 若有優惠碼 → 建立訂閱紀錄
            if promo:
                months = promo["discount_value"] if promo["discount_type"] == "free_month" else 1
                expires = datetime.now(timezone.utc) + timedelta(days=30 * months)
                cur.execute(
                    """INSERT INTO user_subscriptions
                         (user_id, plan, status, expires_at, amount_twd, promo_code)
                       VALUES (%s, %s, 'active', %s, 0, %s)""",
                    (user_id, initial_plan, expires, promo_code),
                )
                # 更新優惠碼使用次數
                cur.execute(
                    "UPDATE promo_codes SET used_count = used_count + 1 WHERE id = %s",
                    (promo["id"],),
                )

            # 記錄事件
            ip = request.client.host if request.client else None
            ua = request.headers.get("user-agent", "")
            cur.execute(
                """INSERT INTO subscription_events
                     (user_id, event_type, from_plan, to_plan, promo_code, ip_address, user_agent)
                   VALUES (%s, 'registered', NULL, %s, %s, %s, %s)""",
                (user_id, initial_plan, promo_code or None, ip, ua),
            )

            conn.commit()

    token = _make_token(user_id, email, initial_plan)
    return {"token": token, "plan": initial_plan, "email": email}


@router.post("/login")
def login(body: LoginRequest, request: Request):
    email = body.email.lower().strip()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, password_hash, password_salt, plan, is_active FROM users WHERE email = %s",
                (email,),
            )
            user = cur.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="Email 或密碼錯誤")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="帳號已停用")

    pw_hash = _hash_password(body.password, user["password_salt"])
    if pw_hash != user["password_hash"]:
        raise HTTPException(status_code=401, detail="Email 或密碼錯誤")

    # 更新登入紀錄
    with get_conn() as conn:
        with conn.cursor() as cur:
            ip = request.client.host if request.client else None
            ua = request.headers.get("user-agent", "")
            cur.execute(
                """UPDATE users SET last_login_at = NOW(), login_count = login_count + 1
                   WHERE id = %s""",
                (user["id"],),
            )
            cur.execute(
                """INSERT INTO subscription_events
                     (user_id, event_type, ip_address, user_agent)
                   VALUES (%s, 'login', %s, %s)""",
                (user["id"], ip, ua),
            )
            conn.commit()

    token = _make_token(user["id"], email, user["plan"])
    return {"token": token, "plan": user["plan"], "email": email}


@router.get("/me")
def me(authorization: str = Header(default="")):
    payload = _current_user(authorization)
    user_id = int(payload["sub"])

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, email, display_name, plan, created_at, last_login_at, login_count
                   FROM users WHERE id = %s""",
                (user_id,),
            )
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="使用者不存在")

            # 取最新有效訂閱
            cur.execute(
                """SELECT plan, status, started_at, expires_at
                   FROM user_subscriptions
                   WHERE user_id = %s AND status = 'active'
                   ORDER BY started_at DESC LIMIT 1""",
                (user_id,),
            )
            sub = cur.fetchone()

    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "plan": user["plan"],
        "created_at": str(user["created_at"])[:10],
        "last_login_at": str(user["last_login_at"])[:10] if user["last_login_at"] else None,
        "login_count": user["login_count"],
        "subscription": dict(sub) if sub else None,
    }
