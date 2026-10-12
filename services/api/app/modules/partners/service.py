"""Partner annotations (PRD §11.4): something ABOUT an existing thing, from another team's system. What each kind
does is decided here, by our rules, never by the partner:

  credibility     a chip on THAT evidence item (e.g. "Forensics (Team X): likely recycled · 0.87"). It never
                  blocks or delays a dispatch and never lowers a priority.
  priority        a suggestion on the case: "Team Y suggests P1 · 0.78 · …". An officer accepts it (it becomes
                  their priority call, with the partner's reason) or ignores it. Both are audited.
  anchor_receipt  the partner anchored our audit head (seq + hash) in its own ledger; Verify checks that our chain
                  at that seq still has that hash, which closes "our own DB admin could re-hash everything".
  identity        not supported yet (PRD: LATER): refused with 422, never silently ignored.

Every annotation is stored, is an audit event, and (when it is about a case) a hashed evidence item on it.
"""

import json

from sqlalchemy import Connection, text

from app.config import Partner
from app.core.eventlog import Actor, append_event
from app.modules.evidence.service import JSON, add, record_bytes

KINDS = ("credibility", "priority", "identity", "anchor_receipt")


class Refused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _case(conn: Connection, partner: Partner, public_id: str):
    c = conn.execute(text("SELECT c.id, c.public_id, c.status, c.incident_id, c.district_id, i.code FROM cases c"
                          " JOIN incidents i ON i.id = c.incident_id WHERE c.public_id = :p"), {"p": public_id}).one_or_none()
    if c is None or (partner.incidents and c.code not in partner.incidents):
        raise Refused(404, f"No case {public_id} for this partner")
    return c


def receive(conn: Connection, partner: Partner, body: dict) -> tuple[dict, bool]:
    """(the result, replay?). Idempotent by (partner, idempotency_key): a replay returns the first result."""
    old = conn.execute(text("SELECT id, kind, case_id, evidence_id FROM partner_annotations WHERE partner = :p"
                            " AND idempotency_key = :k"), {"p": partner.id, "k": body["idempotency_key"]}).one_or_none()
    if old:
        return {"annotation_id": old.id, "kind": old.kind, "effect": _effect(old.kind)}, True
    kind, target = body["kind"], body["target"]
    if kind == "identity":
        raise Refused(422, "identity annotations aren't supported yet (PRD: LATER)")
    case = evidence = None
    if kind == "credibility":
        sha = str(target.get("evidence_sha256") or "")
        evidence = conn.execute(text("SELECT e.id, e.case_id, e.type FROM evidence e WHERE e.sha256 = :s AND e.case_id IS NOT NULL"
                                     " ORDER BY e.id LIMIT 1"), {"s": sha}).one_or_none()
        if evidence is None:
            raise Refused(404, "No evidence item with that sha256")
        case = conn.execute(text("SELECT public_id FROM cases WHERE id = :c"), {"c": evidence.case_id}).scalar()
        case = _case(conn, partner, case)
    elif kind == "priority":
        if body["value"] not in ("P1", "P2", "P3", "P4"):
            raise Refused(422, "A priority suggestion is P1, P2, P3 or P4")
        case = _case(conn, partner, str(target.get("case") or ""))
        if case.status in ("merged", "closed", "cancelled"):
            raise Refused(409, f"{case.public_id} is {case.status}")
    elif kind == "anchor_receipt":
        seq = target.get("seq")
        if not isinstance(seq, int) or not isinstance(target.get("head_hash"), str):
            raise Refused(422, "An anchor receipt names the seq and head_hash it anchored")
    aid = conn.execute(text(
        "INSERT INTO partner_annotations (partner, kind, target, case_id, evidence_id, value, confidence, explanation,"
        " payload, idempotency_key) VALUES (:p, :k, CAST(:t AS jsonb), :c, :e, :v, :conf, :x, CAST(:pl AS jsonb), :key)"
        " RETURNING id"),
        {"p": partner.id, "k": kind, "t": json.dumps(target), "c": case.id if case else None,
         "e": evidence.id if evidence else None, "v": body["value"], "conf": body.get("confidence"),
         "x": body.get("explanation"), "pl": json.dumps(body, ensure_ascii=False), "key": body["idempotency_key"]}).scalar_one()
    actor = Actor("partner", partner.id, "partner")
    data = {"annotation_id": aid, "partner": partner.id, "team": partner.team, "kind": kind, "value": body["value"],
            "confidence": body.get("confidence"), "explanation": body.get("explanation"), "target": target,
            "evidence_id": evidence.id if evidence else None}
    ev = dict(incident_id=case.incident_id, district_id=case.district_id, case_id=case.id) if case else {}
    append_event(conn, actor=actor, action=f"partner.{kind}", entity_type="partner_annotation", entity_id=aid,
                 data=data, **ev)
    if case:   # the annotation itself, as received, is evidence on the case
        add(conn, type="partner_annotation", content=record_bytes(body), mime=JSON, actor=actor, added_by=f"partner:{partner.id}",
            meta={"annotation_id": aid, "partner": partner.id, "team": partner.team, "kind": kind, "value": body["value"],
                  "confidence": body.get("confidence"), "explanation": body.get("explanation"),
                  "evidence_id": evidence.id if evidence else None}, **ev)
    return {"annotation_id": aid, "kind": kind, "effect": _effect(kind)}, False


