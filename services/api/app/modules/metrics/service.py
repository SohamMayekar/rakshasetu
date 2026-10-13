"""The promise bar (PRD F-C6) and the integrity check: every number is one query, and the funnel adds up.

    Never lost   · provenance       reports = cases + merged + to check + without a home   · oldest waiting
    Never doubled · uncertainty     merged · to check · refused
    Never stale  · responsibility   P1 without an owner > 5 min · contact overdue

Funnel, over the incident's reports (each report is in exactly one bucket, so the sum is exact by construction):
    case            the first report of each case it now belongs to (distinct case per report)
    merged          every further report folded into a case that already had one
    to check        a report nobody could read into a case (needs review: e.g. no incident)
    without a home  a report still in the pipeline (no case yet); "never lost" is broken if one waits > 2 min
A number "breaks" (the desk shows it inverted) only when its promise is broken, never because it is large.
"""

from datetime import UTC, datetime

from sqlalchemy import Connection, text

from app.config import get_config, parse_duration
from app.core.auth import Scope

HOMELESS_AFTER_S = 120          # a report still without a case after 2 minutes breaks "never lost"
DUPLICATE_WAIT_S = 15 * 60      # a likely duplicate nobody decided for 15 minutes breaks "never doubled"


def _districts(conn: Connection, scope: Scope, incident_id: int) -> list[int] | None:
    """None = every district of the incident (SEOC viewer, admin); else the desk's own districts."""
    if scope.role in ("admin", "seoc_viewer"):
        return None
    return list(scope.district_ids)


def promises(conn: Connection, scope: Scope, incident_code: str) -> dict | None:
    inc = conn.execute(text("SELECT id FROM incidents WHERE code = :c"), {"c": incident_code}).scalar()
    if inc is None or (scope.role != "admin" and inc not in scope.incident_ids):
        return None
    d = _districts(conn, scope, inc)
    p = {"i": inc, "d": d, "all": d is None, "homeless": HOMELESS_AFTER_S, "dup": DUPLICATE_WAIT_S,
         "p1": parse_duration(get_config().escalation.get("p1_unowned_after", "5m")).total_seconds()}
    in_scope_case = "(:all OR c.district_id = ANY(CAST(:d AS bigint[])))"
    funnel = conn.execute(text("""
        WITH r AS (
          SELECT r.id, r.case_id, r.status, r.received_at, c.district_id,
                 row_number() OVER (PARTITION BY r.case_id ORDER BY r.received_at, r.id) AS nth
            FROM reports r LEFT JOIN cases c ON c.id = r.case_id
           WHERE r.incident_id = :i
             AND (:all OR c.district_id = ANY(CAST(:d AS bigint[]))
                  OR (r.case_id IS NULL AND (r.source->>'district_hint' IS NULL
                      OR CAST(r.source->>'district_hint' AS bigint) = ANY(CAST(:d AS bigint[]))))))
        SELECT count(*) AS reports,
               count(*) FILTER (WHERE case_id IS NOT NULL AND nth = 1) AS cases,
               count(*) FILTER (WHERE case_id IS NOT NULL AND nth > 1) AS merged_reports,
               count(*) FILTER (WHERE case_id IS NULL AND status = 'needs_review') AS to_check,
               count(*) FILTER (WHERE case_id IS NULL AND status <> 'needs_review') AS without_home,
               min(received_at) FILTER (WHERE case_id IS NULL AND status <> 'needs_review') AS oldest_waiting,
               count(*) FILTER (WHERE case_id IS NULL AND status <> 'needs_review'
                                AND received_at < now() - make_interval(secs => :homeless)) AS homeless_late
          FROM r"""), p).one()
    doubled = conn.execute(text(f"""
        SELECT (SELECT count(*) FROM merges m JOIN cases c ON c.id = m.target_case_id
                 WHERE m.incident_id = :i AND m.undone_at IS NULL AND {in_scope_case}) AS merged,
               count(*) FILTER (WHERE s.strength <> 'refused') AS to_check,
               count(*) FILTER (WHERE s.strength = 'refused') AS refused,
               count(*) FILTER (WHERE s.strength <> 'refused' AND s.created_at < now() - make_interval(secs => :dup)) AS late
          FROM merge_suggestions s JOIN cases c ON c.id = s.case_id
         WHERE s.incident_id = :i AND s.status = 'open' AND {in_scope_case}"""), p).one()
    stale = conn.execute(text(f"""
        SELECT count(*) FILTER (WHERE c.priority = 'P1' AND c.status IN ('reported', 'checked')
                                AND c.queue_since < now() - make_interval(secs => :p1)
                                AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.case_id = c.id
                                                AND a.state IN ('open', 'overdue'))) AS p1_unowned,
               (SELECT count(*) FROM assignments a JOIN cases k ON k.id = a.case_id
                 WHERE a.state = 'overdue' AND k.incident_id = :i
                   AND (:all OR k.district_id = ANY(CAST(:d AS bigint[])))) AS overdue,
               count(*) FILTER (WHERE c.status IN ('assigned', 'acknowledged', 'reached')) AS owned
          FROM cases c WHERE c.incident_id = :i AND {in_scope_case}"""), p).one()
    now = datetime.now(UTC)
    oldest = funnel.oldest_waiting
    return {
        "incident": incident_code, "at": now.isoformat(),
        "lost": {"reports": funnel.reports, "cases": funnel.cases, "merged": funnel.merged_reports,
                 "to_check": funnel.to_check, "without_home": funnel.without_home,
                 "oldest_waiting_s": int((now - oldest).total_seconds()) if oldest else None,
                 "adds_up": funnel.reports == funnel.cases + funnel.merged_reports + funnel.to_check + funnel.without_home,
                 "broken": funnel.homeless_late > 0},
        "doubled": {"merged": doubled.merged, "to_check": doubled.to_check, "refused": doubled.refused,
                    "broken": doubled.late > 0},
        "stale": {"p1_unowned": stale.p1_unowned, "overdue": stale.overdue, "owned": stale.owned,
                  "broken": stale.p1_unowned > 0 or stale.overdue > 0},
    }


