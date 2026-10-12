"""PRD §4.2, one test per row. Two layers:

1. `roles.yaml` must encode the §4.2 matrix exactly (transcribed below from the PRD).
2. Each row is exercised through its real endpoint for an allowed and a denied role. Rows whose endpoint
   doesn't exist yet are SKIPPED with the milestone that builds them, so the gap stays visible
   (all must run and pass by m53).
"""

import pytest

from app.config import get_bundle
from tests.conftest import login, needs_db, rows

pytestmark = needs_db

R, CT, DO, IC, TL, SV, AD, PA = "reporter", "call_taker", "duty_officer", "incharge", "team_lead", "seoc_viewer", "admin", "partner"

# PRD §4.2, row by row: action -> roles allowed (own/assigned scoping is tested separately as IDOR).
PRD_MATRIX = {
    "report.submit":          {R, CT, DO, IC, TL, AD, PA},
    "case.status_public":     {R, CT, DO, IC, TL, SV, AD},
    "queue.view":             {CT, DO, IC, TL, AD},
    "totals.view":            {CT, DO, IC, SV, AD},
    "phone.view_masked":      {CT, DO, IC, TL, AD},
    "phone.reveal":           {CT, DO, IC, TL},
    "case.check":             {CT, DO, IC},
    "case.edit":              {CT, DO, IC},
    "case.move_pin":          {CT, DO, IC},
    "merge.decide":           {CT, DO, IC},
    "import.run":             {CT, DO, IC, AD},
    "assignment.create":      {DO, IC},
    "assignment.team_action": {DO, IC, TL},
    "team.radio_contact":     {DO, IC},
    "rescue.family_confirm":  {R},
    "case.decide":            {DO, IC},
    "priority.override":      {DO, IC},
    "escalation.ack":         {DO, IC},
    "incident.admin":         {AD},
    "audit.read":             {DO, IC, AD},
    "partner.annotate":       {PA},
}


def test_roles_yaml_encodes_the_prd_matrix_exactly():
    perms = get_bundle().roles.permissions
    assert set(perms) == set(PRD_MATRIX), "an action was added or dropped"
    for action, roles in PRD_MATRIX.items():
        assert set(perms[action]) == roles, action


# Endpoint checks: (action, method, path, json, allowed_user, denied_user, built_in)
# built_in = None means the endpoint exists now; otherwise the milestone that adds it.
ENDPOINTS = [
    ("queue.view", "GET", "/v1/cases?incident=BR", None, "priya", "seoc", None),
    ("audit.read", "GET", "/v1/audit/verify", None, "rdas", "priya", None),
    ("report.submit", "POST", "/v1/ingest/desk", {"incident": "BR", "text": "6 log chhat par", "client_id": "perm-0001"},
     "priya", "seoc", None),
    # case.status_public: anyone with the case number, no login (tests/test_status_page.py).
    ("totals.view", "GET", "/v1/metrics/promises?incident=BR", None, "seoc", "boat5", "m47"),
    ("case.check", "POST", "/v1/cases/BR-151/check", {}, "priya", "seoc", None),
    ("case.move_pin", "PATCH", "/v1/cases/BR-151/location", {"lat": 26.44, "lng": 84.40, "reason": "caller confirmed"},
     "priya", "seoc", None),
    ("merge.decide", "POST", "/v1/merges",
     lambda db: {"cases": [r[0] for r in rows(db, "SELECT public_id FROM cases WHERE district_id = (SELECT id FROM districts"
                                                  " WHERE name = 'Gopalganj') AND status = 'reported' ORDER BY id LIMIT 2")],
                 "reason": "same family, confirmed by phone"},
     "priya", "seoc", None),
    ("import.run", "POST", "/v1/imports",
     {"files": {"file": ("s.csv", b"Naam,Mob,Gaon\nSita,9876543210,Thawe\n", "text/csv")}, "data": {"incident": "BR"}},
     "priya", "boat5", None),
    ("assignment.create", "POST", "/v1/assignments",
     lambda db: {"case": _unowned_gopalganj_case(db), "team_id": _team(db, "Fire & Rescue Boat 5")}, "rdas", "priya", None),
    ("assignment.team_action", "POST", lambda db: f"/v1/assignments/{_boat5_assignment(db)}/acknowledge", {"eta_minutes": 30},
     "boat5", "priya", None),
    ("team.radio_contact", "POST", lambda db: f"/v1/teams/{_team(db, 'SDRF Boat 2')}/contact", {"channel": "VHF"},
     "rdas", "priya", None),
    ("case.decide", "POST", lambda db: f"/v1/cases/{_unowned_gopalganj_case(db)}/close", {"reason": "duplicate call, verified"},
     "rdas", "priya", None),
    ("escalation.ack", "POST", lambda db: f"/v1/escalations/{_escalation(db)}/ack", {}, "rdas", "priya", None),
    ("incident.admin", "POST", "/v1/incidents", {}, "admin", "rdas", "m48"),
    ("priority.override", "POST", "/v1/cases/BR-151/priority", {}, "rdas", "priya", "m57"),
    ("phone.reveal", "POST", lambda db: f"/v1/cases/{_case_with_phone(db)}/reveal-contact", {"reason": "calling back"},
     "priya", "seoc", None),
    ("partner.annotate", "POST", "/v1/partners/annotations", {}, None, None, "m58"),
]


