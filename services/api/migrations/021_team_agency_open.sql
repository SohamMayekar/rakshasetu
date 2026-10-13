-- 021 · who a team is: any agency, not a fixed list of seven. The form offers a catalog (app/capabilities.py) and
-- "Other", and a deployment names its own teams. Existing rows are untouched.
ALTER TABLE teams DROP CONSTRAINT IF EXISTS teams_agency_check;
ALTER TABLE teams ADD CONSTRAINT teams_agency_not_empty CHECK (length(btrim(agency)) > 0);
