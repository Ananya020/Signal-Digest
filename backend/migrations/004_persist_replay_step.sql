-- Second instance of the same bug class as 002_add_last_successful_fetch.sql:
-- HistoricalReplayProvider's replay position (ReplayClock) was process-memory
-- only. On a real restart (Render spin-down/wake, redeploy, crash) it reset
-- to the beginning of history, silently re-walking from day one while
-- previously-computed flags remained correctly stored. See PROGRESS.md /
-- RELIABILITY.md.
ALTER TABLE provider_state ADD COLUMN IF NOT EXISTS replay_step INTEGER;