def _unowned_gopalganj_case(db):
    return rows(db, "SELECT c.public_id FROM cases c JOIN districts d ON d.id = c.district_id WHERE d.name = 'Gopalganj'"
                    " AND c.status IN ('reported', 'checked') AND NOT EXISTS (SELECT 1 FROM assignments a"
                    " WHERE a.case_id = c.id AND a.state IN ('open', 'overdue')) ORDER BY c.id LIMIT 1")[0][0]


def _case_with_phone(db):
    return rows(db, "SELECT c.public_id FROM cases c JOIN reports r ON r.case_id = c.id JOIN districts d ON d.id = c.district_id"
                    " WHERE d.name = 'Gopalganj' AND r.reporter_phone_enc IS NOT NULL ORDER BY c.id LIMIT 1")[0][0]


def _team(db, name):
    return rows(db, "SELECT id FROM teams WHERE name = :n", n=name)[0][0]


def _escalation(db):
    from sqlalchemy import text
    with db.begin() as c:
        return c.execute(text("INSERT INTO escalations (incident_id, district_id, kind, team_id, line) SELECT t.incident_id,"
                              " t.district_id, 'team_overdue', t.id, 'test' FROM teams t WHERE t.name = 'SDRF Boat 2'"
                              " RETURNING id")).scalar()


def _boat5_assignment(db):
    from sqlalchemy import text
    with db.begin() as c:
        cid = c.execute(text("SELECT id FROM cases WHERE public_id = :p"), {"p": _unowned_gopalganj_case(db)}).scalar()
        return c.execute(text("INSERT INTO assignments (case_id, team_id, next_contact_due) VALUES (:c, :t, now() + interval"
                              " '5 minutes') RETURNING id"), {"c": cid, "t": _team(db, "Fire & Rescue Boat 5")}).scalar()


PARAMS = [pytest.param(*e, id=e[0], marks=pytest.mark.skip(reason=f"endpoint arrives in {e[6]}") if e[6] else ())
          for e in ENDPOINTS]


@pytest.mark.parametrize("action,method,path,body,allowed,denied,built_in", PARAMS)
def test_each_row_through_its_endpoint(seeded, client, app_db, action, method, path, body, allowed, denied, built_in):
    if callable(path):
        path = path(app_db)
    if callable(body):
        body = body(app_db)
    send = ({"files": body["files"], "data": body["data"]} if isinstance(body, dict) and "files" in body
            else {"json": body})
    login(client, denied)
    r = client.request(method, path, **send)
    assert r.status_code == 403, f"{denied} should be refused {action}: {r.status_code} {r.text}"
    login(client, allowed)
    r = client.request(method, path, **send)
    assert r.status_code < 400, f"{allowed} should be allowed {action}: {r.status_code} {r.text}"


def test_every_action_in_the_matrix_has_an_endpoint_check():
    checked = {e[0] for e in ENDPOINTS} | {"phone.view_masked", "case.edit",   # case detail / test_case_edits.py
                                           "case.status_public",             # test_status_page.py
                                           "rescue.family_confirm"}          # linked device only: scenarios/test_t9
    assert checked == set(PRD_MATRIX)
