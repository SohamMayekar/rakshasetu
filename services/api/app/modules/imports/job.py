"""The import job (PRD F-D3 steps 4–8): one durable, resumable job per import on the `import` lane.

Per row, in sheet order:
    normalise → write the report and its `sheet_row` evidence (file hash + row number + the raw cells)
    → rules first (keywords + the mapped columns + the location ladder) → commit: dedupe against every open
    case (earlier rows of this file included, so the file clusters with the same scorer and no chains),
    create the case, and the row's outcome in `import_rows`, all in ONE short transaction.
Rows the rules can't place or count go to the language model afterwards, 20 at a time, one batch at a
time; each row is still its own call, so a quote can only ever come from that row (D9).
The summary is computed from `import_rows`, so it always equals the database.
A killed worker loses nothing: the job is reclaimed, finished rows are skipped, replays are idempotent.
"""

import json
import time
from datetime import UTC

from sqlalchemy import Engine, text

from app.contracts import CanonicalReport, Content, PeopleCount, PersonName, Reporter, Source, Village
from app.core.eventlog import WORKER, append_event
from app.core.jobs import RetryLater, enqueue, handler
from app.core.storage import path_for, uri_for
from app.modules.imports.normalise import normalise_row
from app.modules.imports.parse import read
from app.modules.intake.service import accept
from app.pipeline import llm_extract
from app.pipeline.keywords import to_latin
from app.pipeline.run import commit, load_report, prepare

LANE = "import"
BATCH = 20
PROGRESS_EVERY_S = 1.0
DAMAGED = "phone damaged by Excel"
OLD = "old report: confirm before sending a team"


def columns(n: dict):
    """The mapped columns are data, not prose: they fill the facts directly, labelled Rule (sheet column)."""
    def adjust(ex, _method):
        keys, loc = set(), ex.location
        if n["headcount"] is not None:
            ex = ex.model_copy(update={"people_count": PeopleCount(value=n["headcount"], kind=n["headcount_kind"],
                                                                     quote=n["headcount_cell"][:300])})
            keys.add("people_count")
        if n["village"]:
            loc = loc.model_copy(update={"village_or_locality": Village(original=n["village"][:100],
                                                                        latin=to_latin(n["village"])[:100],
                                                                        quote=n["village"][:300])})
            keys.add("place")
        if n["district"] and not loc.district:
            loc = loc.model_copy(update={"district": n["district"][:100]})
        names = list(ex.person_names)
        if n["name"] and all(p.name.lower() != n["name"].lower() for p in names) and len(names) < 10:
            names.append(PersonName(name=n["name"][:100], quote=n["name"][:300]))
        return ex.model_copy(update={"location": loc, "person_names": names}), keys
    return adjust


def needs_model(p) -> bool:
    """Rules couldn't place it (no pin, or district only) or couldn't count the people."""
    located = p.located
    return located is None or located.lat is None or located.step >= 7 or not p.fields.get("people_count")


