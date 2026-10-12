"""The 300-row demo sheet against its ground truth (PRD F-D3 "done when"; data/scenarios/BR/sheet/).

Measures, and prints with `make sheet-eval`: time to import, each row's outcome against what the generator
says it should be, pairwise precision/recall of the automatic merges, and how many rows the rules read.
"""

import csv
import itertools
from collections import Counter

import pytest

from app.core.jobs import drain
from app.pipeline import register_handlers
from app.settings import get_settings
from tests.conftest import login, needs_db, one, rows

pytestmark = [needs_db, pytest.mark.scenario, pytest.mark.slow]


def _truth() -> dict[int, dict]:
    path = get_settings().data_dir / "scenarios" / "BR" / "sheet" / "ground_truth.csv"
    return {int(r["row"]): r for r in csv.DictReader(path.open(encoding="utf-8"))}


def test_the_demo_sheet_imports_within_45_s_and_matches_its_ground_truth(seeded, client, app_db):
    register_handlers()
    truth = _truth()
    data = (get_settings().data_dir / "scenarios" / "BR" / "sheet" / "volunteer_sheet.csv").read_bytes()
    login(client, "priya")
    imp = client.post("/v1/imports", files={"file": ("volunteer_sheet.csv", data, "text/csv")},
                      data={"incident": "BR"}).json()
    assert imp["proposed"] == {"S.No": "ignore", "Name": "name", "Mobile No": "phone", "No. of people": "headcount",
                               "Village": "village", "Location/Landmark": "location", "Remarks": "notes", "Time": "time",
                               "Status": "status", "Volunteer": "ignore"}
    client.post(f"/v1/imports/{imp['id']}/mapping", json={"mapping": imp["proposed"]})
    drain(app_db)
    imp = client.get(f"/v1/imports/{imp['id']}").json()
    seconds = one(app_db, "SELECT extract(epoch FROM finished_at - started_at) FROM imports WHERE id = :i", i=imp["id"])
    got = {r["row_number"]: r for r in client.get(f"/v1/imports/{imp['id']}/rows").json()}
    case_of = {r.row: r.case_id for r in rows(app_db, (
        "SELECT (e.meta->>'row')::int AS row, r.case_id FROM evidence e JOIN reports r ON r.id = e.report_id"
        " WHERE e.type = 'sheet_row' AND e.sha256 = :s"), s=imp["file_sha256"])}

    # Each row's outcome against the generator's expectation.
    confusion = Counter((truth[n]["expect"], got[n]["outcome"]) for n in truth)
    agree = sum(v for (want, have), v in confusion.items() if want == have)
    # Pairwise, over rows of the same household vs rows that ended in the same case.
    pairs = list(itertools.combinations(sorted(truth), 2))
    same_truth = {p for p in pairs if truth[p[0]]["household"] == truth[p[1]]["household"]}
    same_case = {p for p in pairs if case_of.get(p[0]) and case_of.get(p[0]) == case_of.get(p[1])}
    tp = len(same_truth & same_case)
    precision = tp / len(same_case) if same_case else 1.0
    recall = tp / len(same_truth)
    damaged_rows = [n for n in truth if truth[n]["phone_damaged"] == "True"]

    print(f"\n  summary: {imp['summary']}\n  import took {seconds:.1f} s for {imp['rows_total']} rows"
          f"\n  outcome agrees with ground truth on {agree}/{len(truth)} rows; disagreements:"
          f" {sorted((k, v) for k, v in confusion.items() if k[0] != k[1])}"
          f"\n  automatic merges: precision {precision:.3f}, recall {recall:.3f} ({tp} of {len(same_truth)} same-household"
          f" pairs; {len(same_case) - tp} wrong)")

    assert imp["status"] == "done" and imp["rows_total"] == 300
    assert seconds <= 45                                                       # PRD: ≤ 45 s
    assert precision == 1.0                                                    # never a wrong automatic merge
    assert agree == len(truth), sorted((n, truth[n]["expect"], got[n]["outcome"], got[n]["reason"])
                                       for n in truth if truth[n]["expect"] != got[n]["outcome"])
    assert imp["phones_damaged"] == 14 and len(damaged_rows) == 14
    assert not any(case_of[n] == case_of[m] for n in damaged_rows for m in truth if m != n)   # T5 on the real sheet
    assert imp["rules_read"] + imp["ai_asked"] == imp["rows_total"] - imp["dropped"]
    assert imp["rules_read"] >= 0.9 * imp["rows_total"] or imp["ai_asked"] <= 0.1 * imp["rows_total"]
    das = [n for n in truth if truth[n]["kind"] == "das_pair"]
    assert len({case_of[n] for n in das}) == 2                                # Ramesh ≠ Rajesh
    relay = [n for n in truth if truth[n]["relay_phone"] == "True"]
    assert len({case_of[n] for n in relay}) == len(relay)                     # the volunteer's phone isn't identity
