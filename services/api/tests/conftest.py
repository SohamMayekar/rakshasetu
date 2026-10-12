"""Test harness. Tests run against the `rakshasetu_test` database (never the demo one), through the real
API (FastAPI TestClient) and the real SQL. No fake clock: a test that needs a deadline to pass moves it
into the past in the database. No live provider calls: providers run in fixture mode.

Fixtures
  seeded        a fresh seed of all three packs for this test (wipes the test database first)
  owner_db      SQLAlchemy engine as rakshasetu_owner (for test set-up the app role may not do)
  app_db        SQLAlchemy engine as rakshasetu_app (what api/worker/ticker use)
  client        TestClient on the local listener (the desk)
  public_client TestClient on the public listener (phones through the tunnel)
Helpers
  rows(engine, sql, **params) / one(engine, sql, **params)
  login(client, username, password=None)   sign a TestClient in (the local picker needs no password)
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.migrate import migrate

TEST_DB = os.environ.get("TEST_DATABASE_URL")
TEST_OWNER_DB = os.environ.get("TEST_OWNER_DATABASE_URL")
needs_db = pytest.mark.skipif(not (TEST_DB and TEST_OWNER_DB), reason="needs the test database (run via `make test`)")


@pytest.fixture(scope="session", autouse=True)
def _migrated_test_db():
    if TEST_OWNER_DB:
        migrate(TEST_OWNER_DB, verbose=False)
    if TEST_DB:
        os.environ["DATABASE_URL"] = TEST_DB  # every engine in the app now points at the test database
    os.environ.setdefault("PROVIDER_MODE", "fixture")
    yield


@pytest.fixture(scope="session")
def owner_db():
    eng = create_engine(TEST_OWNER_DB, future=True)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def app_db():
    eng = create_engine(TEST_DB, future=True)
    yield eng
    eng.dispose()


_SNAPSHOT: dict | None = None
SNAP = "seed_snapshot"


def _tables(conn) -> list[str]:
    """Public tables in foreign-key order (parents first), so a restore never violates a constraint."""
    names = [r[0] for r in conn.execute(text(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        " AND tablename NOT IN ('schema_migrations', 'spatial_ref_sys')"))]
    deps = {n: set() for n in names}
    for child, parent in conn.execute(text(
            "SELECT c.conrelid::regclass::text, c.confrelid::regclass::text FROM pg_constraint c"
            " WHERE c.contype = 'f' AND c.connamespace = 'public'::regnamespace")):
        if child in deps and parent in deps and child != parent:
            deps[child].add(parent)
    ordered: list[str] = []
    while deps:
        ready = sorted(n for n, d in deps.items() if not d - set(ordered))
        ordered += ready
        for n in ready:
            del deps[n]
    return ordered


@pytest.fixture
def seeded(owner_db):
    """A fresh copy of the seeded test database. The real seed (through the real pipeline) runs once per
    session; each test then gets an identical restore of that snapshot (much faster than reseeding)."""
    global _SNAPSHOT
    from app.seed import seed
    with owner_db.begin() as c:
        tables = _tables(c)
    if _SNAPSHOT is None:
        _SNAPSHOT = seed(TEST_OWNER_DB)
        with owner_db.begin() as c:
            c.execute(text(f"DROP SCHEMA IF EXISTS {SNAP} CASCADE; CREATE SCHEMA {SNAP}"))
            for t in tables:
                c.execute(text(f"CREATE TABLE {SNAP}.{t} AS SELECT * FROM public.{t}"))
        return _SNAPSHOT
    with owner_db.begin() as c:
        c.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
        for t in tables:
            c.execute(text(f"INSERT INTO public.{t} SELECT * FROM {SNAP}.{t}"))
            for col, seq in c.execute(text(
                    "SELECT a.attname, pg_get_serial_sequence(:t, a.attname) FROM pg_attribute a"
                    " WHERE a.attrelid = CAST(:t AS regclass) AND a.attnum > 0 AND NOT a.attisdropped"
                    " AND pg_get_serial_sequence(:t, a.attname) IS NOT NULL"), {"t": f"public.{t}"}):
                c.execute(text(f"SELECT setval('{seq}', coalesce((SELECT max({col}) FROM public.{t}), 0) + 1, false)"))
    return _SNAPSHOT


def rows(engine, sql, **params):
    with engine.begin() as c:
        return c.execute(text(sql), params).all()


def one(engine, sql, **params):
    r = rows(engine, sql, **params)
    return r[0][0] if r else None


@pytest.fixture
def client():
    from app.main import create_app
    with TestClient(create_app(), headers={"X-RS-Listener": "local"}) as c:
        yield c


@pytest.fixture
def public_client():
    from app.main import create_app
    with TestClient(create_app(), headers={"X-RS-Listener": "public"}) as c:
        yield c


def login(client, username, password=None):
    body = {"username": username} if password is None else {"username": username, "password": password}
    r = client.post("/v1/auth/login", json=body)
    assert r.status_code == 200, r.text
    return client
