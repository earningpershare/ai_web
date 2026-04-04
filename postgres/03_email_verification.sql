-- Migration: 新增 Email 驗證欄位到 users 表
-- 執行方式：psql -U admin -d financial_db -f 03_email_verification.sql

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS email_verified      BOOLEAN      DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS verification_token  VARCHAR(64),
    ADD COLUMN IF NOT EXISTS token_expires_at    TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_users_verification_token
    ON users (verification_token)
    WHERE verification_token IS NOT NULL;
