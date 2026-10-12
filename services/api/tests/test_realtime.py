"""F-C10: a change shows on every open screen; a dropped socket resumes with ?since= and loses nothing."""

import time

from app.core.eventlog import SYSTEM, append_event
from tests.conftest import needs_db, one

pytestmark = needs_db


def _append(app_db, n=1, action="test.realtime", **kw):
    seqs = []
    for _ in range(n):
        with app_db.begin() as c:
            seqs.append(append_event(c, actor=SYSTEM, action=action, entity_type="test", **kw))
    return seqs


def _br(app_db):
    return one(app_db, "SELECT id FROM incidents WHERE code = 'BR'")


def _recv_until(ws, seq):
    got = []
    while True:
        m = ws.receive_json()
        if m["type"] in ("hello", "ping"):
            continue
        got.append(m)
        if m["seq"] >= seq:
            return got


def test_polling_backfill_returns_envelopes_filtered_by_incident(seeded, client, app_db):
    events = client.get("/v1/events", params={"since": 0, "incident": "BR"}).json()
    br = _br(app_db)
    assert events[0]["type"] == "chain.genesis" and events[0]["incident_id"] is None
    assert {e["incident_id"] for e in events} <= {None, br}
    assert any(e["type"] == "case.seeded" for e in events)
    assert [e["seq"] for e in events] == sorted(e["seq"] for e in events)


def test_live_event_reaches_an_open_socket_within_2_seconds(seeded, client, app_db):
    head = one(app_db, "SELECT max(seq) FROM events")
    with client.websocket_connect(f"/v1/ws?since={head}&incident=BR") as ws:
        assert ws.receive_json()["type"] == "hello"
        started = time.monotonic()
        (seq,) = _append(app_db, incident_id=_br(app_db))
        got = _recv_until(ws, seq)
        assert time.monotonic() - started < 2.0
        assert got[-1]["seq"] == seq and got[-1]["type"] == "test.realtime"


def test_reconnect_with_since_loses_nothing(seeded, client, app_db):
    br = _br(app_db)
    head = one(app_db, "SELECT max(seq) FROM events")
    with client.websocket_connect(f"/v1/ws?since={head}&incident=BR") as ws:
        ws.receive_json()
        (first,) = _append(app_db, incident_id=br)
        last_seen = _recv_until(ws, first)[-1]["seq"]
    missed = _append(app_db, 3, incident_id=br)          # the socket is down
    with client.websocket_connect(f"/v1/ws?since={last_seen}&incident=BR") as ws:
        got = _recv_until(ws, missed[-1])
    assert [e["seq"] for e in got] == missed


def test_other_incidents_events_are_not_sent(seeded, client, app_db):
    od = one(app_db, "SELECT id FROM incidents WHERE code = 'OD'")
    head = one(app_db, "SELECT max(seq) FROM events")
    with client.websocket_connect(f"/v1/ws?since={head}&incident=BR") as ws:
        ws.receive_json()
        _append(app_db, incident_id=od)
        (mine,) = _append(app_db, incident_id=_br(app_db))
        got = _recv_until(ws, mine)
    assert [e["seq"] for e in got] == [mine]


def test_case_updates_are_coalesced_to_one_per_second(seeded, client, app_db):
    br = _br(app_db)
    case_id = one(app_db, "SELECT min(id) FROM cases WHERE incident_id = :i", i=br)
    head = one(app_db, "SELECT max(seq) FROM events")
    with client.websocket_connect(f"/v1/ws?since={head}&incident=BR") as ws:
        ws.receive_json()
        seqs = _append(app_db, 5, action="case.updated", incident_id=br, case_id=case_id)
        got = _recv_until(ws, seqs[-1])
    assert len(got) == 2 and got[0]["seq"] == seqs[0] and got[-1]["seq"] == seqs[-1]
