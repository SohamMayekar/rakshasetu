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
from dataclasses import dataclass, field

from pydantic import ValidationError
from sqlalchemy import Engine, text

from app.config import get_config
from app.contracts import Extraction
from app.core.eventlog import WORKER, append_event
from app.core.flags import language_model_enabled
from app.core.jobs import RetryLater, enqueue, handler
from app.modules.cases.service import create_case
from app.pipeline import llm_extract
from app.pipeline.fields import fields_from_extraction
from app.pipeline.keywords import extract_keywords
from app.providers.base import AllProvidersFailed, ProviderUnavailable


@dataclass
class Extracted:
    extraction: Extraction
    method: str                          # ai | rules | structured
    receipt: list[dict]
    amber: dict = field(default_factory=dict)
    extras: dict = field(default_factory=dict)
    backfill: bool = False               # True: the model was down; re-read this report when it's back


def load_report(engine: Engine, report_id: int):
    with engine.connect() as c:
        return c.execute(text("SELECT * FROM reports WHERE id = :id"), {"id": report_id}).one_or_none()


def extract(report) -> Extracted:
    """Stage 1b (network; never inside a transaction).
    Pre-structured partner/surge fields → used as given (validated). Language model on → the model's
    extraction (cache first), quote-checked and cross-checked by rules. Model off, down, out of quota or
    returning output that doesn't fit the contract → the keyword path creates the case (F-C14)."""
    text_in = report.transcript or report.text or ""
    if report.structured:
        try:
            ex = Extraction.model_validate(report.structured)
            return Extracted(ex, "structured", [{"step": "extract", "by": "Partner", "detail": "pre-structured fields, validated"}])
        except ValidationError:
            pass   # read the text instead
    keywords = extract_keywords(text_in)
    if not language_model_enabled():
        return Extracted(keywords, "rules", [{"step": "extract", "by": "Rule",
                                              "detail": f"language model off: {_count(keywords)} fields"}], backfill=True)
    hit = llm_extract.cached(text_in)
    try:
        if hit:
            ex, src = hit
            step = {"step": "extract", "by": "AI", "detail": f"{_count(ex)} fields · cached result of {src}"}
        else:
            ex, src, ms = llm_extract.ask_model(text_in)
            step = {"step": "extract", "by": "AI", "detail": f"{_count(ex)} fields · {src} · {ms} ms"}
    except AllProvidersFailed as e:
        down = any(a["outcome"].startswith("failed") for a in e.attempts)
        why = "language model down" if down else "language model unavailable (no key)"
        return Extracted(keywords, "rules", [{"step": "extract", "by": "Rule", "detail": f"{why}: {_count(keywords)} fields"}],
                         backfill=down)
    except ProviderUnavailable as e:
        return Extracted(keywords, "rules", [{"step": "extract", "by": "Rule",
                                              "detail": f"language model unavailable ({e}): {_count(keywords)} fields"}])
    except ValidationError:
        return Extracted(keywords, "rules", [{"step": "extract", "by": "Rule",
                                              "detail": f"model output didn't fit the contract: {_count(keywords)} fields"}])
    amber = llm_extract.check_quotes(ex, text_in)
    extras = llm_extract.cross_check(ex, keywords)
    checks = "quotes ✓" if not amber else f"{len(amber)} quote(s) not found: amber"
    if extras:
        checks += f" · keywords add {sum(len(v) for v in extras.values())}"
    return Extracted(ex, "ai", [step, {"step": "quotes", "by": "Rule", "detail": checks}], amber, extras)


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
    out = extract(report)
    extraction, method, receipt = out.extraction, out.method, out.receipt
    fields = fields_from_extraction(extraction, method, report.id, out.amber, out.extras)
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
        created = create_case(conn, incident_id=locked.incident_id,
                              district_id=(locked.source or {}).get("district_hint"),
                              report_id=report.id, fields=fields, actor=WORKER, queue_since=report.received_at)
        if out.backfill:
            # When the language model is back it re-reads this report (F-C14). Seen as "waiting" in jobs.
            enqueue(conn, "llm.backfill", {"report_id": report.id, "case_id": created["case_id"]}, "backfill",
                    dedupe_key=f"report:{report.id}:backfill")


RULE_FIELDS = ("hazards", "needs", "vulnerable", "landmarks")


@handler("llm.backfill")
def backfill(engine: Engine, payload: dict) -> None:
    """Re-read a rule-made case with the language model once it is back. Only this report's unchecked
    Rule values are replaced; anything a person checked or set stays as it is."""
    if not language_model_enabled():
        raise RetryLater(30, "language model off")
    report = load_report(engine, payload["report_id"])
    text_in = report.transcript or report.text or ""
    hit = llm_extract.cached(text_in)
    try:
        ex, src = hit if hit else llm_extract.ask_model(text_in)[:2]
    except (AllProvidersFailed, ProviderUnavailable):
        raise RetryLater(60, "language model unavailable") from None
    except ValidationError:
        return   # keep the rule-made fields
    keywords = extract_keywords(text_in)
    new = fields_from_extraction(ex, "ai", report.id, llm_extract.check_quotes(ex, text_in),
                                 llm_extract.cross_check(ex, keywords))
    with engine.begin() as conn:
        case = conn.execute(text("SELECT id, incident_id, district_id, provenance, checked_by FROM cases"
                                 " WHERE id = :c FOR UPDATE"), {"c": payload["case_id"]}).one()
        prov = dict(case.provenance or {})
        mine = lambda p: p.get("report_id") == report.id and p.get("method") == "rule" and not p.get("checked")  # noqa: E731
        for name in RULE_FIELDS:
            prov[name] = [p for p in prov.get(name, []) if not mine(p)] + new["provenance"].get(name, [])
        for name in ("people_count", "place"):
            if name in new["provenance"] and (name not in prov or mine(prov[name])):
                prov[name] = new["provenance"][name]
        hazards = list(dict.fromkeys(p["value"] for p in prov.get("hazards", [])))
        needs = list(dict.fromkeys(p["value"] for p in prov.get("needs", [])))
        vulnerable = list(dict.fromkeys(p["value"] for p in prov.get("vulnerable", [])))
        people = prov.get("people_count", {}).get("value")
        from app.pipeline.fields import summary
        conn.execute(text(
            "UPDATE cases SET provenance = CAST(:p AS jsonb), hazards = :h, needs = :n, vulnerable = :v,"
            " people_count = :pc, summary = :s, version = version + 1, updated_at = now() WHERE id = :c"),
            {"p": json.dumps(prov, ensure_ascii=False), "h": hazards, "n": needs, "v": vulnerable, "pc": people,
             "s": summary(people, None, hazards, needs, vulnerable), "c": case.id})
        conn.execute(text("UPDATE reports SET extraction = CAST(:e AS jsonb), extraction_method = 'ai',"
                          " receipt = receipt || CAST(:r AS jsonb) WHERE id = :id"),
                     {"e": ex.model_dump_json(), "id": report.id,
                      "r": json.dumps([{"step": "backfill", "by": "AI", "detail": f"language model back-filled · {src}"}])})
        append_event(conn, actor=WORKER, action="case.updated", entity_type="case", entity_id=case.id,
                     incident_id=case.incident_id, district_id=case.district_id, case_id=case.id,
                     data={"why": "language model back-filled the rule-made fields", "report_id": report.id})
