"""FastAPI entry point for the `api` process."""

from fastapi import FastAPI
from sqlalchemy import text

from app.config import get_bundle
from app.db import get_engine
from app.modules.demo.router import router as demo_router


def create_app() -> FastAPI:
    get_bundle()  # fail at boot, with the exact key, if a team-owned config file is wrong
    app = FastAPI(title="RakshaSetu API", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict:
        with get_engine().connect() as conn:
            db_ok = conn.execute(text("SELECT 1")).scalar() == 1
        return {"ok": db_ok, "service": "api", "db": "ok" if db_ok else "down"}

    app.include_router(demo_router)
    return app


app = create_app()
