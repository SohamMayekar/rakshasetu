-- 007 · triage ordering (PRD F-C3, F-C2). p1_rank orders cases inside P1:
-- 1 infant or urgent medical → 2 water rising → 3 other vulnerable → 4 everything else (then waiting time).
ALTER TABLE cases ADD COLUMN p1_rank smallint;
CREATE INDEX cases_queue_idx ON cases (incident_id, priority, p1_rank, queue_since);
