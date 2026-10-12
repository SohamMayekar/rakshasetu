-- 014 · rescue records (PRD F-S3): the team records what happened; the family is never asked for anything.
CREATE TABLE rescues (
  id             bigserial PRIMARY KEY,
  case_id        bigint NOT NULL REFERENCES cases(id),
  assignment_id  bigint NOT NULL REFERENCES assignments(id),
  team_id        bigint NOT NULL REFERENCES teams(id),
  recorded_by    bigint REFERENCES users(id),
  channel        text NOT NULL,                     -- app · VHF · HAM · satellite · phone (an officer's radio record)
  outcome        text NOT NULL CHECK (outcome IN ('rescued', 'partial', 'nobody_here', 'couldnt_reach', 'other')),
  people_taken   integer CHECK (people_taken >= 0),
  anyone_left    text CHECK (anyone_left IN ('yes', 'no', 'dont_know')),
  reason         text,                              -- couldn't reach: why · other: what the officer must know
  happened_at    timestamptz,                       -- the phone's own time: provenance only
  received_at    timestamptz NOT NULL DEFAULT now(),
  geom           geography(Point, 4326),            -- the TEAM phone's location at that moment (not the family's)
  away_from_pin  boolean NOT NULL DEFAULT false,
  corroborates   bigint REFERENCES rescues(id)      -- P1 #12: a radio record + the app's later sync = one + corroboration
);
CREATE UNIQUE INDEX rescues_one_per_assignment ON rescues (assignment_id) WHERE corroborates IS NULL;
ALTER TABLE cases ADD COLUMN rescued_at timestamptz;
