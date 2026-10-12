"""Rule R1: one write path, a hash chain whose order is the commit order, NOTIFY on commit only."""

import json
import threading

import psycopg
from sqlalchemy import text

from app.core.eventlog import GENESIS_PREV, SYSTEM, Actor, append_event, canonical, chain_hash, verify_chain
from app.migrate import to_conninfo
from tests.conftest import TEST_DB, needs_db, one, rows

pytestmark = needs_db


def test_seed_starts_a_new_chain_with_a_genesis_event(seeded, app_db):
    first = rows(app_db, "SELECT seq, action, prev_hash FROM events ORDER BY seq LIMIT 1")[0]
    assert (first.seq, first.action, first.prev_hash) == (1, "chain.genesis", GENESIS_PREV)
    assert one(app_db, "SELECT count(*) FROM events WHERE action = 'case.seeded'") == seeded["cases"]


def test_body_is_canonical_text_and_hash_covers_exactly_it(seeded, app_db):
    with app_db.begin() as c:
        seq = append_event(c, actor=Actor("user", "7", "call_taker"), action="case.checked", entity_type="case",
                           entity_id=3, incident_id=1, case_id=3, data={"b": 2, "a": "थावे"}, reason="checked by phone")
    r = rows(app_db, "SELECT body, prev_hash, hash FROM events WHERE seq = :s", s=seq)[0]
    body = json.loads(r.body)
    assert r.body == canonical(body)                       # stored once, in canonical form
    assert '"a":"थावे","b":2' in r.body                    # sorted keys, UTF-8 kept
    assert r.hash == chain_hash(r.prev_hash, r.body)
    assert body["actor"] == {"type": "user", "id": "7", "role": "call_taker"} and body["reason"] == "checked by phone"


def test_a_rolled_back_change_leaves_no_event(seeded, app_db):
    before = one(app_db, "SELECT max(seq) FROM events")
    with app_db.connect() as c:
        tx = c.begin()
        append_event(c, actor=SYSTEM, action="test.rolled_back", entity_type="test")
        tx.rollback()
    assert one(app_db, "SELECT max(seq) FROM events") == before


def test_200_concurrent_appends_make_one_unbroken_chain(seeded, app_db):
    start = one(app_db, "SELECT max(seq) FROM events")
    errors = []

    def worker(n):
        try:
            for i in range(20):
                with app_db.begin() as c:
                    append_event(c, actor=SYSTEM, action="test.concurrent", entity_type="test", entity_id=f"{n}-{i}")
        except Exception as e:  # surface thread errors in the main thread
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(10)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors
    seqs = [r[0] for r in rows(app_db, "SELECT seq FROM events WHERE seq > :s ORDER BY seq", s=start)]
    assert seqs == list(range(start + 1, start + 201))     # no gaps, no duplicates
    with app_db.connect() as c:
        result = verify_chain(c)
    assert result["ok"] and result["count"] == start + 200


def test_notify_is_delivered_only_on_commit(seeded, app_db):
    listener = psycopg.connect(to_conninfo(TEST_DB), autocommit=True)
    listener.execute("LISTEN ev")
    with app_db.connect() as c:
        tx = c.begin()
        seq = append_event(c, actor=SYSTEM, action="test.notify", entity_type="test")
        assert list(listener.notifies(timeout=0.3, stop_after=1)) == []   # nothing before commit
        tx.commit()
    got = list(listener.notifies(timeout=2, stop_after=1))
    listener.close()
    assert [n.payload for n in got] == [str(seq)]


def test_event_order_equals_commit_order_under_a_slow_writer(seeded, app_db):
    """A slow transaction that appended first must not let a faster one take a lower seq after it commits."""
    slow_has_lock = threading.Event()
    done = []

    def slow():
        with app_db.begin() as c:
            done.append(("slow", append_event(c, actor=SYSTEM, action="test.slow", entity_type="test")))
            slow_has_lock.set()
            c.execute(text("SELECT pg_sleep(0.3)"))

    t = threading.Thread(target=slow)
    t.start()
    slow_has_lock.wait()
    with app_db.begin() as c:   # blocks on the advisory lock until `slow` commits
        done.append(("fast", append_event(c, actor=SYSTEM, action="test.fast", entity_type="test")))
    t.join()
    seqs = dict(done)
    assert seqs["fast"] == seqs["slow"] + 1
