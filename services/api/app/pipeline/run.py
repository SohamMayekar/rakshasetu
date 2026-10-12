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

from pydantic import ValidationError
from sqlalchemy import Engine, text

from app.config import get_config
from app.contracts import Extraction
from app.core.eventlog import WORKER
from app.core.flags import language_model_enabled
from app.core.jobs import handler
from app.modules.cases.service import create_case
from app.pipeline.fields import fields_from_extraction
from app.pipeline.keywords import extract_keywords


def load_report(engine: Engine, report_id: int):
    with engine.connect() as c:
        return c.execute(text("SELECT * FROM reports WHERE id = :id"), {"id": report_id}).one_or_none()


def extract(report) -> tuple[Extraction, str, list[dict]]:
    """Stage 1b. Pre-structured partner/surge fields are used as given (validated against the contract);
    otherwise the keyword path reads the text. The language model joins in m19."""
    text_in = report.transcript or report.text or ""
    if report.structured:
        try:
            ex = Extraction.model_validate(report.structured)
            return ex, "structured", [{"step": "extract", "by": "Partner", "detail": "pre-structured fields, validated"}]
        except ValidationError:
            pass   # fall through: read the text instead
    ex = extract_keywords(text_in)
    why = "language model off" if not language_model_enabled() else "keywords"
    return ex, "rules", [{"step": "extract", "by": "Rule", "detail": f"{why}: {_count(ex)} fields"}]


def _count(ex: Extraction) -> int:
    return (bool(ex.people_count) + len(ex.hazards) + len(ex.needs) + len(ex.vulnerable)
            + bool(ex.location.village_or_locality) + len(ex.location.landmarks))


def triage(fields: dict) -> tuple[str, list[str]]:
    """Stage 3. The rule engine arrives in m25; until then every case gets the config's catch-all rule
    (P4, "no urgent signal yet: check"), so a person reads it."""
    catch_all = get_config().priority[-1]
    return catch_all.level, [catch_all.reason]


@handler("report.process")
def process_report(engine: Engine, payload: dict) -> None:
    report = load_report(engine, payload["report_id"])
    if report is None or report.case_id is not None:
        return                                            # idempotent: already processed
    extraction, method, receipt = extract(report)
    fields = fields_from_extraction(extraction, method, report.id)
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
