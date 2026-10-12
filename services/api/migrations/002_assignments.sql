-- 002 · assignments ("lease" in code; "assigned to … · check-in due" on screen). PRD §10, rules R6/R7.
-- Created now because a team lead's Scope is defined by its live assignments (rule R8).
CREATE TABLE assignments (
  id                 bigserial PRIMARY KEY,
  case_id            bigint NOT NULL REFERENCES cases(id),
  team_id            bigint NOT NULL REFERENCES teams(id),
  assigned_by        bigint REFERENCES users(id),
  suggested_rank     integer,                                   -- 1..3 if picked from the suggestions
  phase              text NOT NULL DEFAULT 'offered' CHECK (phase IN ('offered', 'acknowledged', 'reached')),
  eta_minutes        integer,                                   -- the team's own estimate
  long_operation     boolean NOT NULL DEFAULT false,            -- collapse / large site: longer on-scene window
  next_contact_due   timestamptz NOT NULL,                      -- database clock only (rule R6)
  state              text NOT NULL DEFAULT 'open'
                     CHECK (state IN ('open', 'overdue', 'released', 'completed', 'reassigned')),
  standdown_acked_at timestamptz,                               -- after a reassign: "stand-down not acknowledged" until set
  demo_clock         boolean NOT NULL DEFAULT false,            -- ×60 demo timers (live demo cases only)
  created_at         timestamptz NOT NULL DEFAULT now(),
  ended_at           timestamptz,
  end_reason         text
);
-- Rule R7: exactly one live assignment per case, enforced by the database.
CREATE UNIQUE INDEX assignments_one_live_per_case ON assignments (case_id) WHERE state IN ('open', 'overdue');
CREATE INDEX assignments_due_idx ON assignments (next_contact_due) WHERE state = 'open';
CREATE INDEX assignments_team_idx ON assignments (team_id) WHERE state IN ('open', 'overdue');
