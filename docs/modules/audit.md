# audit · the hash-chained event log

- **What it does:** every state change calls `append_event()` (`services/api/app/core/eventlog.py`) as its last statement before commit. The row it writes is the audit trail *and* the real-time stream.
- **Key table:** `events` (seq, at, actor, action, entity, incident/district/case/team, `body` TEXT, prev_hash, hash).
- **The tricky rule:** the body is canonical JSON generated **once** and stored as text; `hash = sha256(prev_hash ‖ body)` over that stored text. A global advisory lock makes sequence order = commit order. The app's DB role can only INSERT and SELECT here.
- **Verify:** `verify_chain()` recomputes every hash, checks each `prev_hash` links, and checks the columns still match the hashed body; it returns the first broken `seq`.
- **How to show it:** seed, then `SELECT seq, action, left(hash,12) FROM events ORDER BY seq DESC LIMIT 5;` — and, from m10, edit a row in `make psql` and watch Verify report "broken at #N".
