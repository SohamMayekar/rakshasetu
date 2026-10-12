"""Per-scene demo resets (PRD F-C12): `make demo-reset SCENE=<id>` or POST /v1/demo/reset {scene}.

A reset seeds the demo database (timestamps relative to now), then REPLAYS every scene before the chosen one
through the real API, signed in as the person who does it on stage (data/scenarios/<pack>/demo.yaml; the pack
is config demo.incident, MH): the
recorded clip through the voice pipeline, the officer's paste, merge, check and sheet, the assignment and
radio log, the team lead's taps, the family's answer. Nothing is written around the API except two things a
reset has to do: it processes the queued jobs itself (so the next step sees the case), and for "Never stale"
it moves Boat 2's check-in deadline to now instead of waiting out the ×60 demo clock. That move is an
event in the audit log ("demo.clock_advanced"), never a silent edit.

    python -m app.modules.demo.scenes --scene stale        (inside the api container)
"""

import argparse
import os
import sys
import time
import uuid
from pathlib import Path

import httpx
import yaml
from sqlalchemy import Engine, text

from app.config import get_config
from app.core.eventlog import SYSTEM, append_event
from app.core.jobs import drain
from app.db import engine_for, get_engine
from app.modules.escalations.ticker import tick
from app.pipeline import register_handlers
from app.seed import seed
from app.settings import get_settings

LOCAL = os.environ.get("DEMO_LOCAL_URL", "http://caddy:80")      # the desk's own listener


class ScriptError(RuntimeError):
    """A step of the demo script didn't do what the script expects: the reset stops and says which."""


def incident() -> str:
    """The pack the performed demo runs on (config demo.incident)."""
    return get_config().demo.get("incident", "MH")


def pack(code: str | None = None) -> Path:
    return get_settings().data_dir / "scenarios" / (code or incident())


def script(code: str | None = None) -> dict:
    return yaml.safe_load((pack(code) / "demo.yaml").read_text())


def scene_ids(code: str | None = None) -> list[str]:
    return [s["id"] for s in script(code)["scenes"]]


class Stage:
    """The people on stage, one at a time, through one HTTP client (signing in switches the cookie)."""

    def __init__(self, http: httpx.Client, db: Engine, code: str):
        self.http, self.db, self.code, self.who, self.state = http, db, code, None, {}

    def as_(self, username: str) -> "Stage":
        if self.who != username:
            r = self.http.post("/v1/auth/login", json={"username": username})
            if r.status_code != 200:
                raise ScriptError(f"sign in as {username}: {r.status_code} {r.text[:200]}")
            self.who = username
        return self

    def call(self, method: str, path: str, **kw) -> dict | list:
        r = self.http.request(method, path, **kw)
        if r.status_code >= 400:
            raise ScriptError(f"{self.who}: {method} {path} → {r.status_code} {r.text[:300]}")
        return r.json() if r.content else {}

    def post(self, path: str, idem: bool = False, **kw) -> dict:
        if idem:
            kw["headers"] = {**kw.get("headers", {}), "Idempotency-Key": f"reset-{uuid.uuid4()}"}
        return self.call("POST", path, **kw)

    def get(self, path: str, **kw):
        return self.call("GET", path, **kw)

    def one(self, sql: str, **p):
        with self.db.connect() as c:
            return c.execute(text(sql), p).scalar()

    def settle(self, report_id: int, timeout: float = 30) -> int:
        """Run the queued jobs here (the worker may take some too) until the report is in a case."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            drain(self.db)
            case = self.one("SELECT case_id FROM reports WHERE id = :r", r=report_id)
            if case:
                return case
            time.sleep(0.2)
        raise ScriptError(f"report {report_id} wasn't in a case after {timeout:.0f} s")

    def team(self, name: str) -> int:
        tid = self.one("SELECT t.id FROM teams t JOIN incidents i ON i.id = t.incident_id WHERE i.code = :c"
                       " AND t.name = :n", c=self.code, n=name)
        if not tid:
            raise ScriptError(f"no team called {name!r} in {self.code}")
        return tid

    def live_assignment(self, case_id: int) -> int:
        aid = self.one("SELECT id FROM assignments WHERE case_id = :c AND state IN ('open', 'overdue')", c=case_id)
        if not aid:
            raise ScriptError(f"case {case_id} has no live assignment")
        return aid


# ---- the steps: each one is a scene, played; a reset to scene N plays scenes 0..N-1 -------------------------

def play_son(st: Stage, s: dict) -> None:
    """0:00 A family asks for help: the recorded clip through the voice pipeline, from the son's phone."""
    st.as_("admin")
    out = st.post("/v1/demo/play-clip", json={"clip": s["son"]["clip"], "device_id": s["son"]["device_id"],
                                              "incident": s["incident"]})
    st.state["son"] = st.settle(out["report_id"])


