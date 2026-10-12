-- 005 · evidence (PRD §10, F-C11). Files are content-addressed (files/ab/<sha256>); the sha256 also goes into
-- the evidence's audit event, so a file swapped on disk fails a re-hash. Originals are immutable.
CREATE TABLE evidence (
  id          bigserial PRIMARY KEY,
  case_id     bigint REFERENCES cases(id),
  report_id   bigint REFERENCES reports(id),
  type        text NOT NULL,              -- open list: audio, transcript, message, sheet_row, merge, rescue, radio, partner_annotation
  uri         text,                       -- files/ab/<sha256> for files; null for records that live in rows
  sha256      text,
  mime        text,
  bytes       bigint,
  captured_at timestamptz NOT NULL DEFAULT now(),
  added_by    text,
  meta        jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX evidence_case_idx ON evidence (case_id);
CREATE INDEX evidence_report_idx ON evidence (report_id);
