"""FastAPI entry point for the `api` process."""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_bundle
from app.db import get_engine
from app.modules.assignments.router import router as assignments_router
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.cases.router import router as cases_router
from app.modules.dedupe.router import router as merges_router
from app.modules.demo.router import router as demo_router
from app.modules.dispatch.router import router as dispatch_router
from app.modules.escalations.router import router as escalations_router
from app.modules.evidence.router import router as evidence_router
from app.modules.imports.router import router as imports_router
from app.modules.incidents.router import router as incidents_router
from app.modules.intake.router import router as intake_router
from app.modules.metrics import surge
from app.modules.metrics.router import router as metrics_router
from app.modules.partners import log as partner_log
from app.modules.partners.router import router as partners_router
from app.modules.public.router import router as public_router
from app.modules.queue.router import router as queue_router
from app.modules.realtime.hub import hub
from app.modules.realtime.router import router as realtime_router
from app.modules.rescues.router import router as rescues_router
from app.modules.teams.router import router as teams_router
from app.modules.telemetry.router import router as telemetry_router


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

    @app.middleware("http")
    async def partner_calls(request: Request, call_next):
        """The partner log (P1 #13): every signed partner POST, refused or not, with its latency and body hash."""
        pid = request.headers.get("x-rakshasetu-partner")
        path = request.url.path
        if request.method != "POST" or not pid or not path.startswith(("/v1/ingest/", "/v1/partners/")):
            return await call_next(request)
        p = next((x for x in get_bundle().partners if x.id == pid), None)
        if p is not None and p.lane == "surge":       # synthetic load: not logged one by one
            return await call_next(request)
        call: dict = {}
        token = partner_log.CALL.set(call)
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            partner_log.CALL.reset(token)
        await run_in_threadpool(partner_log.write, pid, "in", request.method, path, response.status_code,
                                int((time.perf_counter() - t0) * 1000), call)
        return response

    @app.middleware("http")
    async def time_ingest(request: Request, call_next):
        """Ingest acknowledges after the database write; this times exactly that, for the surge screen's p95."""
        if not (request.method == "POST" and request.url.path.startswith("/v1/ingest/")):
            return await call_next(request)
        t0 = time.perf_counter()
        response = await call_next(request)
        surge.record((time.perf_counter() - t0) * 1000, response.status_code)
        return response

    @app.get("/healthz")
    def healthz() -> dict:
        with get_engine().connect() as conn:
            db_ok = conn.execute(text("SELECT 1")).scalar() == 1
        return {"ok": db_ok, "service": "api", "db": "ok" if db_ok else "down"}

    app.include_router(auth_router)
    app.include_router(assignments_router)
    app.include_router(audit_router)
    app.include_router(dispatch_router)
    app.include_router(rescues_router)
    app.include_router(cases_router)
    app.include_router(incidents_router)
    app.include_router(intake_router)
    app.include_router(imports_router)
    app.include_router(merges_router)
    app.include_router(metrics_router)
    app.include_router(public_router)
    app.include_router(queue_router)
    app.include_router(demo_router)
    app.include_router(evidence_router)
    app.include_router(escalations_router)
    app.include_router(teams_router)
    app.include_router(realtime_router)
    app.include_router(partners_router)
    app.include_router(telemetry_router)
    return app


app = create_app()