class Run:
    def __init__(self, engine: Engine, imp):
        self.engine, self.imp = engine, imp
        self.last_progress = 0.0

    # --- one row ---------------------------------------------------------------------------------------------
    def write(self, number: int, n: dict):
        """Write the row's report and evidence (idempotent: the key is the file hash + row number)."""
        imp = self.imp
        if not (n["text"] or n["name"] or n["phone"] or n["headcount"] is not None):
            self.record(number, None, None, "dropped", None, "row has nothing in its mapped columns", n["flags"])
            return None
        report = CanonicalReport(
            schema_version="1", idempotency_key=f"{imp.file_sha256}:{number}", channel="spreadsheet",
            incident_hint=imp.incident_code, received_at=n["time"] or imp.created_at,
            reporter=Reporter(phone=n["phone"], name=n["name"][:200] if n["name"] else None, relation="volunteer"),
            content=Content(text=n["text"][:20000] or None),
            source=Source(system="spreadsheet", ref=f"import:{imp.id}", file_sha256=imp.file_sha256, row=number))
        with self.engine.begin() as conn:
            acc = accept(conn, report, source_ns="sheet", actor=WORKER, district_id=imp.district_id, job=False)
            if not acc.replay:
                conn.execute(text(
                    "INSERT INTO evidence (report_id, type, uri, sha256, mime, added_by, meta)"
                    " VALUES (:r, 'sheet_row', :uri, :sha, :mime, :by, CAST(:meta AS jsonb))"),
                    {"r": acc.report_id, "uri": uri_for(imp.file_sha256), "sha": imp.file_sha256,
                     "mime": "text/csv" if imp.file_kind == "csv" else
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     "by": f"import:{imp.id}", "meta": json.dumps({"import_id": imp.id, "file_name": imp.file_name,
                                                                   "row": number, "cells": n["raw"]}, ensure_ascii=False)})
        report = load_report(self.engine, acc.report_id)
        if report.case_id is not None:      # this file (or this row) was imported before
            pid = self._public_id(report.case_id)
            self.record(number, report.id, report.case_id, "already", None,
                        f"Already imported: {pid}", n["flags"])
            return None
        return report

    def finish_row(self, number: int, n: dict, report, p) -> None:
        if DAMAGED in n["flags"]:
            p.fields["flags"] = [*p.fields.get("flags", []), "phone_damaged_by_excel"]
        if OLD in n["flags"]:
            p.fields["flags"] = [*p.fields.get("flags", []), "old_report"]
        read_by = "ai" if p.out.method == "ai" else "rules"

        def on_commit(conn, res):
            flags = list(n["flags"]) + (["needs_location"] if "needs_location" in res.get("flags", []) else [])
            pid, outcome, line = res.get("public_id"), res["outcome"], res.get("line")
            if outcome == "merged":
                self._record(conn, number, report.id, res["case_id"], "merged", read_by, line, flags)
                if n["done"]:
                    conn.execute(text("UPDATE cases SET flags = array_append(flags, 'sheet_says_done')"
                                      " WHERE id = :c AND NOT 'sheet_says_done' = ANY(flags)"), {"c": res["case_id"]})
                return
            if n["done"] and outcome in ("new", "refused"):
                c = conn.execute(text("UPDATE cases SET status = 'closed', flags = array_append(flags, 'closed_from_sheet'),"
                                      " version = version + 1, updated_at = now() WHERE id = :c"
                                      " RETURNING incident_id, district_id"), {"c": res["case_id"]}).one()
                append_event(conn, actor=WORKER, action="case.updated", entity_type="case", entity_id=res["case_id"],
                             incident_id=c.incident_id, district_id=c.district_id, case_id=res["case_id"],
                             data={"why": "the sheet marks this row done: kept as closed history", "status": "closed"})
                self._record(conn, number, report.id, res["case_id"], "history", read_by,
                             f"{pid}: marked done in the sheet, kept as closed history", flags)
                return
            to_check = outcome in ("suggested", "needs_review") or "needs_location" in flags or OLD in flags or n["done"]
            why = line or (f"{pid}: no location, needs a person" if "needs_location" in flags else
                           f"{pid}: {OLD}" if OLD in flags else f"{pid}: the sheet says done, but it matched an open case"
                           if n["done"] else f"New case {pid}")
            self._record(conn, number, report.id, res["case_id"], "to_check" if to_check else "new", read_by, why, flags)

        try:
            commit(self.engine, report, p, on_commit=on_commit)
        except Exception as e:     # never lost: the report is written; the normal pipeline retries it
            with self.engine.begin() as conn:
                enqueue(conn, "report.process", {"report_id": report.id}, LANE, dedupe_key=f"report:{report.id}:process")
                self._record(conn, number, report.id, None, "pending", None,
                             f"processing failed ({type(e).__name__}); queued for a retry", n["flags"])

    # --- bookkeeping -----------------------------------------------------------------------------------------
    def _public_id(self, case_id: int) -> str:
        with self.engine.connect() as c:
            return c.execute(text("SELECT public_id FROM cases WHERE id = :c"), {"c": case_id}).scalar()

    def _record(self, conn, number, report_id, case_id, outcome, read_by, reason, flags) -> None:
        conn.execute(text(
            "INSERT INTO import_rows (import_id, row_number, report_id, case_id, outcome, read_by, reason, flags)"
            " VALUES (:i, :n, :r, :c, :o, :b, :why, :f) ON CONFLICT (import_id, row_number) DO NOTHING"),
            {"i": self.imp.id, "n": number, "r": report_id, "c": case_id, "o": outcome, "b": read_by,
             "why": reason or outcome, "f": flags})

    def record(self, *args) -> None:
        with self.engine.begin() as conn:
            self._record(conn, *args)

    def counts(self, conn) -> dict:
        r = conn.execute(text(
            "SELECT count(*) AS rows_done,"
            " count(*) FILTER (WHERE outcome = 'new') AS new_cases,"
            " count(*) FILTER (WHERE outcome = 'merged') AS merged,"
            " count(*) FILTER (WHERE outcome = 'to_check') AS to_check,"
            " count(*) FILTER (WHERE outcome = 'history') AS history,"
            " count(*) FILTER (WHERE outcome = 'already') AS already,"
            " count(*) FILTER (WHERE outcome = 'dropped') AS dropped,"
            " count(*) FILTER (WHERE outcome = 'pending') AS pending,"
            " count(*) FILTER (WHERE read_by = 'rules') AS rules_read,"
            " count(*) FILTER (WHERE read_by = 'ai') AS ai_asked,"
            " count(*) FILTER (WHERE :damaged = ANY(flags)) AS phones_damaged"
            " FROM import_rows WHERE import_id = :i"), {"i": self.imp.id, "damaged": DAMAGED}).one()
        return dict(r._mapping)

    def progress(self, force: bool = False, final: bool = False) -> dict | None:
        now = time.monotonic()
        if not force and now - self.last_progress < PROGRESS_EVERY_S:
            return None
        self.last_progress = now
        with self.engine.begin() as conn:
            c = self.counts(conn)
            sets = ", ".join(f"{k} = :{k}" for k in c)
            extra = ", status = 'done', finished_at = now(), summary = :summary" if final else ""
            c_summary = summary_line(self.imp.rows_total, c) if final else None
            conn.execute(text(f"UPDATE imports SET {sets}{extra} WHERE id = :i"), {**c, "i": self.imp.id, "summary": c_summary})
            # A long import keeps its job's lease, so it isn't reclaimed while it is still working.
            conn.execute(text("UPDATE jobs SET locked_at = now() WHERE kind = 'import.run' AND locked_by IS NOT NULL"
                              " AND (payload->>'import_id')::bigint = :i"), {"i": self.imp.id})
            append_event(conn, actor=WORKER, action="import.completed" if final else "import.progress",
                         entity_type="import", entity_id=self.imp.id, incident_id=self.imp.incident_id,
                         district_id=self.imp.district_id,
                         data={"import_id": self.imp.id, "rows_total": self.imp.rows_total, **c,
                               **({"summary": c_summary} if final else {})})
        return c


