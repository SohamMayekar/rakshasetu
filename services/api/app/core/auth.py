"""Authentication and the Scope (PRD F-C9, rule R8).

- The session cookie holds ONLY the user id and when it was issued, signed with HMAC (SECRET_KEY).
  It is httpOnly and SameSite=Strict; mutations are JSON-only (see app.main), which closes CSRF.
- Role and scope are loaded from the database on EVERY request, so a changed role or a reassigned team
  takes effect immediately.
- `Scope` is what every repository function receives. It produces the SQL WHERE fragment that limits
  rows to what this caller may see; it is never a check applied after the query.
"""

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, Request
from fastapi.requests import HTTPConnection
from sqlalchemy import text

from app.config import get_bundle
from app.db import get_engine
from app.settings import get_settings

COOKIE = "rs_session"
SESSION_SECONDS = 12 * 3600
DESK_ROLES = {"call_taker", "duty_officer", "incharge"}


def _sign(payload: str) -> str:
    return hmac.new(get_settings().secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()


def make_token(user_id: int) -> str:
    payload = base64.urlsafe_b64encode(f"{user_id}:{int(time.time())}".encode()).decode()
    return f"{payload}.{_sign(payload)}"


def read_token(token: str | None) -> int | None:
    if not token or "." not in token:
        return None
    payload, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(payload)):
        return None
    try:
        user_id, issued = base64.urlsafe_b64decode(payload.encode()).decode().split(":")
    except (ValueError, UnicodeDecodeError):
        return None
    if time.time() - int(issued) > SESSION_SECONDS:
        return None
    return int(user_id)


@dataclass(frozen=True)
class Scope:
    kind: str                                  # user | partner | public
    role: str
    user_id: int | None = None
    username: str | None = None
    name: str | None = None
    incident_ids: tuple[int, ...] = ()
    district_ids: tuple[int, ...] = ()
    team_id: int | None = None
    partner_id: str | None = None
    extras: dict = field(default_factory=dict, compare=False)

    # --- what may this caller DO? ----------------------------------------------------------------
    def can(self, action: str) -> bool:
        return get_bundle().roles.allows(self.role, action)

    @property
    def actor_id(self) -> str | None:
        return self.partner_id if self.kind == "partner" else (str(self.user_id) if self.user_id else None)

    # --- what may this caller SEE? (rule R8: always inside the SQL) ---------------------------------
    def case_where(self, alias: str = "c") -> tuple[str, dict]:
        if self.role == "admin":
            return "TRUE", {}
        if self.role in DESK_ROLES:
            return (f"({alias}.incident_id = ANY(:scope_incidents) AND {alias}.district_id = ANY(:scope_districts))",
                    {"scope_incidents": list(self.incident_ids), "scope_districts": list(self.district_ids)})
        if self.role == "team_lead" and self.team_id:
            return (f"{alias}.id IN (SELECT a.case_id FROM assignments a WHERE a.team_id = :scope_team"
                    f" AND a.state IN ('open', 'overdue'))", {"scope_team": self.team_id})
        return "FALSE", {}   # SEOC viewer (totals only), partners, the public

    def event_where(self, alias: str = "e") -> tuple[str, dict]:
        """Which audit/stream events this caller may read."""
        if self.role == "admin":
            return "TRUE", {}
        if self.role in DESK_ROLES:
            return (f"(({alias}.incident_id IS NULL AND {alias}.case_id IS NULL)"
                    f" OR ({alias}.incident_id = ANY(:scope_incidents)"
                    f"     AND ({alias}.district_id IS NULL OR {alias}.district_id = ANY(:scope_districts))))",
                    {"scope_incidents": list(self.incident_ids), "scope_districts": list(self.district_ids)})
        if self.role == "team_lead" and self.team_id:
            cases, params = self.case_where("cc")
            return (f"({alias}.team_id = :scope_team OR {alias}.case_id IN (SELECT cc.id FROM cases cc WHERE {cases}))",
                    {"scope_team": self.team_id, **params})
        return "FALSE", {}

    def allows_envelope(self, env: dict) -> bool:
        """The same rule as event_where, for envelopes already in memory (WebSocket fan-out)."""
        if self.role == "admin":
            return True
        if self.role in DESK_ROLES:
            if env["incident_id"] is None:
                return env["data"].get("case_id") is None
            return env["incident_id"] in self.incident_ids and (
                env.get("district_id") is None or env["district_id"] in self.district_ids)
        if self.role == "team_lead":
            return env["data"].get("team_id") == self.team_id or env["data"].get("case_id") in self.extras.get(
                "live_case_ids", set())
        return False


PUBLIC = Scope(kind="public", role="reporter")


def load_user_scope(user_id: int) -> Scope | None:
    with get_engine().connect() as c:
        u = c.execute(text("SELECT id, username, name, role, incident_ids, district_ids, team_id FROM users"
                           " WHERE id = :id"), {"id": user_id}).one_or_none()
    if not u:
        return None
    return Scope(kind="user", role=u.role, user_id=u.id, username=u.username, name=u.name,
                 incident_ids=tuple(u.incident_ids), district_ids=tuple(u.district_ids), team_id=u.team_id)


def optional_scope(conn: HTTPConnection) -> Scope:
    uid = read_token(conn.cookies.get(COOKIE))
    return (load_user_scope(uid) if uid else None) or PUBLIC


def current_scope(request: Request) -> Scope:
    scope = optional_scope(request)
    if scope.kind == "public":
        raise HTTPException(status_code=401, detail="Sign in first")
    return scope


def require(action: str):
    """FastAPI dependency: the caller's role must allow `action` (roles.yaml). Returns the Scope."""
    def dep(scope: Scope = Depends(current_scope)) -> Scope:
        if not scope.can(action):
            raise HTTPException(status_code=403, detail=f"Your role ({scope.role}) can't do this")
        return scope
    return dep
