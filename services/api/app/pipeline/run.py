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
from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import ValidationError
from sqlalchemy import Connection, Engine, text

from app.contracts import Extraction
from app.core.eventlog import WORKER, append_event
from app.core.flags import language_model_enabled
from app.core.jobs import RetryLater, enqueue, handler
from app.modules.cases.service import create_case
from app.modules.dedupe.candidates import candidates, landmark_keys
from app.modules.dedupe.decide import decide, reason_line
from app.modules.dedupe.merge import merge_cases, record_suggestion
from app.modules.dedupe.signals import Household
from app.modules.evidence.service import TEXT, add
from app.modules.location.ladder import resolve as resolve_location
from app.modules.triage.rules import triage
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


def transcribe(engine: Engine, report) -> tuple[str | None, dict]:
    """Stage 1a (voice only; network, outside any transaction). Returns (transcript or None, receipt step)."""
    from app.core import storage
    from app.providers import stt
    with engine.connect() as c:
        ev = c.execute(text("SELECT sha256, meta FROM evidence WHERE report_id = :r AND type = 'audio' ORDER BY id LIMIT 1"),
                       {"r": report.id}).one_or_none()
    if ev is None:
        return None, {"step": "stt", "by": "Rule", "detail": "no audio attached"}
    wav = storage.path_for(ev.meta["wav_sha256"]).read_bytes()
    try:
        res = stt.transcribe(wav, float(ev.meta.get("seconds", 0)), ev.sha256)
    except AllProvidersFailed as e:
        return None, {"step": "stt", "by": "AI", "detail": "speech-to-text failed: " + "; ".join(
            f"{a['provider']} {a['outcome']}" for a in e.attempts)}
    by, label = ("Fixture", "recorded transcript (not live speech to text)") if res.provider == "fixture" \
        else ("AI", f"{res.provider} {res.model} · {res.latency_ms / 1000:.1f} s")
    if not res.value.text.strip():
        return None, {"step": "stt", "by": by, "detail": f"{label}: empty transcript"}
    return res.value.text.strip(), {"step": "stt", "by": by, "detail": label, "language": res.value.language}


def extract(report, allow_model: bool = True, rules_why: str = "seeded report") -> Extracted:
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
    if not allow_model:     # seeding (never spend free quota on seed reports); spreadsheet rows (rules first)
        return Extracted(keywords, "rules", [{"step": "extract", "by": "Rule",
                                              "detail": f"{rules_why}, keywords: {_count(keywords)} fields"}])
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
        why = ("language model down" if down else
               "language model unavailable · " + "; ".join(a["outcome"] for a in e.attempts))
        return Extracted(keywords, "rules", [{"step": "extract", "by": "Rule", "detail": f"{why}: {_count(keywords)} fields"}],
                         backfill=down)
    except ProviderUnavailable as e:
        return Extracted(keywords, "rules", [{"step": "extract", "by": "Rule",
                                              "detail": f"language model unavailable ({e}): {_count(keywords)} fields"}])
    except ValidationError as e:
        first = (e.errors() or [{}])[0]                       # name the field, so a receipt explains itself
        where = ".".join(str(x) for x in first.get("loc", ())) or "the output"
        return Extracted(keywords, "rules", [{"step": "extract", "by": "Rule",
                                              "detail": f"model output didn't fit the contract"
                                                        f" ({where}: {first.get('msg', 'invalid')})"
                                                        f": {_count(keywords)} fields"}])
    amber = llm_extract.check_quotes(ex, text_in)
    extras = llm_extract.cross_check(ex, keywords)
    checks = "quotes ✓" if not amber else f"{len(amber)} quote(s) not found: amber"
    if extras:
        checks += f" · keywords add {sum(len(v) for v in extras.values())}"
    return Extracted(ex, "ai", [step, {"step": "quotes", "by": "Rule", "detail": checks}], amber, extras)


def _count(ex: Extraction) -> int:
    return (bool(ex.people_count) + len(ex.hazards) + len(ex.needs) + len(ex.vulnerable)
            + bool(ex.location.village_or_locality) + len(ex.location.landmarks))


@dataclass
class Prepared:
    """Stage 1's result for one report: everything decided by rules and the AI, nothing written yet."""
    out: Extracted
    fields: dict
    located: object | None
    receipt: list[dict]
    district_hint: int | None


