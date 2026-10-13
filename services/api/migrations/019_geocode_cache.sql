-- 019_geocode_cache: what the free geocoders answered for an address text, so the same address is never sent
-- twice. Text is kept only as its sha256 (the address itself lives on the report/case); a demo reset wipes it
-- with the rest of the database.
CREATE TABLE geocode_cache (
  id          bigserial PRIMARY KEY,
  text_sha256 text NOT NULL,
  provider    text NOT NULL,
  result      jsonb NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX geocode_cache_text_idx ON geocode_cache (text_sha256);
