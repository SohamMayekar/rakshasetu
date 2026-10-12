"""name → adapter. An adapter is a function that returns a CanonicalReport."""

from collections.abc import Callable

from app.contracts import CanonicalReport

ADAPTERS: dict[str, Callable[..., CanonicalReport]] = {}


def adapter(name: str):
    def wrap(fn):
        ADAPTERS[name] = fn
        return fn
    return wrap
