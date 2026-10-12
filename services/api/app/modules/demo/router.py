"""Demo controls (PRD F-C12): local listener only, DEMO_MODE only. Reset, surge and the rest land in later milestones."""

from fastapi import APIRouter, Depends, Request

from app.core.listener import listener_of, require_demo
from app.settings import get_settings

router = APIRouter(prefix="/v1/demo", tags=["demo"], dependencies=[Depends(require_demo)])


@router.get("/status")
def demo_status(request: Request) -> dict:
    s = get_settings()
    return {"demo_mode": s.demo_mode, "listener": listener_of(request), "public_url": s.public_url}
