"""One SQLAlchemy engine per process. Queries are explicit SQL (`text()`), so every WHERE clause is visible."""

from functools import lru_cache

from sqlalchemy import Engine, create_engine

from app.settings import get_settings


@lru_cache(maxsize=4)
def engine_for(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20, future=True)


def get_engine() -> Engine:
    return engine_for(get_settings().database_url)
