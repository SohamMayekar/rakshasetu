"""FastAPI entry point for the `api` process."""

from fastapi import FastAPI
from sqlalchemy import text

from app.db import get_engine


def create_app() -> FastAPI:
    app = FastAPI(title="RakshaSetu API", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict:
        with get_engine().connect() as conn:
            db_ok = conn.execute(text("SELECT 1")).scalar() == 1
        return {"ok": db_ok, "service": "api", "db": "ok" if db_ok else "down"}

    return app


app = create_app()
