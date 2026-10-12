"""report.process: the intake pipeline for one report (PRD §8.1), as plain functions.

    1. INTAKE   transcribe* → extract → check quotes → resolve location      (outside any transaction)
    2. DEDUPE   score candidates → create / merge / suggest / refuse         (one short transaction,
    3. TRIAGE   priority rules → reasons                                      under the incident lock)
    4. SUGGEST  rank teams (computed when the desk asks; a person assigns)

Network calls (STT, LLM) never run while a database transaction or lock is open. The handler is
idempotent: a report that already has a case is left alone, so a reclaimed job can't make a second case.
Stages are filled in milestone by milestone; each records a step in the report's pipeline receipt.
"""

import json

from sqlalchemy import Engine, text

from app.config import get_config
from app.contracts import Extraction
from app.core.eventlog import WORKER
from app.core.jobs import handler
from app.modules.cases.service import create_case


def load_report(engine: Engine, report_id: int):
    with engine.connect() as c:
        return c.execute(text("SELECT * FROM reports WHERE id = :id"), {"id": report_id}).one_or_none()


def extract(report) -> tuple[Extraction, str, list[dict]]:
    """Stage 1b. Until the keyword path (m18) and the language model (m19) exist, nothing is extracted."""
    return Extraction.empty(report.language), "rules", [{"step": "extract", "by": "Rule", "detail": "no extractor yet"}]


def triage(fields: dict) -> tuple[str, list[str]]:
    """Stage 3. With no extracted facts, only the catch-all rule (the last one in the config) can match."""
    catch_all = get_config().priority[-1]
    return catch_all.level, [catch_all.reason]


@handler("report.process")
def process_report(engine: Engine, payload: dict) -> None:
    report = load_report(engine, payload["report_id"])
    if report is None or report.case_id is not None:
        return                                            # idempotent: already processed
    extraction, method, receipt = extract(report)
    fields: dict = {}
    priority, reasons = triage(fields)
    fields.update(priority=priority, priority_reasons=reasons)
    receipt.append({"step": "priority", "by": "Rule", "detail": f"{priority} · {reasons[0]}"})
    with engine.begin() as conn:
        locked = conn.execute(text("SELECT case_id, incident_id, source FROM reports WHERE id = :id FOR UPDATE"),
                              {"id": report.id}).one()
        if locked.case_id is not None:
            return
        if locked.incident_id is None:
            conn.execute(text("UPDATE reports SET status = 'needs_review', review_reason = 'unknown incident'"
                              " WHERE id = :id"), {"id": report.id})
            return
        conn.execute(text("UPDATE reports SET extraction = CAST(:e AS jsonb), extraction_method = :m,"
                          " receipt = CAST(:r AS jsonb) WHERE id = :id"),
                     {"e": extraction.model_dump_json(), "m": method, "r": json.dumps(receipt), "id": report.id})
        create_case(conn, incident_id=locked.incident_id, district_id=(locked.source or {}).get("district_hint"),
                    report_id=report.id, fields=fields, actor=WORKER, queue_since=report.received_at)
