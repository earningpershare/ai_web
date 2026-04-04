-- ============================================================
-- Auth & Subscription Schema
-- ============================================================

-- 使用者資料表
CREATE TABLE IF NOT EXISTS users (
    id                  SERIAL PRIMARY KEY,
    email               VARCHAR(255) NOT NULL UNIQUE,
    password_hash       VARCHAR(255) NOT NULL,
    password_salt       VARCHAR(64)  NOT NULL,
    display_name        VARCHAR(100),
    plan                VARCHAR(20)  NOT NULL DEFAULT 'free',   -- free / pro / ultimate
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    email_verified      BOOLEAN      NOT NULL DEFAULT FALSE,
    -- 彈性分析欄位
    referral_source     VARCHAR(100),                           -- 來源渠道（自然流量、優惠碼等）
    promo_code_used     VARCHAR(50),                            -- 使用的優惠碼
    utm_source          VARCHAR(100),
    utm_medium          VARCHAR(100),
    utm_campaign        VARCHAR(100),
    last_login_at       TIMESTAMPTZ,
    login_count         INT          NOT NULL DEFAULT 0,
    metadata            JSONB        NOT NULL DEFAULT '{}',     -- 預留彈性欄位
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 訂閱紀錄
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id                  SERIAL PRIMARY KEY,
    user_id             INT          NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan                VARCHAR(20)  NOT NULL,                  -- pro / ultimate
    status              VARCHAR(20)  NOT NULL DEFAULT 'active', -- active / cancelled / expired / trial
    started_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ,
    cancelled_at        TIMESTAMPTZ,
    amount_twd          INT,                                    -- 實收金額（台幣）
    payment_method      VARCHAR(50),                            -- 付款方式（預留）
    payment_ref         VARCHAR(200),                           -- 金流交易編號（預留）
    promo_code          VARCHAR(50),                            -- 本次訂閱使用的優惠碼
    metadata            JSONB        NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 優惠碼
CREATE TABLE IF NOT EXISTS promo_codes (
    id                  SERIAL PRIMARY KEY,
    code                VARCHAR(50)  NOT NULL UNIQUE,
    description         VARCHAR(200),
    discount_type       VARCHAR(20)  NOT NULL DEFAULT 'free_month', -- free_month / percent / fixed
    discount_value      INT          NOT NULL DEFAULT 1,            -- 月數 / 折扣%數 / 折扣金額
    target_plan         VARCHAR(20)  NOT NULL DEFAULT 'pro',        -- 適用方案
    max_uses            INT,                                        -- NULL = 無限制
    used_count          INT          NOT NULL DEFAULT 0,
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    expires_at          TIMESTAMPTZ,
    metadata            JSONB        NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 訂閱事件日誌（完整 audit trail）
CREATE TABLE IF NOT EXISTS subscription_events (
    id                  SERIAL PRIMARY KEY,
    user_id             INT          NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type          VARCHAR(50)  NOT NULL, -- registered / upgraded / downgraded / cancelled / promo_applied / login
    from_plan           VARCHAR(20),
    to_plan             VARCHAR(20),
    promo_code          VARCHAR(50),
    ip_address          VARCHAR(45),
    user_agent          TEXT,
    metadata            JSONB        NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_users_email           ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_plan            ON users (plan);
CREATE INDEX IF NOT EXISTS idx_users_created_at      ON users (created_at);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user    ON user_subscriptions (user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status  ON user_subscriptions (status);
CREATE INDEX IF NOT EXISTS idx_sub_events_user       ON subscription_events (user_id);
CREATE INDEX IF NOT EXISTS idx_sub_events_type       ON subscription_events (event_type);
CREATE INDEX IF NOT EXISTS idx_sub_events_created    ON subscription_events (created_at);

-- 預設優惠碼範例（可依需求修改）
INSERT INTO promo_codes (code, description, discount_type, discount_value, target_plan, max_uses)
VALUES
    ('LAUNCH2026', '創站優惠 — 進階版免費一個月', 'free_month', 1, 'pro', 100),
    ('ULTIMATE88', '終極版優惠碼', 'free_month', 1, 'ultimate', 20)
ON CONFLICT (code) DO NOTHING;