def prepare(engine: Engine, report, *, allow_model: bool = True, rules_why: str = "seeded report",
            adjust: Callable[[Extraction, str], tuple[Extraction, set[str]]] | None = None) -> Prepared:
    """Stage 1 (network allowed; no transaction held). `adjust` lets a channel add facts it holds as data,
    e.g. a spreadsheet's mapped columns; the keys it fills are labelled Rule, with the column as the quote."""
    stt_steps: list[dict] = []
    audio_only = False
    if report.channel == "voice" and not report.transcript:
        transcript, step = transcribe(engine, report)
        stt_steps.append(step)
        if transcript is None:
            audio_only = True          # the clip still becomes a case: "audio only: listen", sorted as urgent
        else:
            with engine.begin() as conn:
                saved = conn.execute(text("UPDATE reports SET transcript = :t, language = :l WHERE id = :id AND transcript IS NULL"),
                                     {"t": transcript, "l": step.get("language"), "id": report.id}).rowcount
                if saved:   # the words as speech-to-text gave them, hashed like the clip they came from
                    add(conn, type="transcript", content=transcript.encode(), mime=TEXT, actor=WORKER,
                        added_by=f"stt:{step.get('by')}", report_id=report.id,
                        meta={"by": step.get("by"), "detail": step.get("detail"), "language": step.get("language")})
            report = load_report(engine, report.id)
    if audio_only:
        out = Extracted(Extraction.empty(), "rules", [])
    else:
        out = extract(report, allow_model=allow_model, rules_why=rules_why)
    from_columns: set[str] = set()
    if adjust:
        out.extraction, from_columns = adjust(out.extraction, out.method)
    extraction, method, receipt = out.extraction, out.method, stt_steps + out.receipt
    fields = fields_from_extraction(extraction, method, report.id, out.amber, out.extras)
    for key in from_columns:
        if isinstance(fields["provenance"].get(key), dict):
            fields["provenance"][key].update(method="rule", source="sheet column")
    # Stage 1d: resolve location (rules over the committed gazetteer; read-only, no transaction held).
    district_hint = (report.source or {}).get("district_hint")
    with engine.connect() as c:
        located = resolve_location(c, report.incident_id, extraction, report.transcript or report.text or "",
                                   district_hint) if report.incident_id else None
    if located:
        fields.update(located.fields())
        fields["attributes"]["location_detail"] = fields.pop("location_detail")
        fields["flags"] = list(located.flags)
        if located.place:
            fields["location_text"] = located.place["name"]
        receipt.append({"step": "place", "by": "Rule", "detail": located.method.split(" · ")[0] + " · "
                        + located.method.split(" · ")[1] if located.lat is not None else "no location: needs a person"})
    if audio_only:
        fields["flags"] = ["audio_only", *fields.get("flags", [])]
        fields["summary"] = "audio only: listen"
    if llm_extract.instruction_like(report.transcript or report.text or ""):   # P1 #11: flagged, and changes nothing
        fields["flags"] = [*fields.get("flags", []), "instruction_like_text"]
        receipt.append({"step": "words", "by": "Rule", "detail": "instruction-like words flagged · priority still comes only from the rules"})
    priority, reasons, rank = triage(fields)                  # Stage 3: rules, never the model
    fields.update(priority=priority, priority_reasons=reasons, p1_rank=rank)
    receipt.append({"step": "priority", "by": "Rule", "detail": f"{priority} · {' · '.join(reasons)}"})
    return Prepared(out, fields, located, receipt, district_hint)


