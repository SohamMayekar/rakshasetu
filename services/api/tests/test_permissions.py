"""PRD §4.2, one test per row. Two layers:

1. `roles.yaml` must encode the §4.2 matrix exactly (transcribed below from the PRD).
2. Each row is exercised through its real endpoint for an allowed and a denied role. Rows whose endpoint
   doesn't exist yet are SKIPPED with the milestone that builds them, so the gap stays visible
   (all must run and pass by m53).
"""

import pytest

from app.config import get_bundle
from tests.conftest import login, needs_db

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
    ("case.status_public", "GET", "/v1/public/cases/BR-151/status", None, None, None, "m21"),
    ("totals.view", "GET", "/v1/metrics/promises?incident=BR", None, "seoc", "boat5", "m47"),
    ("case.check", "POST", "/v1/cases/BR-151/check", {}, "priya", "boat5", "m24"),
    ("case.move_pin", "PATCH", "/v1/cases/BR-151/location", {}, "priya", "rdas_denied", "m24"),
    ("merge.decide", "POST", "/v1/merges", {}, "priya", "boat5", "m28"),
    ("import.run", "POST", "/v1/imports", {}, "priya", "boat5", "m29"),
    ("assignment.create", "POST", "/v1/assignments", {}, "rdas", "priya", "m40"),
    ("assignment.team_action", "POST", "/v1/assignments/1/acknowledge", {}, "boat5", "priya", "m40"),
    ("team.radio_contact", "POST", "/v1/teams/1/contact", {}, "rdas", "priya", "m42"),
    ("rescue.family_confirm", "POST", "/v1/public/cases/BR-151/confirm", {}, None, None, "m46"),
    ("case.decide", "POST", "/v1/cases/BR-151/close", {}, "rdas", "priya", "m45"),
    ("escalation.ack", "POST", "/v1/escalations/1/ack", {}, "rdas", "priya", "m41"),
    ("incident.admin", "POST", "/v1/incidents", {}, "admin", "rdas", "m48"),
    ("priority.override", "POST", "/v1/cases/BR-151/priority", {}, "rdas", "priya", "m57"),
    ("phone.reveal", "POST", "/v1/cases/BR-151/reveal-contact", {}, "priya", "seoc", "m57"),
    ("partner.annotate", "POST", "/v1/partners/annotations", {}, None, None, "m58"),
]


PARAMS = [pytest.param(*e, id=e[0], marks=pytest.mark.skip(reason=f"endpoint arrives in {e[6]}") if e[6] else ())
          for e in ENDPOINTS]


@pytest.mark.parametrize("action,method,path,body,allowed,denied,built_in", PARAMS)
def test_each_row_through_its_endpoint(seeded, client, action, method, path, body, allowed, denied, built_in):
    login(client, denied)
    r = client.request(method, path, json=body)
    assert r.status_code == 403, f"{denied} should be refused {action}: {r.status_code} {r.text}"
    login(client, allowed)
    r = client.request(method, path, json=body)
    assert r.status_code < 400, f"{allowed} should be allowed {action}: {r.status_code} {r.text}"


def test_every_action_in_the_matrix_has_an_endpoint_check():
    checked = {e[0] for e in ENDPOINTS} | {"phone.view_masked", "case.edit"}   # covered by case detail / m24
    assert checked == set(PRD_MATRIX)
