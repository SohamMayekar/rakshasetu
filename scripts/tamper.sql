-- Q&A tamper demo (PRD F-C8). Run as the database SUPERUSER: `make tamper` (the app role can't do this).
-- It rewrites the reason on one past event, the kind of quiet edit an insider might try.
-- Then press Verify on the Audit screen (or `make verify`): "broken at #<that seq>".
-- `make demo-reset` (or `make seed`) starts a fresh chain afterwards.
\set target_seq `echo ${SEQ:-5}`
UPDATE events SET reason = 'edited quietly by a superuser' WHERE seq = :target_seq;
SELECT seq, action, reason FROM events WHERE seq = :target_seq;
