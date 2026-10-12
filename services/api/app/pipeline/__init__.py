"""The intake pipeline: four plain stages as ordinary functions (PRD §8.1). No workflow framework.

`register_handlers()` imports every module that registers a job handler, so the worker knows them all.
"""


def register_handlers() -> None:
    # Each import registers @handler functions with app.core.jobs.HANDLERS. Stages arrive in m15+.
    pass
