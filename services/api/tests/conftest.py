"""Test harness: tests run against the rakshasetu_test database (never the demo database)."""

import os

import pytest

from app.migrate import migrate

TEST_DB = os.environ.get("TEST_DATABASE_URL")
TEST_OWNER_DB = os.environ.get("TEST_OWNER_DATABASE_URL")


@pytest.fixture(scope="session", autouse=True)
def _migrated_test_db():
    if TEST_OWNER_DB:
        migrate(TEST_OWNER_DB, verbose=False)
    if TEST_DB:
        os.environ["DATABASE_URL"] = TEST_DB
    yield