def summary_line(total: int, c: dict) -> str:
    """The line said out loud on stage. Every number is a count of import_rows."""
    parts = [f"{total} rows → {c['new_cases']} new cases", f"{c['merged']} merged", f"{c['to_check']} to check",
             f"{c['dropped']} dropped"]
    if c["history"]:
        parts.append(f"{c['history']} already done (closed history)")
    if c["already"]:
        parts.append(f"{c['already']} already imported")
    if c["pending"]:
        parts.append(f"{c['pending']} still processing")
    parts.append(f"rules read {c['rules_read']}, AI asked about {c['ai_asked']}")
    if c["phones_damaged"]:
        parts.append(f"{c['phones_damaged']} phone numbers damaged by Excel, not used")
    return " · ".join(parts)


@handler("import.run")
def run_import(engine: Engine, payload: dict) -> None:
    iid = payload["import_id"]
    with engine.connect() as hold:
        # One runner per import, even if a slow job's lease were reclaimed (session lock, released on close).
        if not hold.execute(text("SELECT pg_try_advisory_lock(hashtext(:k))"), {"k": f"import:{iid}"}).scalar():
            raise RetryLater(15, "another worker is running this import")
        try:
            _run(engine, iid)
        finally:
            hold.execute(text("SELECT pg_advisory_unlock(hashtext(:k))"), {"k": f"import:{iid}"})
            hold.commit()


def _run(engine: Engine, iid: int) -> None:
    with engine.begin() as conn:
        imp = conn.execute(text("SELECT m.*, i.code AS incident_code FROM imports m JOIN incidents i ON i.id = m.incident_id"
                                " WHERE m.id = :i"), {"i": iid}).one_or_none()
        if imp is None or imp.status == "done":
            return
        conn.execute(text("UPDATE imports SET status = 'running', started_at = coalesce(started_at, now()) WHERE id = :i"),
                     {"i": iid})
        finished = {r[0] for r in conn.execute(text("SELECT row_number FROM import_rows WHERE import_id = :i"), {"i": iid})}
    sheet = read(imp.file_name, path_for(imp.file_sha256).read_bytes())
    mapping = dict(imp.mapping)
    run = Run(engine, imp)
    run.progress(force=True)
    deferred = []
    for number, cells in zip(sheet.numbers, sheet.rows, strict=True):
        if number in finished:
            continue
        n = normalise_row(cells, sheet.headers, mapping, imp.created_at.astimezone(UTC))
        report = run.write(number, n)
        if report is not None:
            p = prepare(engine, report, allow_model=False, rules_why="spreadsheet row, rules first", adjust=columns(n))
            if needs_model(p) and llm_extract.could_ask(report.text or ""):
                deferred.append((number, n, report.id))
            else:
                run.finish_row(number, n, report, p)
        run.progress()
    # Step 4b: rows the rules couldn't read, to the language model in batches of 20, one batch at a time.
    for start in range(0, len(deferred), BATCH):
        for number, n, report_id in deferred[start:start + BATCH]:
            report = load_report(engine, report_id)
            if report.case_id is not None:
                continue
            run.finish_row(number, n, report, prepare(engine, report, allow_model=True, adjust=columns(n)))
        run.progress(force=True)
    run.progress(force=True, final=True)
