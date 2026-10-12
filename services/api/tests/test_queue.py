""""Needs you now" (PRD F-C2): attention rows only, one ordering rule, one chip, one action per role."""

from sqlalchemy import text

from tests.conftest import login, needs_db, one

pytestmark = [needs_db]


def _q(client, who="priya"):
    login(client, who)
    r = client.get("/v1/queue?incident=BR")
    assert r.status_code == 200, r.text
    return r.json()


def _sql(db, sql, **p):
    with db.begin() as c:
        c.execute(text(sql), p)


def _gopalganj_case(db, where="TRUE"):
    return one(db, "SELECT c.id FROM cases c JOIN districts d ON d.id = c.district_id WHERE d.name = 'Gopalganj'"
                   f" AND c.status IN ('reported', 'checked') AND {where} ORDER BY c.id LIMIT 1")


def _team(db):
    return one(db, "SELECT t.id FROM teams t JOIN districts d ON d.id = t.district_id WHERE d.name = 'Gopalganj' LIMIT 1")


def test_the_queue_is_ordered_by_priority_then_broken_promises_then_the_p1_order(seeded, client):
    q = _q(client)
    keys = [r["sort"] for r in q["rows"]]
    assert keys == sorted(keys) and q["rows"]
    pri = [r["priority"] for r in q["rows"]]
    assert pri == sorted(pri)                                       # P1 rows first
    p1 = [r for r in q["rows"] if r["priority"] == "P1"]
    broken = [r["broken"] for r in p1]
    assert broken == sorted(broken, reverse=True)                   # broken promises before new work
    assert all(r["line1"] and r["line2"] for r in q["rows"])        # a two-line summary on every row


def test_a_healthy_owned_case_leaves_the_queue_and_counts_as_on_it(seeded, client, app_db):
    cid = _gopalganj_case(app_db, "c.status = 'checked' AND 'needs_location' <> ALL(c.flags)")
    before = _q(client)
    assert cid in [r["id"] for r in before["rows"]]
    _sql(app_db, "UPDATE cases SET status = 'assigned' WHERE id = :c", c=cid)
    _sql(app_db, "INSERT INTO assignments (case_id, team_id, next_contact_due) VALUES (:c, :t, now() + interval '20 minutes')",
         c=cid, t=_team(app_db))
    after = _q(client)
    assert cid not in [r["id"] for r in after["rows"]]
    assert after["on_it"] == before["on_it"] + 1


def test_contact_overdue_is_the_chip_and_puts_the_row_first_in_its_priority(seeded, client, app_db):
    cid = _gopalganj_case(app_db, "c.status = 'checked'")
    _sql(app_db, "UPDATE cases SET status = 'acknowledged' WHERE id = :c", c=cid)
    _sql(app_db, "INSERT INTO assignments (case_id, team_id, phase, next_contact_due) VALUES (:c, :t, 'acknowledged',"
                 " now() - interval '190 seconds')", c=cid, t=_team(app_db))
    rows = _q(client, "rdas")["rows"]
    row = next(r for r in rows if r["id"] == cid)
    assert row["chip"].startswith("contact overdue 3:1") and row["broken"]
    assert row["action"] == {"kind": "radio", "label": "Heard on radio"}       # an officer's action
    same = [r for r in rows if r["priority"] == row["priority"]]
    assert same.index(row) < len([r for r in same if r["broken"]])           # among the broken, before new work
    assert next(r for r in _q(client, "priya")["rows"] if r["id"] == cid)["action"]["kind"] != "radio"   # call-taker can't


def test_one_chip_ranked_needs_location_over_unchecked_p1(seeded, client, app_db):
    cid = _gopalganj_case(app_db, "c.status = 'reported'")
    _sql(app_db, "UPDATE cases SET priority = 'P1', queue_since = now(), flags = array_append(flags, 'needs_location')"
                 " WHERE id = :c", c=cid)
    row = next(r for r in _q(client)["rows"] if r["id"] == cid)
    assert row["chip"] == "needs location"
    assert row["action"]["kind"] == "pin"
    _sql(app_db, "UPDATE cases SET flags = array_remove(flags, 'needs_location') WHERE id = :c", c=cid)
    row = next(r for r in _q(client)["rows"] if r["id"] == cid)
    assert row["chip"] == "unchecked P1"
    assert row["action"] == {"kind": "check", "label": "Check"}                # the call-taker's next step
    row = next(r for r in _q(client, "rdas")["rows"] if r["id"] == cid)
    assert row["action"]["kind"] == "assign"                                  # the officer's: P1 is assigned before the check


def test_a_p1_without_an_owner_past_5_minutes_is_a_broken_promise(seeded, client, app_db):
    cid = _gopalganj_case(app_db, "c.status = 'checked'")
    _sql(app_db, "UPDATE cases SET priority = 'P1', p1_rank = 4, queue_since = now() - interval '12 minutes' WHERE id = :c", c=cid)
    row = next(r for r in _q(client, "rdas")["rows"] if r["id"] == cid)
    assert row["chip"] == "no owner 12 min" and row["broken"]
    assert row["action"]["kind"] == "assign" and row["action"]["label"].startswith("Assign → ")
    _sql(app_db, "UPDATE cases SET queue_since = now() - interval '2 minutes' WHERE id = :c", c=cid)
    row = next(r for r in _q(client, "rdas")["rows"] if r["id"] == cid)
    assert not row["broken"]                                                  # new work, not yet a broken promise


