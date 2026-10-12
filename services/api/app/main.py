"""FastAPI entry point for the `api` process."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="RakshaSetu API", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True, "service": "api"}

    return app


app = create_app()