def promises_all(conn: Connection, scope: Scope) -> dict:
    """The national bar: the three promises added up over every incident this person may see. A number breaks
    when it breaks anywhere, and the funnel still adds up because each incident's funnel does."""
    codes = [r[0] for r in conn.execute(text("SELECT code FROM incidents ORDER BY id"))]
    parts = [p for c in codes if (p := promises(conn, scope, c)) is not None]
    total = {"lost": {"reports": 0, "cases": 0, "merged": 0, "to_check": 0, "without_home": 0, "oldest_waiting_s": None,
                      "adds_up": True, "broken": False},
             "doubled": {"merged": 0, "to_check": 0, "refused": 0, "broken": False},
             "stale": {"p1_unowned": 0, "overdue": 0, "owned": 0, "broken": False}}
    for p in parts:
        for group, fields in total.items():
            for k, v in p[group].items():
                if k == "oldest_waiting_s":
                    if v is not None:
                        fields[k] = v if fields[k] is None else max(fields[k], v)
                elif k == "adds_up":
                    fields[k] = fields[k] and v
                elif k == "broken":
                    fields[k] = fields[k] or v
                else:
                    fields[k] += v
    return {"incident": None, "at": datetime.now(UTC).isoformat(), **total}


def integrity(conn: Connection) -> dict:
    """Invariants that must hold at any moment (PRD §13: "every rehearsal ends with Verify ✓ and integrity = 0").
    Each problem is named with what it found; 0 problems is the bar."""
    from app.core.eventlog import verify_chain
    from app.core.storage import rehash
    problems: list[str] = []

    def check(sql: str, what: str) -> None:
        n = conn.execute(text(sql)).scalar()
        if n:
            problems.append(f"{n} {what}")

    check("SELECT count(*) FROM reports WHERE case_id IS NULL AND status NOT IN ('needs_review')"
          " AND received_at < now() - interval '2 minutes'", "report(s) without a case after 2 minutes")
    check("SELECT count(*) FROM cases c WHERE c.status <> 'merged' AND NOT EXISTS (SELECT 1 FROM reports r WHERE r.case_id = c.id)",
          "live case(s) with no report")
    check("SELECT count(*) FROM cases WHERE status = 'merged' AND parent_case_id IS NULL", "merged case(s) with no target")
    check("SELECT count(*) FROM cases c WHERE c.status IN ('assigned', 'acknowledged', 'reached') AND NOT EXISTS"
          " (SELECT 1 FROM assignments a WHERE a.case_id = c.id AND a.state IN ('open', 'overdue'))",
          "case(s) marked as owned with no live assignment")
    check("SELECT count(*) FROM assignments a JOIN cases c ON c.id = a.case_id WHERE a.state IN ('open', 'overdue')"
          " AND c.status NOT IN ('assigned', 'acknowledged', 'reached', 'reported', 'checked')",
          "live assignment(s) on a case that isn't open")
    check("SELECT count(*) FROM (SELECT case_id FROM assignments WHERE state IN ('open', 'overdue') GROUP BY case_id"
          " HAVING count(*) > 1) x", "case(s) with two live owners")
    check("SELECT count(*) FROM jobs WHERE dead_at IS NOT NULL", "dead job(s)")
    for sha in [r[0] for r in conn.execute(text("SELECT DISTINCT sha256 FROM evidence WHERE uri IS NOT NULL"))]:
        if not rehash(sha):
            problems.append(f"evidence file {sha[:12]}… no longer matches its hash")
    chain = verify_chain(conn)
    if not chain.get("ok"):
        problems.append(f"audit chain broken at seq {chain.get('broken_at')}")
    return {"problems": len(problems), "details": problems, "events_verified": chain.get("count")}
