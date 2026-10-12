"""FastAPI entry point for the `api` process."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_bundle
from app.db import get_engine
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.cases.router import router as cases_router
from app.modules.dedupe.router import router as merges_router
from app.modules.demo.router import router as demo_router
from app.modules.imports.router import router as imports_router
from app.modules.intake.router import router as intake_router
from app.modules.public.router import router as public_router
from app.modules.queue.router import router as queue_router
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

    @app.middleware("http")
    async def json_only_mutations(request: Request, call_next):
        """With SameSite=Strict cookies, refusing form-encoded mutations closes cross-site request forgery."""
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.headers.get("content-length", "0") != "0":
            ctype = request.headers.get("content-type", "").split(";")[0].strip()
            if ctype not in ("application/json", "multipart/form-data"):
                return JSONResponse({"detail": "Send JSON (application/json)"}, status_code=415)
        return await call_next(request)

    @app.get("/healthz")
    def healthz() -> dict:
        with get_engine().connect() as conn:
            db_ok = conn.execute(text("SELECT 1")).scalar() == 1
        return {"ok": db_ok, "service": "api", "db": "ok" if db_ok else "down"}

    app.include_router(auth_router)
    app.include_router(audit_router)
    app.include_router(cases_router)
    app.include_router(intake_router)
    app.include_router(imports_router)
    app.include_router(merges_router)
    app.include_router(public_router)
    app.include_router(queue_router)
    app.include_router(demo_router)
    app.include_router(realtime_router)
    return app


app = create_app()
