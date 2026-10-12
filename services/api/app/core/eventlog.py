"""The one write path for history (rule R1, PRD F-C8 and F-C10).

Every state change calls `append_event()` as the LAST statement before its transaction commits.
The `events` row it writes is both the audit trail and the real-time stream: nothing reaches a screen
unless it is in this chain.

How a row is made:
  1. pg_advisory_xact_lock(1): one appender at a time, so sequence order = commit order and no reader
     can ever skip an event (the lock is held until commit, so keep transactions short).
  2. Read the chain head (seq, hash). seq = head + 1; prev_hash = head hash (64 zeros for the first).
  3. Build the canonical JSON body ONCE (sorted keys, no spaces, UTF-8) and store it as TEXT.
  4. hash = sha256(prev_hash || body) over exactly that stored text.
  5. pg_notify('ev', seq): Postgres delivers it only when the transaction commits.

"Tamper-evident, not tamper-proof": the app's DB role can only INSERT and SELECT here (rule R9). A database
superuser could rewrite and re-hash everything, which is why the head is exported for partner anchoring.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Connection, text

GENESIS_PREV = "0" * 64


@dataclass(frozen=True)
class Actor:
    type: str                 # user | system | partner | reporter
    id: str | None = None     # user id, partner id, device hash prefix, or "system"/"ticker"/"worker"
    role: str | None = None   # the role at the time of acting

    def as_dict(self) -> dict:
        return {"type": self.type, "id": self.id, "role": self.role}


SYSTEM = Actor("system", "system")
WORKER = Actor("system", "worker")
TICKER = Actor("system", "ticker")


def canonical(obj) -> str:
    """The one serialisation used for hashing: sorted keys, compact, UTF-8 kept as-is."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def chain_hash(prev_hash: str, body: str) -> str:
    return hashlib.sha256((prev_hash + body).encode("utf-8")).hexdigest()


def append_event(conn: Connection, *, actor: Actor, action: str, entity_type: str, entity_id=None,
                 incident_id: int | None = None, district_id: int | None = None, case_id: int | None = None,
                 team_id: int | None = None, data: dict | None = None, reason: str | None = None) -> int:
    conn.execute(text("SELECT pg_advisory_xact_lock(1)"))
    head = conn.execute(text(
        "SELECT clock_timestamp() AS at,"
        " (SELECT seq FROM events ORDER BY seq DESC LIMIT 1) AS seq,"
        " (SELECT hash FROM events ORDER BY seq DESC LIMIT 1) AS hash")).one()
    seq = (head.seq or 0) + 1
    prev = head.hash or GENESIS_PREV
    at: datetime = head.at
    body = canonical({
        "seq": seq, "at": at.isoformat(), "actor": actor.as_dict(), "action": action,
        "entity": {"type": entity_type, "id": None if entity_id is None else str(entity_id)},
        "incident_id": incident_id, "district_id": district_id, "case_id": case_id, "team_id": team_id,
        "data": data or {}, "reason": reason,
    })
    conn.execute(text(
        "INSERT INTO events (seq, at, actor_type, actor_id, actor_role, action, entity_type, entity_id,"
        " incident_id, district_id, case_id, team_id, body, reason, prev_hash, hash)"
        " VALUES (:seq, :at, :atype, :aid, :arole, :action, :etype, :eid, :inc, :dist, :case, :team,"
        "         :body, :reason, :prev, :hash)"),
        dict(seq=seq, at=at, atype=actor.type, aid=actor.id, arole=actor.role, action=action, etype=entity_type,
             eid=None if entity_id is None else str(entity_id), inc=incident_id, dist=district_id, case=case_id,
             team=team_id, body=body, reason=reason, prev=prev, hash=chain_hash(prev, body)))
    conn.execute(text("SELECT pg_notify('ev', :seq)"), {"seq": str(seq)})
    return seq


def _columns_match_body(row, b: dict) -> bool:
    """A body is only trustworthy if the denormalised columns say the same thing (an edit to `action`
    or `case_id` without touching the body must also break the chain)."""
    return (b.get("seq") == row.seq and b.get("action") == row.action
            and b["actor"].get("type") == row.actor_type and b["actor"].get("id") == row.actor_id
            and b["actor"].get("role") == row.actor_role
            and b["entity"].get("type") == row.entity_type and b["entity"].get("id") == row.entity_id
            and b.get("incident_id") == row.incident_id and b.get("district_id") == row.district_id
            and b.get("case_id") == row.case_id and b.get("team_id") == row.team_id
            and b.get("reason") == row.reason and datetime.fromisoformat(b["at"]) == row.at)


def verify_chain(conn: Connection, batch: int = 2000) -> dict:
    """Recompute the whole chain. Returns {ok, count, head_seq, head_hash, broken_at, problem}."""
    expected_prev, count, last = GENESIS_PREV, 0, None
    after = -1
    while True:
        rows = conn.execute(text(
            "SELECT seq, at, actor_type, actor_id, actor_role, action, entity_type, entity_id, incident_id,"
            " district_id, case_id, team_id, body, reason, prev_hash, hash FROM events"
            " WHERE seq > :after ORDER BY seq LIMIT :n"), {"after": after, "n": batch}).all()
        if not rows:
            break
        for r in rows:
            problem = None
            if r.prev_hash != expected_prev:
                problem = "prev_hash doesn't link to the previous event (a row was removed or inserted)"
            elif chain_hash(r.prev_hash, r.body) != r.hash:
                problem = "hash doesn't match the body (the body was edited)"
            else:
                try:
                    if not _columns_match_body(r, json.loads(r.body)):
                        problem = "a column no longer matches the hashed body (the row was edited)"
                except (ValueError, KeyError, TypeError):
                    problem = "the body is not valid canonical JSON"
            if problem:
                return {"ok": False, "count": count, "broken_at": r.seq, "problem": problem,
                        "head_seq": last.seq if last else None, "head_hash": last.hash if last else None}
            expected_prev, count, last = r.hash, count + 1, r
            after = r.seq
    return {"ok": True, "count": count, "broken_at": None, "problem": None,
            "head_seq": last.seq if last else None, "head_hash": last.hash if last else None}
