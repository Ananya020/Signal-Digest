-- Step A: Signal Evolution ("since you last checked", made literal)
-- Applied manually: psql -f 002_since_last_checked.sql

ALTER TABLE flag_ack
  ADD COLUMN severity_rank_at_ack SMALLINT,
  ADD COLUMN z_score_at_ack NUMERIC(6,3);

-- Audit table only — never read by ack-bust logic, never affects it.
CREATE TABLE flag_ack_history (
  id                    BIGSERIAL PRIMARY KEY,
  flag_id               BIGINT REFERENCES flags(id),
  watchlist_id          UUID REFERENCES watchlists(id),
  severity_rank_at_ack  SMALLINT,
  z_score_at_ack        NUMERIC(6,3),
  acked_at              TIMESTAMPTZ NOT NULL,
  superseded_at         TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_flag_ack_history_flag_id ON flag_ack_history (flag_id, superseded_at DESC);