def commit(engine: Engine, report, p: Prepared,
           on_commit: Callable[[Connection, dict], None] | None = None) -> dict | None:
    """Stages 2–3 in ONE short transaction under the incident lock. Returns what happened, or None if
    another worker got there first. `on_commit(conn, result)` runs inside the same transaction."""
    extraction, method, fields, located, district_hint = (p.out.extraction, p.out.method, p.fields, p.located,
                                                          p.district_hint)
    with engine.begin() as conn:
        locked = conn.execute(text("SELECT case_id, incident_id, source FROM reports WHERE id = :id FOR UPDATE"),
                              {"id": report.id}).one()
        if locked.case_id is not None:
            return None
        if locked.incident_id is None:
            conn.execute(text("UPDATE reports SET status = 'needs_review', review_reason = 'unknown incident'"
                              " WHERE id = :id"), {"id": report.id})
            result = {"outcome": "needs_review", "case_id": None, "public_id": None, "line": "unknown incident"}
            if on_commit:
                on_commit(conn, result)
            return result
        conn.execute(text("UPDATE reports SET extraction = CAST(:e AS jsonb), extraction_method = :m,"
                          " receipt = CAST(:r AS jsonb) WHERE id = :id"),
                     {"e": extraction.model_dump_json(), "m": method, "r": json.dumps(p.receipt), "id": report.id})
        # Stage 2: DEDUPE, under a per-incident lock so two reports about one household arriving in the same
        # second can't both create a case (rule R5).
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"dedupe:{locked.incident_id}"})
        new = household_of(report, fields)
        decision = decide(conn, new, candidates(conn, locked.incident_id, new))
        # Every report gets its own case first (so the reporter always has an id that later redirects);
        # an auto-merge then folds it into the older case at once, undoable like any merge.
        created = create_case(conn, incident_id=locked.incident_id,
                              district_id=(located.district_id if located and located.district_id else district_hint),
                              report_id=report.id, fields=fields, actor=WORKER, queue_since=report.received_at)
        result = {"case_id": created["case_id"], "public_id": created["public_id"], "flags": fields.get("flags", [])}
        if decision.kind == "auto_merge":
            m = decision.target
            line = reason_line(m)
            merge_cases(conn, target_id=m.candidate.case_id, source_id=created["case_id"], actor=WORKER,
                        decided_by="rule", score=m.score.total, signals=m.score.signals, reasons=m.reasons, line=line)
            result.update(outcome="merged", case_id=m.candidate.case_id, line=line)
        else:
            lines = []
            for m in decision.suggestions:
                lines.append(reason_line(m))
                record_suggestion(conn, incident_id=locked.incident_id, district_id=created["district_id"],
                                  case_id=created["case_id"], match=m, line=lines[-1], actor=WORKER)
            open_ = [m for m in decision.suggestions if m.strength != "refused"]
            result.update(outcome="suggested" if open_ else ("refused" if decision.suggestions else "new"),
                          line=lines[0] if lines else None)
            if p.out.backfill:
                # When the language model is back it re-reads this report (F-C14). Seen as "waiting" in jobs.
                enqueue(conn, "llm.backfill", {"report_id": report.id, "case_id": created["case_id"]}, "backfill",
                        dedupe_key=f"report:{report.id}:backfill")
        if on_commit:
            on_commit(conn, result)
        return result


@handler("report.process")
def process_report(engine: Engine, payload: dict) -> dict | None:
    report = load_report(engine, payload["report_id"])
    if report is None or report.case_id is not None:
        return None                                       # idempotent: already processed
    return commit(engine, report, prepare(engine, report, allow_model=not payload.get("seed")))


def household_of(report, fields: dict) -> Household:
    """The new report as a household for duplicate scoring."""
    attrs = fields.get("attributes") or {}
    return Household(
        case_id=None, phones={report.reporter_phone_hash} if report.reporter_phone_hash else set(),
        devices={report.device_hash} if report.device_hash else set(), village=fields.get("location_text"),
        lat=fields.get("lat"), lng=fields.get("lng"), radius_m=fields.get("radius_m"),
        confidence=fields.get("location_confidence"),
        landmarks=landmark_keys(attrs.get("location_detail"), fields.get("provenance")),
        people=fields.get("people_count"), names=list(attrs.get("person_names") or []), at=report.received_at)


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
        from app.modules.cases.service import retriage
        retriage(conn, case.id, WORKER, why="language model back-filled the facts")
        conn.execute(text("UPDATE reports SET extraction = CAST(:e AS jsonb), extraction_method = 'ai',"
                          " receipt = receipt || CAST(:r AS jsonb) WHERE id = :id"),
                     {"e": ex.model_dump_json(), "id": report.id,
                      "r": json.dumps([{"step": "backfill", "by": "AI", "detail": f"language model back-filled · {src}"}])})
        append_event(conn, actor=WORKER, action="case.updated", entity_type="case", entity_id=case.id,
                     incident_id=case.incident_id, district_id=case.district_id, case_id=case.id,
                     data={"why": "language model back-filled the rule-made fields", "report_id": report.id})
