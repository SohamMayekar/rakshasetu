"""The `ticker` process: every 5 s, passed check-in deadlines become escalations (PRD F-S2).

It is its own process so a 300-row import or a slow language-model call can never delay an escalation.
The logic is app.modules.escalations.ticker.tick(); timers live in the database, so a restart loses nothing.
"""

from app.db import get_engine
from app.loop import run_forever
from app.modules.escalations.ticker import tick


def step() -> None:
    tick(get_engine())


if __name__ == "__main__":
    run_forever("ticker", 5.0, step)
