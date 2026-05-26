-- IDXDaily PostgreSQL schema
-- Apply with: python -m backend.db.apply_schema  (from project root)

-- ── Core tables ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tickers (
    id                 TEXT PRIMARY KEY,
    symbol             TEXT UNIQUE NOT NULL,
    name               TEXT NOT NULL,
    sector             TEXT,
    subsector          TEXT,
    description        TEXT,
    market_cap         FLOAT,
    aliases            TEXT[],          -- computed match strings for news detection
    ticker_tag_enabled BOOLEAN NOT NULL DEFAULT FALSE,  -- scrape per-ticker pages
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS tickers_symbol_idx ON tickers (symbol);

CREATE TABLE IF NOT EXISTS articles (
    id               TEXT PRIMARY KEY,
    ticker_id        TEXT NOT NULL REFERENCES tickers(id) ON DELETE CASCADE,
    title            TEXT NOT NULL,
    original_summary TEXT NOT NULL DEFAULT '',
    ai_summary       TEXT,
    url              TEXT,
    source           TEXT NOT NULL,
    published_at     TIMESTAMPTZ,          -- NULL = date could not be verified; excluded from recent views
    sentiment        TEXT NOT NULL DEFAULT 'NEUTRAL',
    impact_score     FLOAT NOT NULL DEFAULT 5.0,
    category         TEXT NOT NULL DEFAULT 'GENERAL',
    is_early_signal  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS articles_ticker_pub_idx ON articles (ticker_id, published_at);
CREATE INDEX IF NOT EXISTS articles_sentiment_idx  ON articles (sentiment);
CREATE INDEX IF NOT EXISTS articles_impact_idx     ON articles (impact_score);

-- Junction table: one article can mention multiple tickers
CREATE TABLE IF NOT EXISTS ticker_mentions (
    article_id       TEXT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    ticker_id        TEXT NOT NULL REFERENCES tickers(id)  ON DELETE CASCADE,
    match_confidence VARCHAR(10) NOT NULL DEFAULT 'medium',  -- 'high' | 'medium' | 'low'
    match_type       VARCHAR(20) NOT NULL DEFAULT 'ticker_match', -- 'ticker_match' | 'macro_impact'
    ai_summary       TEXT,                                   -- per-ticker framed summary
    sentiment        VARCHAR(10),                            -- per-ticker sentiment
    impact_score     REAL,                                   -- per-ticker impact
    PRIMARY KEY (article_id, ticker_id)
);

CREATE INDEX IF NOT EXISTS ticker_mentions_ticker_idx ON ticker_mentions (ticker_id);

-- ── Aggregates ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ticker_sentiment_daily (
    ticker_id    TEXT NOT NULL REFERENCES tickers(id) ON DELETE CASCADE,
    date         DATE NOT NULL,
    bullish_cnt  INTEGER NOT NULL DEFAULT 0,
    bearish_cnt  INTEGER NOT NULL DEFAULT 0,
    neutral_cnt  INTEGER NOT NULL DEFAULT 0,
    avg_impact   FLOAT NOT NULL DEFAULT 5.0,
    PRIMARY KEY (ticker_id, date)
);

CREATE TABLE IF NOT EXISTS market_signals (
    id          TEXT PRIMARY KEY,
    ticker_id   TEXT REFERENCES tickers(id) ON DELETE SET NULL,
    signal_type TEXT NOT NULL,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    confidence  FLOAT NOT NULL,
    sentiment   TEXT NOT NULL,
    source_url  TEXT,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Market history (for percentile-rank Fear & Greed formula) ──────────────

CREATE TABLE IF NOT EXISTS ihsg_daily (
    date       DATE PRIMARY KEY,
    close      REAL NOT NULL,
    volume     REAL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS usdidr_daily (
    date       DATE PRIMARY KEY,
    close      REAL NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Fear & Greed Index ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fear_greed_index (
    date              DATE PRIMARY KEY,
    score             FLOAT,             -- NULL if <2 active components
    label             TEXT NOT NULL,
    bullish_pct       FLOAT NOT NULL DEFAULT 0,
    bearish_pct       FLOAT NOT NULL DEFAULT 0,
    neutral_pct       FLOAT NOT NULL DEFAULT 0,
    total_articles    INTEGER NOT NULL DEFAULT 0,
    window_days       INTEGER NOT NULL DEFAULT 7,
    active_components INTEGER NOT NULL DEFAULT 0,
    components_json   JSONB,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Batch enrichment tracking ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS enrichment_batches (
    batch_id         TEXT PRIMARY KEY,          -- Gemini batch job name
    submitted_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    checked_at       TIMESTAMPTZ,
    completed_at     TIMESTAMPTZ,
    status           TEXT NOT NULL DEFAULT 'JOB_STATE_PENDING',
    article_ids_json JSONB NOT NULL,            -- ordered list of article IDs
    model            TEXT NOT NULL DEFAULT 'gemini-2.5-flash-lite',
    article_count    INTEGER NOT NULL DEFAULT 0
);

-- Safe migrations for existing deployments:
ALTER TABLE tickers ADD COLUMN IF NOT EXISTS aliases            TEXT[];
ALTER TABLE tickers ADD COLUMN IF NOT EXISTS ticker_tag_enabled BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE fear_greed_index ADD COLUMN IF NOT EXISTS score             FLOAT;
ALTER TABLE fear_greed_index ADD COLUMN IF NOT EXISTS active_components INTEGER NOT NULL DEFAULT 0;
ALTER TABLE fear_greed_index ADD COLUMN IF NOT EXISTS components_json   JSONB;
ALTER TABLE ticker_mentions  ADD COLUMN IF NOT EXISTS match_confidence  VARCHAR(10) NOT NULL DEFAULT 'medium';
ALTER TABLE ticker_mentions  ADD COLUMN IF NOT EXISTS ai_summary        TEXT;
ALTER TABLE ticker_mentions  ADD COLUMN IF NOT EXISTS sentiment         VARCHAR(10);
ALTER TABLE ticker_mentions  ADD COLUMN IF NOT EXISTS impact_score      REAL;
ALTER TABLE ticker_mentions  ADD COLUMN IF NOT EXISTS match_type        VARCHAR(20) NOT NULL DEFAULT 'ticker_match';
ALTER TABLE articles        ALTER COLUMN published_at DROP NOT NULL;
ALTER TABLE articles        ALTER COLUMN ticker_id   DROP NOT NULL;
ALTER TABLE articles        ADD COLUMN IF NOT EXISTS body             TEXT;
ALTER TABLE articles        ADD COLUMN IF NOT EXISTS body_fetched_at  TIMESTAMPTZ;

-- ── Foreign investor net flow (A1) ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS foreign_flow_daily (
    date             DATE PRIMARY KEY,
    net_idr_billions REAL,    -- positive = net buy, negative = net sell
    buy_idr_billions REAL,
    sell_idr_billions REAL,
    source           TEXT,
    fetched_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Per-stock daily closes for market breadth (A2) ─────────────────────────

CREATE TABLE IF NOT EXISTS stock_daily (
    ticker     TEXT NOT NULL,
    date       DATE NOT NULL,
    close      REAL NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (ticker, date)
);

CREATE INDEX IF NOT EXISTS stock_daily_date_idx ON stock_daily (date DESC);

-- ── Smoothing columns on fear_greed_index (A3) ─────────────────────────────

ALTER TABLE fear_greed_index ADD COLUMN IF NOT EXISTS raw_score      REAL;
ALTER TABLE fear_greed_index ADD COLUMN IF NOT EXISTS smoothed_score REAL;
