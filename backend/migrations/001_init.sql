-- Signal Digest — initial schema, verbatim from DATA_MODEL.md
-- Applied manually: psql -f 001_init.sql

CREATE TABLE tickers (
  ticker           TEXT PRIMARY KEY,       -- e.g. 'RELIANCE.NS'
  name             TEXT NOT NULL,
  sector           TEXT NOT NULL,          -- hand-curated, small set
  listed_since     DATE
);

CREATE TABLE price_ticks (
  id               BIGSERIAL PRIMARY KEY,
  ticker           TEXT REFERENCES tickers(ticker),
  price            NUMERIC(12,4) NOT NULL,
  volume           BIGINT,
  ts               TIMESTAMPTZ NOT NULL,
  source           TEXT NOT NULL,          -- real_historical / replay_simulated
  UNIQUE (ticker, ts, source)              -- DB-enforced dedup, not app-layer check-then-insert
);

CREATE INDEX idx_ticker_ts ON price_ticks (ticker, ts DESC);

CREATE TABLE baselines (
  ticker           TEXT REFERENCES tickers(ticker),
  as_of_date       DATE NOT NULL,
  mean_return_30d  NUMERIC(10,6),
  stdev_return_30d NUMERIC(10,6),
  avg_volume_30d   NUMERIC(16,2),
  stdev_5d         NUMERIC(10,6),
  stdev_30d        NUMERIC(10,6),
  sample_size      INT NOT NULL,           -- gates confidence: <20 days -> "not enough history"
  PRIMARY KEY (ticker, as_of_date)
);

CREATE TABLE flags (
  id               BIGSERIAL PRIMARY KEY,
  ticker           TEXT REFERENCES tickers(ticker),
  trading_day      DATE NOT NULL,
  signal_type      TEXT NOT NULL,          -- 'price_zscore' | 'volatility_regime'
  z_score          NUMERIC(6,3),
  severity         TEXT NOT NULL,          -- notable/significant/extreme (display label)
  severity_rank    SMALLINT NOT NULL,      -- notable=1, significant=2, extreme=3 — comparable
  volume_ratio     NUMERIC(6,2),
  sector_relative  TEXT,                   -- 'sector_wide' | 'stock_specific' | NULL
  computed_at      TIMESTAMPTZ NOT NULL,
  provider_state_at_computation TEXT,      -- audit trail
  UNIQUE (ticker, trading_day, signal_type)
);

CREATE TABLE watchlists (
  id UUID PRIMARY KEY, user_id UUID NOT NULL, name TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE watchlist_items (
  watchlist_id UUID REFERENCES watchlists(id),
  ticker TEXT REFERENCES tickers(ticker),
  added_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (watchlist_id, ticker)
);

CREATE TABLE watchlist_ack_state (
  watchlist_id   UUID REFERENCES watchlists(id) PRIMARY KEY,
  last_seen_hash TEXT NOT NULL,
  last_seen_at   TIMESTAMPTZ NOT NULL
);

CREATE TABLE flag_ack (
  flag_id      BIGINT REFERENCES flags(id),
  watchlist_id UUID REFERENCES watchlists(id),
  acked_at     TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (flag_id, watchlist_id)
);

CREATE TABLE provider_state (
  id INT PRIMARY KEY DEFAULT 1, mode TEXT NOT NULL DEFAULT 'normal', frozen_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
);
