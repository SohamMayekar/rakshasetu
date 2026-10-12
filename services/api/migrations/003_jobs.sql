-- 003 · the job queue (PRD §10, rule R20). Claimed with SELECT … FOR UPDATE SKIP LOCKED; a job locked for
-- more than 60 s is reclaimed (its worker died). Lanes: live_voice > whatsapp_partner > import > surge > backfill.
CREATE TABLE jobs (
  id           bigserial PRIMARY KEY,
  kind         text NOT NULL,                       -- e.g. report.process, import.rows, llm.backfill
  lane         text NOT NULL,
  lane_rank    integer NOT NULL,                    -- 0 = most urgent
  payload      jsonb NOT NULL DEFAULT '{}',
  dedupe_key   text UNIQUE,                         -- enqueue is idempotent: the same key never makes two jobs
  run_at       timestamptz NOT NULL DEFAULT now(),
  attempts     integer NOT NULL DEFAULT 0,
  max_attempts integer NOT NULL DEFAULT 5,
  locked_by    text,
  locked_at    timestamptz,
  done_at      timestamptz,
  dead_at      timestamptz,                         -- gave up after max_attempts (shown by the integrity check)
  error        text,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX jobs_claimable_idx ON jobs (lane_rank, run_at, id) WHERE done_at IS NULL AND dead_at IS NULL;
