"""Evidence items (PRD F-C11): every one is a file in the content-addressed store (`files/ab/<sha256>`, hashed
while it is written), and its sha256 goes into the audit chain in an `evidence.added` event (rule R16). So a
file swapped on disk later fails its re-hash, and a row edited in the database no longer matches the chain.

Types (an open list): audio, transcript, message, sheet_row, merge, rescue, radio, partner_annotation.
An item made for a report before its case exists (a clip, a transcript, the original message) is linked, and
its event written, when the report's case is created (cases.service.link_report_evidence).
"""

import json

from sqlalchemy import Connection, text

from app.core import storage
from app.core.eventlog import Actor, append_event

MAX_RECORD = 1024 * 1024
TEXT = "text/plain; charset=utf-8"
JSON = "application/json"


def record_bytes(obj: dict) -> bytes:
    """A record as stored: canonical JSON (sorted keys), so the same record always has the same hash."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()


def add(conn: Connection, *, type: str, content: bytes, mime: str, actor: Actor, added_by: str,
        meta: dict | None = None, report_id: int | None = None, case_id: int | None = None,
        incident_id: int | None = None, district_id: int | None = None) -> int:
    sha, size = storage.store_bytes(content, MAX_RECORD)
    uri = storage.uri_for(sha)
    eid = conn.execute(text(
        "INSERT INTO evidence (case_id, report_id, type, uri, sha256, mime, bytes, added_by, meta)"
        " VALUES (:c, :r, :t, :uri, :sha, :mime, :n, :by, CAST(:meta AS jsonb)) RETURNING id"),
        {"c": case_id, "r": report_id, "t": type, "uri": uri, "sha": sha, "mime": mime, "n": size, "by": added_by,
         "meta": json.dumps(meta or {}, ensure_ascii=False, default=str)}).scalar_one()
    if case_id is not None:
        append_event(conn, actor=actor, action="evidence.added", entity_type="evidence", entity_id=eid,
                     incident_id=incident_id, district_id=district_id, case_id=case_id,
                     data={"evidence_id": eid, "type": type, "sha256": sha, "uri": uri, "report_id": report_id})
    return eid
