"""Spreadsheet import, steps 1–3 (PRD F-D3). Desk only (local listener), `import.run`, inside the Scope.

POST /v1/imports               upload a CSV/XLSX (multipart: file, incident) → stored by hash, headers read,
                               mapping proposed, preview of how the first rows read
GET  /v1/imports/{id}          the import's state and counts
POST /v1/imports/{id}/mapping  a person confirms (or corrects) the mapping; that one click starts the import job
GET  /v1/imports/{id}/rows     every row's outcome and its reason (the judge can pick any row)
"""

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.auth import Scope, require
from app.core.eventlog import Actor, append_event
from app.core.jobs import enqueue
from app.core.listener import require_local
from app.core.phones import mask
from app.core.storage import path_for, store_bytes
from app.db import get_engine
from app.modules.imports import mapping as mapping_mod
from app.modules.imports.normalise import normalise_row
from app.modules.imports.parse import MAX_BYTES, Sheet, SheetError, read

router = APIRouter(prefix="/v1/imports", tags=["imports"], dependencies=[Depends(require_local)])
PREVIEW_ROWS = 8


def _actor(scope: Scope) -> Actor:
    return Actor("user", str(scope.user_id), scope.role)


def _where(scope: Scope) -> tuple[str, dict]:
    """Which imports this caller may see: their incidents and districts (rule R8, inside the SQL)."""
    if scope.role == "admin":
        return "TRUE", {}
    return ("(m.incident_id = ANY(:scope_incidents) AND (m.district_id IS NULL OR m.district_id = ANY(:scope_districts)))",
            {"scope_incidents": list(scope.incident_ids), "scope_districts": list(scope.district_ids)})


def preview(sheet: Sheet, mapping: dict[str, str], at: datetime) -> list[dict]:
    out = []
    for number, cells in zip(sheet.numbers[:PREVIEW_ROWS], sheet.rows[:PREVIEW_ROWS], strict=True):
        n = normalise_row(cells, sheet.headers, mapping, at)
        out.append({"row": number, "cells": cells,   # numbered as the volunteer sees it in Excel (header = 1)
                    "reads_as": {"name": n["name"], "phone": mask(n["phone"]) if n["phone"] else None,
                                 "headcount": n["headcount"], "headcount_kind": n["headcount_kind"],
                                 "village": n["village"], "time": n["time"].isoformat() if n["time"] else None,
                                 "done": n["done"], "text": n["text"]},
                    "flags": n["flags"]})
    return out


def _view(r) -> dict:
    d = dict(r._mapping)
    for k in ("created_at", "started_at", "finished_at"):
        d[k] = d[k].isoformat() if d[k] else None
    d["warnings"] = list(d["warnings"])
    return d


@router.post("", status_code=201)
def upload(file: UploadFile = File(...), incident: str = Form(..., max_length=10),
           scope: Scope = Depends(require("import.run"))) -> dict:
    data = file.file.read(MAX_BYTES + 1)
    name = (file.filename or "sheet").rsplit("/", 1)[-1][:200]
    try:
        sheet = read(name, data)
    except SheetError as e:
        raise HTTPException(422, f"Couldn't read this sheet: {e}") from None
    if not sheet.rows:
        raise HTTPException(422, "Couldn't read this sheet: it has headers but no rows")
    now = datetime.now(UTC)
    with get_engine().begin() as conn:
        inc = conn.execute(text("SELECT id, status FROM incidents WHERE code = :c"), {"c": incident}).one_or_none()
        if inc is None or (scope.role != "admin" and inc.id not in scope.incident_ids):
            raise HTTPException(404, "No such incident")
        if inc.status == "closed":
            raise HTTPException(409, "This incident is closed")
        sha, _ = store_bytes(data, MAX_BYTES)
        proposed = mapping_mod.propose(sheet.headers)
        district_id = scope.district_ids[0] if scope.district_ids and scope.role != "admin" else None
        iid = conn.execute(text(
            "INSERT INTO imports (incident_id, district_id, file_name, file_sha256, file_kind, encoding, uploaded_by,"
            " headers, proposed, preview, rows_total, warnings)"
            " VALUES (:inc, :d, :name, :sha, :kind, :enc, :u, CAST(:headers AS jsonb), CAST(:proposed AS jsonb),"
            "         CAST(:preview AS jsonb), :n, :warnings) RETURNING id"),
            dict(inc=inc.id, d=district_id, name=name, sha=sha, kind=sheet.kind, enc=sheet.encoding, u=scope.user_id,
                 headers=_json(sheet.headers), proposed=_json(proposed),
                 preview=_json(preview(sheet, proposed, now)), n=len(sheet.rows),
                 warnings=sheet.warnings)).scalar()
        append_event(conn, actor=_actor(scope), action="import.uploaded", entity_type="import", entity_id=iid,
                     incident_id=inc.id, district_id=district_id,
                     data={"import_id": iid, "file_name": name, "file_sha256": sha, "rows": len(sheet.rows)})
        r = conn.execute(text("SELECT * FROM imports m WHERE id = :id"), {"id": iid}).one()
    return _view(r)


