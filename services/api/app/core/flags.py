"""Runtime switches every process reads from the database (e.g. the demo's "language model off")."""

import json

from sqlalchemy import Connection, text

from app.config import get_config
from app.db import get_engine


def get_flag(key: str, default):
    with get_engine().connect() as c:
        v = c.execute(text("SELECT value FROM runtime_flags WHERE key = :k"), {"k": key}).scalar()
    return default if v is None else v


def set_flag(conn: Connection, key: str, value, by: str) -> None:
    conn.execute(text("INSERT INTO runtime_flags (key, value, updated_by) VALUES (:k, CAST(:v AS jsonb), :b)"
                      " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_by = :b, updated_at = now()"),
                 {"k": key, "v": json.dumps(value), "b": by})


def language_model_enabled() -> bool:
    return bool(get_flag("language_model_enabled", get_config().providers.get("language_model_enabled", True)))
