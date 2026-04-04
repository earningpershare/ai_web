-- ============================================================
-- 在 Supabase SQL Editor 執行此腳本
-- 建立會員相關資料表（auth 本體由 Supabase Auth 管理）
-- ============================================================

-- ── 使用者個人資料（擴展 Supabase auth.users）─────────────────
CREATE TABLE IF NOT EXISTS public.user_profiles (
    id              UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
    display_name    VARCHAR(100),
    plan            VARCHAR(20)  NOT NULL DEFAULT 'free',
    referral_source VARCHAR(100),
    promo_code_used VARCHAR(50),
    utm_source      VARCHAR(100),
    utm_medium      VARCHAR(100),
    utm_campaign    VARCHAR(100),
    login_count     INTEGER      NOT NULL DEFAULT 0,
    last_login_at   TIMESTAMPTZ,
    metadata        JSONB        NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── 優惠碼 ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.promo_codes (
    id             SERIAL       PRIMARY KEY,
    code           VARCHAR(50)  NOT NULL UNIQUE,
    target_plan    VARCHAR(20)  NOT NULL DEFAULT 'pro',
    discount_type  VARCHAR(30)  NOT NULL DEFAULT 'free_month',
    discount_value INTEGER      NOT NULL DEFAULT 1,
    max_uses       INTEGER,
    used_count     INTEGER      NOT NULL DEFAULT 0,
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    expires_at     TIMESTAMPTZ,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── 訂閱紀錄 ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.user_subscriptions (
    id          SERIAL      PRIMARY KEY,
    user_id     UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    plan        VARCHAR(20) NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ,
    amount_twd  INTEGER     DEFAULT 0,
    promo_code  VARCHAR(50),
    metadata    JSONB       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 事件紀錄（分析用）────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.subscription_events (
    id          SERIAL      PRIMARY KEY,
    user_id     UUID        REFERENCES auth.users(id) ON DELETE CASCADE,
    event_type  VARCHAR(50) NOT NULL,
    from_plan   VARCHAR(20),
    to_plan     VARCHAR(20),
    promo_code  VARCHAR(50),
    ip_address  VARCHAR(45),
    user_agent  TEXT,
    metadata    JSONB       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 索引 ──────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_user_profiles_plan          ON public.user_profiles (plan);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id  ON public.user_subscriptions (user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_status   ON public.user_subscriptions (status);
CREATE INDEX IF NOT EXISTS idx_subscription_events_user_id ON public.subscription_events (user_id);
CREATE INDEX IF NOT EXISTS idx_subscription_events_type    ON public.subscription_events (event_type);

-- ── 預設優惠碼 ────────────────────────────────────────────────
INSERT INTO public.promo_codes (code, target_plan, discount_type, discount_value, max_uses)
VALUES
    ('LAUNCH2026', 'pro',      'free_month', 1, NULL),
    ('ULTIMATE88', 'ultimate', 'free_month', 1, NULL)
ON CONFLICT (code) DO NOTHING;

-- ── Row Level Security ────────────────────────────────────────
ALTER TABLE public.user_profiles      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscription_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.promo_codes        ENABLE ROW LEVEL SECURITY;

-- 使用者只能看自己的資料（service_role key 會繞過 RLS）
CREATE POLICY "own profile"       ON public.user_profiles
    FOR SELECT USING (auth.uid() = id);
CREATE POLICY "own subscriptions" ON public.user_subscriptions
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "promo read"        ON public.promo_codes
    FOR SELECT USING (is_active = TRUE);

-- ── 自動更新 updated_at ───────────────────────────────────────
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END; $$;

CREATE TRIGGER trg_user_profiles_updated_at
    BEFORE UPDATE ON public.user_profiles
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
