-- 017 · partner annotations (PRD §11.4) and the partner log (P1 #13).
-- An annotation is ABOUT an existing thing; what it does is decided by our rules (app/modules/partners).
CREATE TABLE partner_annotations (
  id              bigserial PRIMARY KEY,
  partner         text NOT NULL,
  kind            text NOT NULL CHECK (kind IN ('credibility', 'priority', 'identity', 'anchor_receipt')),
  target          jsonb NOT NULL,
  case_id         bigint REFERENCES cases(id),
  evidence_id     bigint REFERENCES evidence(id),
  value           text NOT NULL,
  confidence      numeric(4, 3),
  explanation     text,
  payload         jsonb NOT NULL,
  idempotency_key text NOT NULL,
  received_at     timestamptz NOT NULL DEFAULT now(),
  decision        text CHECK (decision IN ('accepted', 'ignored')),   -- priority suggestions: an officer's call
  decided_by      bigint REFERENCES users(id),
  decided_at      timestamptz,
  UNIQUE (partner, idempotency_key)
);
CREATE INDEX partner_annotations_case_idx ON partner_annotations (case_id);

-- Every partner call, in or out, signed or not: what the partner log drawer shows. A log, not evidence.
CREATE TABLE partner_calls (
  id           bigserial PRIMARY KEY,
  at           timestamptz NOT NULL DEFAULT now(),
  partner      text,                     -- as the request claimed it (not trusted when the signature fails)
  direction    text NOT NULL CHECK (direction IN ('in', 'out')),
  method       text NOT NULL,
  endpoint     text NOT NULL,
  status       int NOT NULL,
  signature_ok boolean,
  latency_ms   int,
  body_sha256  text,
  note         text
);
CREATE INDEX partner_calls_at_idx ON partner_calls (at DESC);
