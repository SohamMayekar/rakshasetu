"""Which Caddy listener a request came through (rule R18).

Caddy sets `X-RS-Listener` on every request it forwards and overwrites any value a client sent.
A request without the header (e.g. straight to the container) is treated as public: the safe default.
"""

from fastapi import HTTPException, Request

from app.settings import get_settings


def listener_of(request: Request) -> str:
    return "local" if request.headers.get("x-rs-listener") == "local" else "public"


def require_local(request: Request) -> None:
    """Desk-only endpoints: 404 on the public listener, as if they didn't exist."""
    if listener_of(request) != "local":
        raise HTTPException(status_code=404, detail="Not found")


def require_demo(request: Request) -> None:
    """Demo controls: DEMO_MODE on, local listener, and never through the tunnel (Cloudflare adds CF-Connecting-IP)."""
    if not get_settings().demo_mode:
        raise HTTPException(status_code=404, detail="Demo mode is off")
    if listener_of(request) != "local" or "cf-connecting-ip" in request.headers:
        raise HTTPException(status_code=403, detail="Demo controls exist only on the local listener")
