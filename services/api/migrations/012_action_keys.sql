-- 012 · idempotency for responder and officer actions (PRD §11: every mutating responder endpoint takes
-- Idempotency-Key). A retried tap returns the first answer instead of acting twice.
CREATE TABLE action_keys (
  scope      text NOT NULL,                 -- who sent it: "user:12"
  key        text NOT NULL,
  response   jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (scope, key)
);