@router.get("")
def list_imports(incident: str | None = None, scope: Scope = Depends(require("import.run"))) -> list[dict]:
    """This desk's imports for an incident, newest first."""
    where, params = _where(scope)
    with get_engine().connect() as conn:
        rows = conn.execute(text(f"SELECT m.* FROM imports m JOIN incidents i ON i.id = m.incident_id"
                                 f" WHERE (CAST(:code AS text) IS NULL OR i.code = :code) AND {where} ORDER BY m.id DESC LIMIT 20"),
                            {**params, "code": incident}).all()
    return [_view(r) for r in rows]


@router.get("/{iid}")
def get_import(iid: int, scope: Scope = Depends(require("import.run"))) -> dict:
    where, params = _where(scope)
    with get_engine().connect() as conn:
        r = conn.execute(text(f"SELECT * FROM imports m WHERE m.id = :id AND {where}"), {**params, "id": iid}).one_or_none()
    if r is None:
        raise HTTPException(404, "No such import")
    return _view(r)


class Mapping(BaseModel):
    mapping: dict[str, str] = Field(max_length=40)


@router.post("/{iid}/mapping")
def confirm_mapping(iid: int, body: Mapping, scope: Scope = Depends(require("import.run"))) -> dict:
    where, params = _where(scope)
    with get_engine().begin() as conn:
        r = conn.execute(text(f"SELECT * FROM imports m WHERE m.id = :id AND {where} FOR UPDATE"),
                         {**params, "id": iid}).one_or_none()
        if r is None:
            raise HTTPException(404, "No such import")
        if r.status not in ("uploaded", "mapped"):
            raise HTTPException(409, f"This import is already {r.status}")
        problems = mapping_mod.validate(body.mapping, list(r.headers))
        if problems:
            raise HTTPException(422, problems)
        clean = {h: ("ignore" if f == "unknown" else f) for h, f in body.mapping.items()}
        sheet = _reread(r)
        conn.execute(text("UPDATE imports SET mapping = CAST(:m AS jsonb), preview = CAST(:p AS jsonb), status = 'mapped'"
                          " WHERE id = :id"),
                     {"m": _json(clean), "p": _json(preview(sheet, clean, r.created_at)), "id": iid})
        changed = sorted(h for h in clean if clean[h] != (r.proposed or {}).get(h))
        append_event(conn, actor=_actor(scope), action="import.mapped", entity_type="import", entity_id=iid,
                     incident_id=r.incident_id, district_id=r.district_id,
                     data={"import_id": iid, "mapping": clean, "changed_from_proposal": changed})
        enqueue(conn, "import.run", {"import_id": iid}, "import", dedupe_key=f"import:{iid}:run", max_attempts=3)
        r = conn.execute(text("SELECT * FROM imports m WHERE id = :id"), {"id": iid}).one()
    return _view(r)


@router.get("/{iid}/rows")
def import_rows(iid: int, outcome: str | None = None, limit: int = 500,
                scope: Scope = Depends(require("import.run"))) -> list[dict]:
    where, params = _where(scope)
    with get_engine().connect() as conn:
        if conn.execute(text(f"SELECT 1 FROM imports m WHERE m.id = :id AND {where}"), {**params, "id": iid}).first() is None:
            raise HTTPException(404, "No such import")
        rows = conn.execute(text(
            "SELECT r.row_number, r.outcome, r.read_by, r.reason, r.flags, r.case_id, c.public_id, c.priority, c.status,"
            " EXISTS (SELECT 1 FROM assignments a WHERE a.case_id = c.id AND a.state IN ('open', 'overdue')) AS owned"
            " FROM import_rows r LEFT JOIN cases c ON c.id = r.case_id"
            " WHERE r.import_id = :id AND (CAST(:o AS text) IS NULL OR r.outcome = :o)"
            " ORDER BY r.row_number LIMIT :lim"), {"id": iid, "o": outcome, "lim": min(max(limit, 1), 5000)}).all()
    return [{**dict(r._mapping), "flags": list(r.flags)} for r in rows]


def _reread(r):
    return read(r.file_name, path_for(r.file_sha256).read_bytes())


def _json(v) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)
