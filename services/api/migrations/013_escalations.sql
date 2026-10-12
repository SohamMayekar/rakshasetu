-- 013 · escalations (PRD F-S2). Routed to a ROLE in the district, never a named person (PRD §15).
CREATE TABLE escalations (
  id           bigserial PRIMARY KEY,
  incident_id  bigint NOT NULL REFERENCES incidents(id),
  district_id  bigint REFERENCES districts(id),
  kind         text NOT NULL CHECK (kind IN ('team_overdue', 'capacity_gap')),
  team_id      bigint REFERENCES teams(id),
  case_ids     bigint[] NOT NULL DEFAULT '{}',
  level        integer NOT NULL DEFAULT 1,                    -- 1: EOC Duty Officer · 2: EOC In-charge
  role         text NOT NULL DEFAULT 'duty_officer',
  line         text NOT NULL,                                 -- the one sentence the officer reads
  status       text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'acked', 'resolved')),
  opened_at    timestamptz NOT NULL DEFAULT now(),
  acked_by     bigint REFERENCES users(id),
  acked_at     timestamptz,
  resolved_at  timestamptz,
  resolution   text
);
-- One live escalation per team (not one per case: no alarm floods), and one capacity gap per district.
CREATE UNIQUE INDEX escalations_one_per_team ON escalations (team_id) WHERE kind = 'team_overdue' AND status <> 'resolved';
CREATE UNIQUE INDEX escalations_one_gap_per_district ON escalations (district_id) WHERE kind = 'capacity_gap' AND status <> 'resolved';
