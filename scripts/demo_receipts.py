"""The receipts of `scripts/demo_live.sh`: which reports a live provider read, and which the word rules did.

Read-only SQL over reports.receipt and cases.provenance (the app role selects both; no app imports, no
provider calls). Seeded reports — read by the rules at seed time, never by a model — are left out, so what
is left is what the demonstration itself just did.

    source native/env.sh && services/api/.venv/bin/python scripts/demo_receipts.py [--minutes 30] [--limit 8]
"""

import argparse
import os
import sys
from collections import Counter

import psycopg

READ_STEPS = ("stt", "extract", "quotes", "backfill")
LABELS = {"ai": "the model", "rules": "the word rules", "rule": "the word rules",
          "structured": "the partner", "partner": "the partner", "human": "a person"}


def connect() -> psycopg.Connection:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        sys.exit("DATABASE_URL is not set: source native/env.sh first")
    return psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"))


def print_reports(cur: psycopg.Cursor, minutes: int, limit: int) -> None:
    rows = cur.execute(
        """
        SELECT r.id, i.code, r.channel, c.public_id, r.receipt
        FROM reports r
        JOIN incidents i ON i.id = r.incident_id
        LEFT JOIN cases c ON c.id = r.case_id
        WHERE r.received_at > now() - make_interval(mins => %(m)s)
          AND r.extraction_method IS NOT NULL
          AND jsonb_typeof(r.receipt) = 'array' AND jsonb_array_length(r.receipt) > 0
          AND coalesce(r.receipt::text, '') NOT LIKE '%%seeded report%%'
          AND r.channel IN ('voice', 'web_form')
        ORDER BY r.id DESC LIMIT %(n)s
        """, {"m": minutes, "n": limit}).fetchall()
    if not rows:
        print("no voice or typed reports in the last %d minutes — did the reset run?" % minutes)
        return
    print("== receipts: the demonstration's reports, oldest first ==")
    for rid, code, channel, public_id, receipt in reversed(rows):
        print(f"  #{rid} {channel} ({code}) → {public_id or 'no case yet'}")
        for step in receipt:
            if step.get("step") in READ_STEPS:
                print(f"      {step['step']:<8} {step.get('by', ''):<6} {step.get('detail', '')}")


def tally(cur: psycopg.Cursor, minutes: int, extra: str = "") -> list[tuple[str, int]]:
    return cur.execute(
        f"""
        SELECT r.extraction_method, count(*) FROM reports r
        WHERE r.received_at > now() - make_interval(mins => %(m)s)
          AND r.extraction_method IS NOT NULL
          AND coalesce(r.receipt::text, '') NOT LIKE '%%seeded report%%'
          {extra}
        GROUP BY 1 ORDER BY 2 DESC
        """, {"m": minutes}).fetchall()


def label(pairs: list[tuple[str, int]]) -> str:
    return " · ".join(f"{LABELS.get(method, method)} {n}" for method, n in pairs)


def print_case(cur: psycopg.Cursor, minutes: int, wanted: str | None = None) -> None:
    if wanted:
        row = cur.execute(
            "SELECT c.public_id, c.provenance, i.code FROM cases c JOIN incidents i ON i.id = c.incident_id"
            " WHERE c.public_id = %(p)s", {"p": wanted}).fetchone()
    else:
        row = cur.execute(
            """
            SELECT c.public_id, c.provenance, i.code
            FROM reports r JOIN cases c ON c.id = r.case_id JOIN incidents i ON i.id = c.incident_id
            WHERE r.received_at > now() - make_interval(mins => %(m)s) AND r.channel = 'voice'
              AND c.status <> 'merged'
            ORDER BY r.id DESC LIMIT 1
            """, {"m": minutes}).fetchone()
    if not row:
        return
    public_id, provenance, code = row
    per_field, methods = [], Counter()
    for field, entries in sorted((provenance or {}).items()):
        entries = [entries] if isinstance(entries, dict) else entries
        got = [e.get("method") for e in entries if isinstance(e, dict) and e.get("method")]
        if got:
            per_field.append(f"{field}={','.join(got)}")
            methods.update(got)
    print(f"\nthe demo case {public_id}: facts read by "
          f"{label(sorted(methods.items(), key=lambda kv: -kv[1])) or 'nobody yet'}")
    if per_field:
        print("  " + "  ·  ".join(per_field))
    print(f"  open it: /desk/{code}?case={public_id}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minutes", type=int, default=30, help="look back over reports from the last N minutes")
    ap.add_argument("--limit", type=int, default=8, help="how many voice/typed reports to show")
    ap.add_argument("--case", help="the demo's case (the runner passes the son's case; without it, the newest "
                                   "voice report's case is shown, which a caller testing at the same time can steal)")
    args = ap.parse_args()
    with connect() as conn, conn.cursor() as cur:
        print_reports(cur, args.minutes, args.limit)
        sheet = tally(cur, args.minutes, "AND r.channel = 'spreadsheet'")
        if sheet:
            print(f"\nsheet rows: {label(sheet)}")
        total = tally(cur, args.minutes)
        if total:
            print(f"all reports this run: {label(total)}")
        print_case(cur, args.minutes, args.case)
    return 0


if __name__ == "__main__":
    sys.exit(main())
