-- 018 · outbound partner webhooks (PRD §11.4): where each subscribed partner's stream has got to in the
-- event log. Deliveries themselves are ordinary jobs (kind webhook.deliver); every attempt is a partner_calls row.
CREATE TABLE webhook_cursors (
  partner      text PRIMARY KEY,
  last_seq     bigint NOT NULL,              -- the last events.seq turned into deliveries
  last_head_at timestamptz                   -- when the last audit.head went out
);
