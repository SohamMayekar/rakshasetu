"""Merge decisions by people (PRD §11.1, F-D2). Desk only (local listener), `merge.decide`, inside the Scope."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.auth import Scope, require
from app.core.eventlog import Actor, append_event
from app.core.listener import require_local
from app.db import get_engine
from app.modules.cases.service import Conflict, NotAllowed
from app.modules.dedupe.merge import merge_cases, undo_merge

router = APIRouter(tags=["merges"], dependencies=[Depends(require_local)])


class Decision(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


class ManualMerge(BaseModel):
    cases: list[str] = Field(min_length=2, max_length=2)      # public ids or ids; the older one is kept
    reason: str = Field(min_length=3, max_length=300)


class Undo(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


def _actor(scope: Scope) -> Actor:
    return Actor("user", str(scope.user_id), scope.role)


def _visible(conn, scope: Scope, refs: list) -> list:
    where, params = scope.case_where("c")
    out = []
    for ref in refs:
        ref = str(ref)
        key = "c.id = :ref_id" if ref.isdigit() else "c.public_id = :ref"
        r = conn.execute(text(f"SELECT c.id, c.public_id, c.queue_since FROM cases c WHERE {key} AND {where}"),
                         {**params, "ref": ref, "ref_id": int(ref) if ref.isdigit() else None}).one_or_none()
        if r is None:
            raise HTTPException(404, f"No such case: {ref}")
        out.append(r)
    return out


def _run(fn):
    try:
        with get_engine().begin() as conn:
            return fn(conn)
    except LookupError:
        raise HTTPException(404, "Not found") from None
    except (Conflict, NotAllowed) as e:
        raise HTTPException(409, e.message) from None


@router.get("/v1/merge-suggestions")
def list_suggestions(incident: str | None = None, case: int | None = None,
                     scope: Scope = Depends(require("merge.decide"))) -> list[dict]:
    """Open suggestions in the caller's scope; ?case= keeps those with that case on either side (the drawer)."""
    where, params = scope.case_where("c")
    with get_engine().connect() as conn:
        rows = conn.execute(text(
            "SELECT s.id, s.case_id, c.public_id, s.candidate_case_id, k.public_id AS candidate, s.score, s.strength,"
            " s.reasons, s.conflicts, s.signals, s.created_at FROM merge_suggestions s"
            " JOIN cases c ON c.id = s.case_id JOIN cases k ON k.id = s.candidate_case_id JOIN incidents i ON i.id = c.incident_id"
            f" WHERE s.status = 'open' AND {where} AND (CAST(:inc AS text) IS NULL OR i.code = :inc)"
            " AND (CAST(:case AS bigint) IS NULL OR s.case_id = :case OR s.candidate_case_id = :case) ORDER BY s.id"),
            {**params, "inc": incident, "case": case}).all()
    return [{**dict(r._mapping), "score": float(r.score), "created_at": r.created_at.isoformat()} for r in rows]


def _suggestion(conn, scope: Scope, sid: int):
    s = conn.execute(text("SELECT * FROM merge_suggestions WHERE id = :id FOR UPDATE"), {"id": sid}).one_or_none()
    if s is None:
        raise LookupError(sid)
    _visible(conn, scope, [s.case_id, s.candidate_case_id])
    if s.status != "open":
        raise Conflict(f"This suggestion was already {s.status}")
    return s


@router.post("/v1/merge-suggestions/{sid}/accept")
def accept(sid: int, body: Decision, scope: Scope = Depends(require("merge.decide"))) -> dict:
    def go(conn):
        s = _suggestion(conn, scope, sid)
        if s.strength == "refused" and not body.reason:
            raise NotAllowed("These were refused (the names differ). Say why you're merging them anyway.")
        mid = merge_cases(conn, target_id=s.candidate_case_id, source_id=s.case_id, actor=_actor(scope),
                          decided_by=str(scope.user_id), score=float(s.score), signals=s.signals, reasons=list(s.reasons),
                          line="Merged by a person: " + " · ".join(s.reasons), reason=body.reason, suggestion_id=sid)
        return {"merge_id": mid, "kept": s.candidate_case_id}
    return _run(go)


@router.post("/v1/merge-suggestions/{sid}/reject")
def reject(sid: int, body: Decision, scope: Scope = Depends(require("merge.decide"))) -> dict:
    def go(conn):
        s = _suggestion(conn, scope, sid)
        conn.execute(text("UPDATE merge_suggestions SET status = 'rejected', decided_by = :u, decided_at = now() WHERE id = :id"),
                     {"u": scope.user_id, "id": sid})
        lo, hi = sorted((s.case_id, s.candidate_case_id))
        conn.execute(text("INSERT INTO merge_blocks (case_a, case_b, created_by, reason) VALUES (:a, :b, :u, :r)"
                          " ON CONFLICT DO NOTHING"), {"a": lo, "b": hi, "u": scope.user_id, "r": body.reason or "not the same household"})
        conn.execute(text("UPDATE cases SET flags = array_remove(flags, 'possible_duplicate') WHERE id = :c AND NOT EXISTS"
                          " (SELECT 1 FROM merge_suggestions WHERE case_id = :c AND status = 'open' AND strength <> 'refused')"),
                     {"c": s.case_id})
        c = conn.execute(text("SELECT incident_id, district_id FROM cases WHERE id = :c"), {"c": s.case_id}).one()
        append_event(conn, actor=_actor(scope), action="merge.rejected", entity_type="merge_suggestion", entity_id=sid,
                     incident_id=c.incident_id, district_id=c.district_id, case_id=s.case_id, reason=body.reason,
                     data={"suggestion_id": sid, "candidate_case_id": s.candidate_case_id, "blocked": True})
        return {"rejected": sid, "blocked": [lo, hi]}
    return _run(go)


@router.post("/v1/merges")
def manual_merge(body: ManualMerge, scope: Scope = Depends(require("merge.decide"))) -> dict:
    def go(conn):
        a, b = sorted(_visible(conn, scope, body.cases), key=lambda r: (r.queue_since, r.id))
        mid = merge_cases(conn, target_id=a.id, source_id=b.id, actor=_actor(scope), decided_by=str(scope.user_id),
                          line=f"Merged by a person: {body.reason}", reason=body.reason)
        return {"merge_id": mid, "kept": a.public_id, "absorbed": b.public_id}
    return _run(go)


@router.post("/v1/merges/{merge_id}/undo")
def undo(merge_id: int, body: Undo, scope: Scope = Depends(require("merge.decide"))) -> dict:
    def go(conn):
        m = conn.execute(text("SELECT target_case_id, source_case_id FROM merges WHERE id = :id"), {"id": merge_id}).one_or_none()
        if m is None:
            raise LookupError(merge_id)
        _visible(conn, scope, [m.target_case_id])
        return undo_merge(conn, merge_id, _actor(scope), body.reason)
    return _run(go)
