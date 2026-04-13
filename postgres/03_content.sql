-- ============================================================
-- Migration：新增研究文章與每日操作日誌 table
-- 適用於已存在的 DB（VPS 上手動執行）
-- ============================================================

-- 研究文章
CREATE TABLE IF NOT EXISTS research_articles (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR(200) NOT NULL,
    summary         TEXT,                           -- 摘要（免費可見）
    content         TEXT NOT NULL,                  -- 全文（目前免費，未來可付費）
    tags            TEXT[],                         -- 標籤，例如 {'外資','PCR','回測'}
    author          VARCHAR(100) DEFAULT 'AI 研究員',
    published_at    TIMESTAMPTZ DEFAULT NOW(),
    is_published    BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_articles_published_at ON research_articles (published_at DESC);

-- 每日操作日誌
CREATE TABLE IF NOT EXISTS daily_operations (
    id                  SERIAL PRIMARY KEY,
    trade_date          DATE NOT NULL,
    title               VARCHAR(200) NOT NULL,          -- 標題，例如「外資連三日減倉，做空台指」
    trigger_indicators  TEXT,                           -- 觸發指標描述
    direction           VARCHAR(20),                    -- 做多/做空/出場/觀望
    entry_price         DECIMAL(10,2),                  -- 進場價格（可空）
    entry_contracts     INTEGER,                        -- 口數（可空）
    exit_price          DECIMAL(10,2),                  -- 出場價格（可空）
    pnl                 DECIMAL(12,2),                  -- 損益（可空，未出場留空）
    pnl_note            VARCHAR(200),                   -- 損益備註，例如「+12,000（+0.6%）」
    content             TEXT,                           -- 自由書寫內文
    is_published        BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_ops_trade_date ON daily_operations (trade_date DESC);
