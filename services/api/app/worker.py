"""The `worker` process: runs the intake pipeline and the importer from the Postgres job queue.

Milestone 02 only proves the process runs and reaches the database; the job queue arrives in m14.
"""

from sqlalchemy import text

from app.db import get_engine
from app.loop import run_forever


def step() -> None:
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))


if __name__ == "__main__":
    run_forever("worker", 1.0, step)