def test_a_possible_duplicate_offers_the_match(seeded, client, app_db):
    a, b = (one(app_db, "SELECT c.id FROM cases c JOIN districts d ON d.id = c.district_id WHERE d.name = 'Gopalganj'"
                        f" AND c.status = 'checked' AND 'needs_location' <> ALL(c.flags) ORDER BY c.id {o} LIMIT 1")
            for o in ("ASC", "DESC"))
    pid_b = one(app_db, "SELECT public_id FROM cases WHERE id = :b", b=b)
    _sql(app_db, "INSERT INTO merge_suggestions (incident_id, case_id, candidate_case_id, score, strength, reasons, conflicts,"
                 " signals) SELECT incident_id, :a, :b, 0.7, 'strong', '{same village}', '{}', '{}' FROM cases WHERE id = :a", a=a, b=b)
    row = next(r for r in _q(client)["rows"] if r["id"] == a)
    assert row["action"] == {"kind": "match", "label": f"Review match → {pid_b}", "target": pid_b}


def test_the_queue_is_scoped_and_desk_only(seeded, client, public_client):
    rows = _q(client, "mkumar")["rows"]                                       # BR, Muzaffarpur only
    assert rows and all(r["line2"] for r in rows)
    gopalganj = set(r["id"] for r in _q(client, "priya")["rows"])
    assert not gopalganj & {r["id"] for r in rows}
    login(client, "boat5")                                                    # a team lead: its live cases only
    assert client.get("/v1/queue?incident=BR").json()["rows"] == []
    login(client, "seoc")                                                     # totals only
    assert client.get("/v1/queue?incident=BR").status_code == 403
    login(public_client, "priya", "rakshasetu")
    assert public_client.get("/v1/queue?incident=BR").status_code == 404


def test_a_sheets_new_cases_wait_as_one_row_and_its_to_check_rows_come_in_one_by_one(seeded, client, app_db):
    from app.core.jobs import drain
    from app.pipeline import register_handlers
    register_handlers()
    login(client, "priya")
    sheet = (b"Naam,Mob,Kitne log,Gaon,Location,Remarks\n"
             b"Sita Devi,98765 65001,4,Katiya,,chhat par\n"
             b"Gita Devi,98765 65002,3,Bhore,,paani ghus gaya\n"
             b"Mohan Ram,98765 65003,5,Nautan,,rasta kat gaya\n"
             b"Hari Ram,98765 65004,2,,,fase hain\n")            # no place: to check
    imp = client.post("/v1/imports", files={"file": ("relief.csv", sheet, "text/csv")}, data={"incident": "BR"}).json()
    client.post(f"/v1/imports/{imp['id']}/mapping", json={"mapping": imp["proposed"]})
    drain(app_db)
    rows = _q(client)["rows"]
    group = [r for r in rows if r["kind"] == "group"]
    assert len(group) == 1 and group[0]["public_id"] == "relief.csv" and len(group[0]["members"]) == 3
    assert group[0]["line1"] == "3 new cases from this sheet need a team"
    assert group[0]["action"] == {"kind": "import", "label": "Open the list", "target": str(imp["id"])}
    no_place = one(app_db, "SELECT c.id FROM reports r JOIN cases c ON c.id = r.case_id WHERE r.idempotency_key = :k",
                   k=f"{imp['file_sha256']}:5")
    single = next(r for r in rows if r["id"] == no_place)
    assert single["kind"] == "case" and single["chip"] == "needs location"
    assert not set(group[0]["members"]) & {r["id"] for r in rows if r["kind"] == "case"}
    listed = client.get("/v1/imports?incident=BR").json()
    assert listed[0]["id"] == imp["id"]
    detail = client.get(f"/v1/imports/{imp['id']}/rows").json()
    assert all("owned" in r and "case_id" in r for r in detail)


def test_an_owned_p1_that_nobody_checked_still_needs_its_check(seeded, client, app_db):
    """Officers assign P1s before the check (nobody on a roof waits for paperwork); the check still has to happen."""
    pid = one(app_db, "SELECT c.public_id FROM cases c JOIN districts d ON d.id = c.district_id WHERE d.name = 'Gopalganj'"
                      " AND c.checked_at IS NULL AND c.geom IS NOT NULL AND NOT EXISTS (SELECT 1 FROM assignments a"
                      " WHERE a.case_id = c.id AND a.state IN ('open', 'overdue')) ORDER BY c.id LIMIT 1")
    _sql(app_db, "UPDATE cases SET priority = 'P1', queue_since = now() WHERE public_id = :p", p=pid)
    login(client, "rdas")
    client.post("/v1/assignments", json={"case": pid, "team_id": one(app_db, "SELECT id FROM teams WHERE name = 'Fire & Rescue Boat 5'")})
    row = next(r for r in _q(client)["rows"] if r["public_id"] == pid)
    assert row["chip"] == "unchecked P1" and row["action"] == {"kind": "check", "label": "Check"}