def play_merge(st: Stage, s: dict) -> None:
    """0:50 Never doubled: the neighbour's forward is suggested and merged, the case checked; the Das family refused."""
    st.as_(s["operator"])
    son = st.state["son"]
    rid = st.post("/v1/ingest/desk", json={"incident": s["incident"], "text": s["forward"]["text"], "phone": s["forward"]["phone"],
                                           "client_id": str(uuid.uuid4()), "pasted_forward": True})["report_id"]
    fwd = st.settle(rid)
    if fwd != son:
        pair = [x for x in st.get("/v1/merge-suggestions", params={"case": son})
                if {x["case_id"], x["candidate_case_id"]} == {son, fwd} and x["strength"] != "refused"]
        if not pair:
            raise ScriptError("the neighbour's forward wasn't suggested as the son's household")
        st.state["son"] = son = st.post(f"/v1/merge-suggestions/{pair[0]['id']}/accept", json={})["kept"]
    st.post(f"/v1/cases/{son}/check", json={})
    rid = st.post("/v1/ingest/desk", json={"incident": s["incident"], "text": s["das"]["text"], "phone": s["das"]["phone"],
                                           "client_id": str(uuid.uuid4())})["report_id"]
    das = st.settle(rid)
    if das == son:
        raise ScriptError("the Das report was merged into the son's case; the script expects a refusal")


def play_sheet(st: Stage, s: dict) -> None:
    """1:15 The volunteer sheet: upload, confirm the proposed mapping, wait for the summary."""
    st.as_(s["operator"])
    path = pack(s["incident"]) / s["sheet"]
    imp = st.post("/v1/imports", files={"file": (path.name, path.read_bytes(), "text/csv")}, data={"incident": s["incident"]})
    st.post(f"/v1/imports/{imp['id']}/mapping", json={"mapping": imp["proposed"]})
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        drain(st.db)
        if st.get(f"/v1/imports/{imp['id']}")["status"] == "done":
            return
        time.sleep(0.3)
    raise ScriptError("the sheet import didn't finish in 90 s")


def play_stale(st: Stage, s: dict) -> None:
    """1:45 Never stale: Boat 2 acknowledges on radio with an ETA, goes silent past it, and the officer reassigns."""
    st.as_(s["operator"])
    son, boat2, boat5 = st.state["son"], st.team(s["radio_team"]), st.team(s["reassign_to"])
    aid = st.post("/v1/assignments", json={"case": str(son), "team_id": boat2})["assignment_id"]
    st.post(f"/v1/teams/{boat2}/contact", json={"kind": "radio", "channel": s["radio"]["channel"],
                                               "new_eta": s["radio"]["eta_minutes"], "note": "Acknowledged on radio"})
    with st.db.begin() as c:   # the ×60 demo clock would take ~15 s more; on the record, not silently
        c.execute(text("UPDATE assignments SET next_contact_due = now() - interval '1 second' WHERE id = :a"), {"a": aid})
        row = c.execute(text("SELECT incident_id, district_id FROM cases WHERE id = :c"), {"c": son}).one()
        append_event(c, actor=SYSTEM, action="demo.clock_advanced", entity_type="assignment", entity_id=aid,
                     incident_id=row.incident_id, district_id=row.district_id, case_id=son, team_id=boat2,
                     data={"assignment_id": aid, "why": f"demo reset: {s['radio_team']}'s ETA has passed"})
    tick(st.db)
    esc = [e for e in st.get("/v1/escalations", params={"incident": s["incident"]}) if e["team_id"] == boat2]
    if not esc:
        raise ScriptError(f"no escalation opened for {s['radio_team']}")
    st.post(f"/v1/escalations/{esc[0]['id']}/reassign", json={"case": str(son), "team_id": boat5})


