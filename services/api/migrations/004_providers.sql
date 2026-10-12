-- 004 · provider bookkeeping (PRD §8.4, §10).
-- provider_usage: stop at 80% of a free cap. One row per provider per window (minute or day).
CREATE TABLE provider_usage (
  provider      text NOT NULL,
  window_kind   text NOT NULL CHECK (window_kind IN ('minute', 'day')),
  window_start  timestamptz NOT NULL,
  calls         integer NOT NULL DEFAULT 0,
  tokens        integer NOT NULL DEFAULT 0,
  audio_seconds numeric NOT NULL DEFAULT 0,
  PRIMARY KEY (provider, window_kind, window_start)
);
-- extraction_cache: the same text gives the same result with no new call (cleared on a demo reset).
CREATE TABLE extraction_cache (
  text_sha256 text NOT NULL,
  provider    text NOT NULL,
  model       text NOT NULL,
  result      jsonb NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (text_sha256, provider, model)
);
-- runtime_flags: switches the demo controls flip at runtime and every process reads (e.g. language model off).
CREATE TABLE runtime_flags (
  key        text PRIMARY KEY,
  value      jsonb NOT NULL,
  updated_by text,
  updated_at timestamptz NOT NULL DEFAULT now()
);
