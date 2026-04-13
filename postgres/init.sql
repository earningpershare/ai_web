-- ============================================================
-- Financial Database Schema
-- Taiwan Futures Exchange (TAIFEX) Data
-- ============================================================

-- 台指期貨每日行情
CREATE TABLE IF NOT EXISTS tx_futures_daily (
    id              SERIAL PRIMARY KEY,
    trade_date      DATE NOT NULL,
    contract_code   VARCHAR(20) NOT NULL,
    contract_month  VARCHAR(30) NOT NULL,
    open_price      NUMERIC(10, 2),
    high_price      NUMERIC(10, 2),
    low_price       NUMERIC(10, 2),
    close_price     NUMERIC(10, 2),
    volume          BIGINT,
    open_interest   BIGINT,
    settlement_price NUMERIC(10, 2),
    session         VARCHAR(10) NOT NULL DEFAULT '一般',
    last_edit_time  TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (trade_date, contract_code, contract_month, session)
);

-- 台指選擇權每日行情
CREATE TABLE IF NOT EXISTS txo_options_daily (
    id              SERIAL PRIMARY KEY,
    trade_date      DATE NOT NULL,
    contract_code   VARCHAR(20) NOT NULL,
    contract_month  VARCHAR(30) NOT NULL,
    strike_price    NUMERIC(10, 2) NOT NULL,
    call_put        CHAR(1) NOT NULL,
    open_price      NUMERIC(10, 4),
    high_price      NUMERIC(10, 4),
    low_price       NUMERIC(10, 4),
    close_price     NUMERIC(10, 4),
    volume          BIGINT,
    open_interest   BIGINT,
    settlement_price NUMERIC(10, 4),
    session         VARCHAR(10) NOT NULL DEFAULT '一般',
    last_edit_time  TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (trade_date, contract_code, contract_month, strike_price, call_put, session)
);