def _effect(kind: str) -> str:
    return {"credibility": "a chip on that evidence item; it never blocks a dispatch or lowers a priority",
            "priority": "a suggestion an officer accepts or ignores",
            "anchor_receipt": "checked by Verify against our chain"}.get(kind, "")


def decide(conn: Connection, scope, annotation_id: int, accept: bool) -> dict:
    """An officer accepts a partner's priority suggestion (it becomes their own call, with the partner's reason)
    or ignores it. Either way it's on the record."""
    from app.modules.cases.service import NotAllowed, lock_case, override_priority
    a = conn.execute(text("SELECT a.*, c.public_id FROM partner_annotations a JOIN cases c ON c.id = a.case_id"
                          " WHERE a.id = :i AND a.kind = 'priority' FOR UPDATE OF a"), {"i": annotation_id}).one_or_none()
    if a is None or lock_case(conn, scope, a.public_id) is None:
        raise LookupError(annotation_id)
    if a.decision:
        raise NotAllowed(f"Already {a.decision}")
    from app.config import get_bundle
    team = next((p.team for p in get_bundle().partners if p.id == a.partner), a.partner)
    if accept:
        override_priority(conn, scope, a.public_id, a.value,
                          f"accepted {team}'s suggestion ({a.confidence or '?'}): {a.explanation or a.value}")
    conn.execute(text("UPDATE partner_annotations SET decision = :d, decided_by = :u, decided_at = now() WHERE id = :i"),
                 {"d": "accepted" if accept else "ignored", "u": scope.user_id, "i": annotation_id})
    c = conn.execute(text("SELECT id, incident_id, district_id FROM cases WHERE id = :c"), {"c": a.case_id}).one()
    append_event(conn, actor=Actor("user", str(scope.user_id), scope.role),
                 action="partner.suggestion_accepted" if accept else "partner.suggestion_ignored",
                 entity_type="partner_annotation", entity_id=a.id, incident_id=c.incident_id, district_id=c.district_id,
                 case_id=c.id, data={"annotation_id": a.id, "team": team, "value": a.value, "by": scope.name})
    return {"annotation_id": a.id, "decision": "accepted" if accept else "ignored"}


def for_case(conn: Connection, case_id: int) -> list[dict]:
    from app.config import get_bundle
    teams = {p.id: p.team for p in get_bundle().partners}
    rows = conn.execute(text("SELECT id, partner, kind, value, confidence, explanation, evidence_id, decision, received_at"
                             " FROM partner_annotations WHERE case_id = :c ORDER BY id"), {"c": case_id}).all()
    return [{**dict(r._mapping), "team": teams.get(r.partner, r.partner), "received_at": r.received_at.isoformat(),
             "confidence": float(r.confidence) if r.confidence is not None else None} for r in rows]


def anchors(conn: Connection) -> list[dict]:
    """Each anchor receipt, checked: does our chain at that seq still have the hash the partner anchored?"""
    from app.config import get_bundle
    teams = {p.id: p.team for p in get_bundle().partners}
    out = []
    for a in conn.execute(text("SELECT id, partner, target, value, received_at FROM partner_annotations"
                               " WHERE kind = 'anchor_receipt' ORDER BY id")).all():
        seq, anchored = a.target.get("seq"), a.target.get("head_hash")
        ours = conn.execute(text("SELECT hash FROM events WHERE seq = :s"), {"s": seq}).scalar()
        out.append({"annotation_id": a.id, "team": teams.get(a.partner, a.partner), "seq": seq, "receipt": a.value,
                    "at": a.received_at.isoformat(), "matches": ours == anchored})
    return out