def play_rescue(st: Stage, s: dict) -> None:
    """2:30 The rescue: trip 1 takes 4 with someone still there; trip 2 takes 2, nobody left; the family says yes."""
    son, boat5 = st.state["son"], st.team(s["reassign_to"])
    for n, trip in enumerate(s["trips"]):
        if n:   # a partial rescue ends that assignment: the officer sends the boat back
            st.as_(s["operator"]).post("/v1/assignments", json={"case": str(son), "team_id": boat5})
        st.as_(s["team_lead"])
        aid = st.live_assignment(son)
        st.post(f"/v1/assignments/{aid}/acknowledge", idem=True, json={"eta_minutes": trip["eta_minutes"]})
        st.post(f"/v1/assignments/{aid}/reached", idem=True, json={})
        st.post(f"/v1/cases/{son}/rescues", idem=True,
                json={"people_taken": trip["people_taken"], "anyone_left": trip["anyone_left"]})
    pid = st.one("SELECT public_id FROM cases WHERE id = :c", c=son)
    st.post(f"/v1/public/cases/{pid}/confirm", json={"device_id": s["son"]["device_id"], "answer": s["family_answer"]})


def real_clock(db: Engine) -> int:
    """A reset point waits for the presenter. A live assignment the replay made (Boat 5, offered at the end of
    "Never stale") would be on the ×60 demo clock and overdue seconds after the reset; it goes onto the real
    clock instead, with what was left of its window scaled back up (an event says so). Anything the presenter
    does from here is live and on the demo clock as usual."""
    from app.config import get_config
    k = get_config().contact.demo_clock_multiplier
    with db.begin() as c:
        rows = c.execute(text(
            "SELECT a.id, a.case_id, a.team_id, t.name AS team, k.incident_id, k.district_id,"
            " greatest(extract(epoch FROM a.next_contact_due - now()), 0) AS left_s FROM assignments a"
            " JOIN teams t ON t.id = a.team_id JOIN cases k ON k.id = a.case_id"
            " WHERE a.state IN ('open', 'overdue') AND a.demo_clock FOR UPDATE OF a")).all()
        for a in rows:
            secs = max(float(a.left_s) * k, 60)
            c.execute(text("UPDATE assignments SET demo_clock = false, next_contact_due = now() + make_interval(secs => :s)"
                           " WHERE id = :a"), {"s": secs, "a": a.id})
            append_event(c, actor=SYSTEM, action="demo.clock_real", entity_type="assignment", entity_id=a.id,
                         incident_id=a.incident_id, district_id=a.district_id, case_id=a.case_id, team_id=a.team_id,
                         data={"assignment_id": a.id, "team": a.team, "seconds": round(secs),
                               "why": "demo reset point: the timer waits for the presenter, on the real clock"})
    return len(rows)


PLAY = {"son": play_son, "merge": play_merge, "sheet": play_sheet, "stale": play_stale, "rescue": play_rescue}


def reset(scene: str = "son", *, code: str | None = None, owner_url: str | None = None,
          http: httpx.Client | None = None) -> dict:
    """Seed, then play every scene before `scene` of pack `code` (default: the configured demo pack). Returns what
    a person needs to carry on from there."""
    code = code or incident()
    ids = scene_ids(code)
    if scene not in ids:
        raise ScriptError(f"no scene {scene!r}; scenes are {', '.join(ids)}")
    owner_url = owner_url or os.environ.get("DEMO_OWNER_DATABASE_URL")
    if not owner_url:
        raise ScriptError("DEMO_OWNER_DATABASE_URL is not set")
    t0 = time.monotonic()
    register_handlers()
    from app.modules.partners.webhooks import quiet_streams
    with quiet_streams(engine_for(owner_url)):   # partners hear nothing of the seed or the replay
        seed(owner_url, reason=f"demo reset to scene {scene!r}")
        timings = {"seed": round(time.monotonic() - t0, 1)}
        s = script(code)
        own = http is None
        http = http or httpx.Client(base_url=LOCAL, timeout=60)
        try:
            st = Stage(http, get_engine(), code)
            for step in ids[:ids.index(scene)]:
                t = time.monotonic()
                PLAY[step](st, s)
                timings[step] = round(time.monotonic() - t, 1)
        finally:
            if own:
                http.close()
        real_clock(st.db)
    son = st.state.get("son")
    return {"scene": scene, "seconds": round(time.monotonic() - t0, 1), "timings": timings,
            "son_case": st.one("SELECT public_id FROM cases WHERE id = :c", c=son) if son else None}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scene", default="son", help=f"one of: {', '.join(scene_ids())}")
    args = ap.parse_args()
    if not get_settings().demo_mode:
        sys.exit("refusing to reset: DEMO_MODE is off (a reset wipes the database)")
    try:
        print(reset(args.scene))
    except ScriptError as e:
        sys.exit(f"reset stopped: {e}")


if __name__ == "__main__":
    main()