-- Put/Call Ratio
CREATE TABLE IF NOT EXISTS put_call_ratio (
    id              SERIAL PRIMARY KEY,
    trade_date      DATE NOT NULL UNIQUE,
    pc_oi_ratio     NUMERIC(8, 4),
    pc_vol_ratio    NUMERIC(8, 4),
    call_oi         BIGINT,
    put_oi          BIGINT,
    call_volume     BIGINT,
    put_volume      BIGINT,
    last_edit_time  TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 三大法人 - 期貨
CREATE TABLE IF NOT EXISTS institutional_futures (
    id                  SERIAL PRIMARY KEY,
    trade_date          DATE NOT NULL,
    contract_code       VARCHAR(20) NOT NULL,
    institution_type    VARCHAR(30) NOT NULL,
    long_volume         BIGINT,
    long_amount         BIGINT,
    short_volume        BIGINT,
    short_amount        BIGINT,
    net_volume          BIGINT,
    net_amount          BIGINT,
    long_oi             BIGINT,
    short_oi            BIGINT,
    net_oi              BIGINT,
    last_edit_time      TIMESTAMPTZ DEFAULT NOW(),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (trade_date, contract_code, institution_type)
);

-- 三大法人 - 選擇權 (call/put 分開，buy/sell 明確)
CREATE TABLE IF NOT EXISTS institutional_options (
    id                  SERIAL PRIMARY KEY,
    trade_date          DATE NOT NULL,
    contract_code       VARCHAR(20) NOT NULL,
    institution_type    VARCHAR(30) NOT NULL,
    call_buy_volume     BIGINT,
    call_buy_amount     BIGINT,
    call_sell_volume    BIGINT,
    call_sell_amount    BIGINT,
    call_net_volume     BIGINT,
    call_net_amount     BIGINT,
    call_buy_oi         BIGINT,
    call_sell_oi        BIGINT,
    call_net_oi         BIGINT,
    put_buy_volume      BIGINT,
    put_buy_amount      BIGINT,
    put_sell_volume     BIGINT,
    put_sell_amount     BIGINT,
    put_net_volume      BIGINT,
    put_net_amount      BIGINT,
    put_buy_oi          BIGINT,
    put_sell_oi         BIGINT,
    put_net_oi          BIGINT,
    last_edit_time      TIMESTAMPTZ DEFAULT NOW(),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (trade_date, contract_code, institution_type)
);

-- 散戶期貨 (全市場 - 三大法人)
CREATE TABLE IF NOT EXISTS retail_futures (
    id             SERIAL PRIMARY KEY,
    trade_date     DATE NOT NULL,
    contract_code  VARCHAR(20) NOT NULL,
    long_volume    BIGINT,
    short_volume   BIGINT,
    net_volume     BIGINT,
    long_oi        BIGINT,
    short_oi       BIGINT,
    net_oi         BIGINT,
    last_edit_time TIMESTAMPTZ DEFAULT NOW(),
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (trade_date, contract_code)
);

-- 散戶選擇權 (全市場 - 三大法人)
CREATE TABLE IF NOT EXISTS retail_options (
    id               SERIAL PRIMARY KEY,
    trade_date       DATE NOT NULL,
    call_buy_volume  BIGINT,
    call_sell_volume BIGINT,
    call_net_volume  BIGINT,
    call_buy_oi      BIGINT,
    call_sell_oi     BIGINT,
    call_net_oi      BIGINT,
    put_buy_volume   BIGINT,
    put_sell_volume  BIGINT,
    put_net_volume   BIGINT,
    put_buy_oi       BIGINT,
    put_sell_oi      BIGINT,
    put_net_oi       BIGINT,
    last_edit_time   TIMESTAMPTZ DEFAULT NOW(),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (trade_date)
);

-- 選擇權各履約價加權平均持倉成本
CREATE TABLE IF NOT EXISTS options_strike_avg_cost (
    id             SERIAL PRIMARY KEY,
    trade_date     DATE NOT NULL,
    contract_month VARCHAR(30) NOT NULL,
    strike_price   NUMERIC(10,2) NOT NULL,
    call_put       VARCHAR(1) NOT NULL,
    daily_price    NUMERIC(10,4),
    volume         BIGINT,
    open_interest  BIGINT,
    delta_oi       BIGINT,
    avg_cost       NUMERIC(10,4),
    last_edit_time TIMESTAMPTZ DEFAULT NOW(),
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (trade_date, contract_month, strike_price, call_put)
);

-- 各群體市場方向分析（折算小台）
CREATE TABLE IF NOT EXISTS market_direction (
    id                  SERIAL PRIMARY KEY,
    trade_date          DATE NOT NULL,
    group_type          VARCHAR(20) NOT NULL,
    tx_net_oi           BIGINT,
    mtx_net_oi          BIGINT,
    mxf_net_oi          BIGINT,
    futures_delta_mtx   NUMERIC(12,2),
    call_buy_oi         BIGINT,
    call_sell_oi        BIGINT,
    put_buy_oi          BIGINT,
    put_sell_oi         BIGINT,
    options_bull_oi     BIGINT,
    options_bear_oi     BIGINT,
    options_net_oi      BIGINT,
    options_delta_mtx   NUMERIC(12,2),
    total_delta_mtx     NUMERIC(12,2),
    last_edit_time      TIMESTAMPTZ DEFAULT NOW(),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (trade_date, group_type)
);

-- 全市場 ITM/OTM 未平倉分布
CREATE TABLE IF NOT EXISTS market_itm_otm (
    id               SERIAL PRIMARY KEY,
    trade_date       DATE NOT NULL,
    underlying_price NUMERIC(10,2),
    call_itm_oi      BIGINT,
    call_otm_oi      BIGINT,
    call_atm_oi      BIGINT,
    put_itm_oi       BIGINT,
    put_otm_oi       BIGINT,
    put_atm_oi       BIGINT,
    call_itm_volume  BIGINT,
    call_otm_volume  BIGINT,
    put_itm_volume   BIGINT,
    put_otm_volume   BIGINT,
    last_edit_time   TIMESTAMPTZ DEFAULT NOW(),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (trade_date)
);

-- 大額交易人未沖銷部位
CREATE TABLE IF NOT EXISTS large_trader_positions (
    id                  SERIAL PRIMARY KEY,
    trade_date          DATE NOT NULL,
    contract_code       VARCHAR(20) NOT NULL,
    trader_type         VARCHAR(80) NOT NULL,
    long_position       BIGINT,
    short_position      BIGINT,
    market_oi           BIGINT,
    last_edit_time      TIMESTAMPTZ DEFAULT NOW(),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (trade_date, contract_code, trader_type)
);

-- 爬蟲執行日誌
CREATE TABLE IF NOT EXISTS crawler_log (
    id          SERIAL PRIMARY KEY,
    agent_name  VARCHAR(100) NOT NULL,
    trade_date  DATE NOT NULL,
    status      VARCHAR(20) NOT NULL,
    records     INT DEFAULT 0,
    message     TEXT,
    executed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Max Pain 歷史
CREATE TABLE IF NOT EXISTS market_max_pain (
    id               SERIAL PRIMARY KEY,
    trade_date       DATE NOT NULL UNIQUE,
    max_pain_strike  NUMERIC(10, 2),
    underlying_price NUMERIC(10, 2),
    delta_pts        NUMERIC(10, 2),
    last_edit_time   TIMESTAMPTZ DEFAULT NOW(),
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- 週選 / 月選 OI 結構
CREATE TABLE IF NOT EXISTS market_oi_structure (
    id                   SERIAL PRIMARY KEY,
    trade_date           DATE NOT NULL UNIQUE,
    weekly_call_oi       BIGINT,
    weekly_put_oi        BIGINT,
    monthly_call_oi      BIGINT,
    monthly_put_oi       BIGINT,
    weekly_oi_ratio      NUMERIC(8, 4),
    weekly_dominant_exp  VARCHAR(30),
    last_edit_time       TIMESTAMPTZ DEFAULT NOW(),
    created_at           TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_tx_futures_date      ON tx_futures_daily (trade_date);
CREATE INDEX IF NOT EXISTS idx_txo_options_date     ON txo_options_daily (trade_date);
CREATE INDEX IF NOT EXISTS idx_pcr_date             ON put_call_ratio (trade_date);
CREATE INDEX IF NOT EXISTS idx_inst_futures_date    ON institutional_futures (trade_date);
CREATE INDEX IF NOT EXISTS idx_inst_options_date    ON institutional_options (trade_date);
CREATE INDEX IF NOT EXISTS idx_large_trader_date    ON large_trader_positions (trade_date);
CREATE INDEX IF NOT EXISTS idx_crawler_log_date     ON crawler_log (trade_date);
CREATE INDEX IF NOT EXISTS idx_retail_futures_date  ON retail_futures (trade_date);
CREATE INDEX IF NOT EXISTS idx_retail_options_date  ON retail_options (trade_date);
CREATE INDEX IF NOT EXISTS idx_strike_cost_date     ON options_strike_avg_cost (trade_date);
CREATE INDEX IF NOT EXISTS idx_market_dir_date      ON market_direction (trade_date);
CREATE INDEX IF NOT EXISTS idx_market_itm_date      ON market_itm_otm (trade_date);
CREATE INDEX IF NOT EXISTS idx_market_max_pain_date ON market_max_pain (trade_date);
CREATE INDEX IF NOT EXISTS idx_market_oi_str_date   ON market_oi_structure (trade_date);

-- ============================================================
-- 研究文章
-- ============================================================

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

-- ============================================================
-- 每日操作日誌
-- ============================================================

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
