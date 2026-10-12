"""Apply SQL migrations in order, as rakshasetu_owner (rule R9). Then re-apply grants.

Plain numbered SQL files in `migrations/`, tracked in `schema_migrations`. Run by the one-shot
`migrate` compose service before the api starts, and by the test harness for the test database.
"""

import os
import sys
from pathlib import Path

import psycopg

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


def to_conninfo(url: str) -> str:
    """SQLAlchemy URLs say postgresql+psycopg://; psycopg wants postgresql://."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def migrate(owner_url: str, verbose: bool = True) -> list[str]:
    applied_now: list[str] = []
    with psycopg.connect(to_conninfo(owner_url), autocommit=True) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations ("
                     " version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
        done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
        for f in sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql")):
            if f.stem in done:
                continue
            with conn.transaction():
                conn.execute(f.read_text())
                conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (f.stem,))
            applied_now.append(f.stem)
            if verbose:
                print(f"applied {f.stem}")
        conn.execute((MIGRATIONS / "grants.sql").read_text())
    return applied_now


if __name__ == "__main__":
    url = os.environ.get("OWNER_DATABASE_URL")
    if not url:
        sys.exit("OWNER_DATABASE_URL is not set")
    applied = migrate(url)
    print(f"migrations up to date ({len(applied)} applied now)")
