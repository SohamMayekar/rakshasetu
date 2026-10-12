-- 010 · one row per spreadsheet row: what happened to it and why (PRD F-D3 "the judge can pick any row").
-- Written in the SAME transaction as the row's case, so the import summary is always the database's count.
CREATE TABLE import_rows (
  import_id   bigint NOT NULL REFERENCES imports(id),
  row_number  integer NOT NULL,                      -- as the volunteer sees it in Excel (header = 1)
  report_id   bigint REFERENCES reports(id),
  case_id     bigint REFERENCES cases(id),           -- the case the row ended in (after any merge)
  outcome     text NOT NULL CHECK (outcome IN ('new', 'merged', 'to_check', 'history', 'already', 'dropped', 'pending')),
  read_by     text CHECK (read_by IN ('rules', 'ai')),
  reason      text NOT NULL,
  flags       text[] NOT NULL DEFAULT '{}',
  at          timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (import_id, row_number)
);
ALTER TABLE imports ADD COLUMN history integer NOT NULL DEFAULT 0,
                    ADD COLUMN already integer NOT NULL DEFAULT 0,
                    ADD COLUMN pending integer NOT NULL DEFAULT 0,
                    ADD COLUMN summary text;
