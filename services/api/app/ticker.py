"""The `ticker` process: every 5 s, finds passed check-in deadlines and raises escalations (PRD F-S2).

It is its own process so a 300-row import or a slow LLM call can never delay an escalation.
Milestone 02 only proves the process runs and reaches the database; the deadline logic arrives in m41.
"""

from sqlalchemy import text

from app.db import get_engine
from app.loop import run_forever


def step() -> None:
    with get_engine().connect() as conn:
        conn.execute(text("SELECT now()"))


if __name__ == "__main__":
    run_forever("ticker", 5.0, step)
