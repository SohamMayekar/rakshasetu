"""Rule R9: the app role can append to `events` but can never edit or delete history."""

import os

import psycopg
import pytest

from app.migrate import to_conninfo

APP = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not APP, reason="needs TEST_DATABASE_URL")


def _app_conn():
    return psycopg.connect(to_conninfo(APP))


def test_app_role_owns_no_table():
    with _app_conn() as c:
        owned = c.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner = current_user").fetchone()[0]
    assert owned == 0


@pytest.mark.parametrize("stmt", [
    "UPDATE events SET reason = 'edited'",
    "DELETE FROM events",
    "TRUNCATE events",
    "CREATE TABLE sneaky (id int)",
])
def test_app_role_cannot_rewrite_history_or_the_schema(stmt):
    with _app_conn() as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
        c.execute(stmt)


def test_app_role_can_append_and_read_events():
    with _app_conn() as c:
        c.execute("INSERT INTO events (seq, at, actor_type, action, entity_type, body, prev_hash, hash)"
                  " VALUES (-1, now(), 'system', 'test.probe', 'test', '{}', 'x', 'probe-hash-unique')")
        assert c.execute("SELECT count(*) FROM events WHERE seq = -1").fetchone()[0] == 1
        c.rollback()  # leave the test database clean
