"""POST /v1/auth/login · POST /v1/auth/logout · GET /v1/me · GET /v1/auth/users (the demo picker)."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config import get_bundle, get_config
from app.core.auth import COOKIE, SESSION_SECONDS, Scope, current_scope, make_token
from app.core.listener import listener_of
from app.core.passwords import check_password
from app.db import get_engine
from app.settings import get_settings

router = APIRouter(tags=["auth"])


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str | None = Field(default=None, max_length=200)


def _picker_allowed(request: Request) -> bool:
    """Password-less "sign in as…" exists only in DEMO_MODE, on the local listener, never via the tunnel."""
    return (get_settings().demo_mode and listener_of(request) == "local"
            and "cf-connecting-ip" not in request.headers)


@router.post("/v1/auth/login")
def login(body: Login, request: Request, response: Response) -> dict:
    with get_engine().connect() as c:
        u = c.execute(text("SELECT id, role, password_hash FROM users WHERE username = :u"),
                      {"u": body.username}).one_or_none()
    roles = get_bundle().roles.roles
    if not u or not roles.get(u.role, {}).get("login"):
        raise HTTPException(status_code=401, detail="Unknown user")
    if body.password is None:
        if not _picker_allowed(request):
            raise HTTPException(status_code=401, detail="Password required")
    elif not check_password(body.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Wrong password")
    secure = request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https"
    response.set_cookie(COOKIE, make_token(u.id), max_age=SESSION_SECONDS, httponly=True, samesite="strict",
                        secure=secure, path="/")
    return {"ok": True}


@router.post("/v1/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/v1/auth/users")
def picker_users(request: Request, role: str | None = None) -> list[dict]:
    """Who can sign in without typing a password on this listener (DEMO_MODE + local only).

    No `role`: the profiles in config (demo.sign_in_picker), in that order — the desk, a team, the admin.
    `role=team_lead`: every rescue team's lead with its team and district, so the team app can offer a chooser
    instead of hard-wiring one boat. Every other seeded user still exists (the permission and IDOR tests use
    them), off this list."""
    if not _picker_allowed(request):
        raise HTTPException(status_code=404, detail="Not found")
    roles = get_bundle().roles.roles
    with get_engine().connect() as c:
        if role:
            rows = c.execute(text(
                "SELECT u.username, u.name, u.role, t.name AS team, d.name AS district, i.code AS incident"
                " FROM users u LEFT JOIN teams t ON t.id = u.team_id"
                " LEFT JOIN districts d ON d.id = t.district_id LEFT JOIN incidents i ON i.id = t.incident_id"
                " WHERE u.role = :r AND u.team_id IS NOT NULL"
                " ORDER BY i.code, d.name, t.name"), {"r": role}).all()
            return [{"username": r.username, "name": r.name, "role": r.role, "role_label": roles[r.role]["label"],
                     "team": r.team, "district": r.district, "incident": r.incident, "title": r.team, "line": r.district or ""}
                    for r in rows]
        shown = get_config().demo.get("sign_in_picker", [])
        rows = {r.username: r for r in c.execute(text(
            "SELECT u.username, u.name, u.role, t.name AS team FROM users u LEFT JOIN teams t ON t.id = u.team_id"
            " WHERE u.username = ANY(:names)"), {"names": [p["username"] for p in shown]}).all()}
    return [{"username": r.username, "name": r.name, "role": r.role, "role_label": roles[r.role]["label"], "team": r.team,
             "title": p["title"], "line": p["line"]}
            for p in shown if (r := rows.get(p["username"]))]


@router.get("/v1/me")
def me(request: Request, scope: Scope = Depends(current_scope)) -> dict:
    b = get_bundle()
    with get_engine().connect() as c:
        incidents = c.execute(text("SELECT id, code, name, type, status FROM incidents WHERE id = ANY(:ids) ORDER BY id"),
                              {"ids": list(scope.incident_ids)}).all()
        districts = c.execute(text("SELECT id, name, incident_id FROM districts WHERE id = ANY(:ids) ORDER BY id"),
                              {"ids": list(scope.district_ids)}).all()
        team = c.execute(text("SELECT id, name, has_app FROM teams WHERE id = :t"), {"t": scope.team_id}).one_or_none()
    return {
        "user": {"id": scope.user_id, "username": scope.username, "name": scope.name, "role": scope.role,
                 "role_label": b.roles.roles[scope.role]["label"]},
        "team": dict(team._mapping) if team else None,
        "incidents": [dict(r._mapping) for r in incidents],
        "districts": [dict(r._mapping) for r in districts],
        "permissions": sorted(a for a in b.roles.permissions if scope.can(a)),
        "flags": b.flags,
        "demo_mode": get_settings().demo_mode,
        "listener": listener_of(request),
    }
