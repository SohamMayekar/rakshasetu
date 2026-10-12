"""FastAPI entry point for the `api` process."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.config import get_bundle
from app.db import get_engine
from app.modules.audit.router import router as audit_router
from app.modules.demo.router import router as demo_router
from app.modules.realtime.hub import hub
from app.modules.realtime.router import router as realtime_router


def create_app() -> FastAPI:
    get_bundle()  # fail at boot, with the exact key, if a team-owned config file is wrong
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await hub.start()      # the one LISTEN connection for real-time fan-out
        yield
        await hub.stop()

    app = FastAPI(title="RakshaSetu API", version="0.1.0", lifespan=lifespan)

    @app.get("/healthz")
    def healthz() -> dict:
        with get_engine().connect() as conn:
            db_ok = conn.execute(text("SELECT 1")).scalar() == 1
        return {"ok": db_ok, "service": "api", "db": "ok" if db_ok else "down"}

    app.include_router(audit_router)
    app.include_router(demo_router)
    app.include_router(realtime_router)
    return app


app = create_app()
