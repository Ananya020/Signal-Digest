-- Phase 4 correction: last_successful_fetch was not persisted, so a process
-- restart during a genuine 'stale' fault reset the freshness age clock to
-- "now" and incorrectly reported LIVE. See PROGRESS.md / RELIABILITY.md.
ALTER TABLE provider_state ADD COLUMN IF NOT EXISTS last_successful_fetch TIMESTAMPTZ;
