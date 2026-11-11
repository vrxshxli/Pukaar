"""FastAPI app for Pukaar: API routes, the live event stream, and the built frontend."""
import asyncio
import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth, db, events, llm, orchestrator, scenario
from .auth import require_officer
from .tools import approvals, audit, geo, messaging, teams, tickets
from .tools.approvals import ApprovalRequired

log = logging.getLogger("pukaar")
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
_stop = threading.Event()


def _ticker():
    # Moves the game forward: alerts, team movement, stale tickets.
    while not _stop.is_set():
        try:
            orchestrator.tick()
        except Exception:
            log.exception("tick failed")
        _stop.wait(1.0)


@asynccontextmanager
async def lifespan(app):
    db.connect()
    auth.ensure_accounts()
    if auth.using_default_passwords():
        log.warning("Using the demo passwords. Set PUKAAR_OFFICER_PASSWORD and PUKAAR_VOLUNTEER_PASSWORD "
                    "before sharing a public link.")
    if os.environ.get("LLM_MODE"):
        db.set_setting("llm_mode", os.environ["LLM_MODE"])
    events.bind_loop(asyncio.get_running_loop())
    if llm.mode() == "ollama":
        llm.warm_up()
    if os.environ.get("PUKAAR_NO_TICKER") != "1":
        threading.Thread(target=_ticker, daemon=True, name="ticker").start()
    yield
    _stop.set()


app = FastAPI(title="Pukaar", lifespan=lifespan)


class MessageIn(BaseModel):
    phone: str
    text: str
    channel: str = "chat"
    name: str | None = None
    area: str | None = None


class DecisionIn(BaseModel):
    decision: str
    officer: str = "Duty officer"
    team_id: str | None = None


class VolunteerIn(BaseModel):
    action: str
    road: str | None = None
    otp: str | None = None


class SettingsIn(BaseModel):
    automation: bool | None = None
    llm_mode: str | None = None
    auto_field: bool | None = None
    planner_scope: str | None = None
    listen_llm: bool | None = None
    ollama_model: str | None = None


class CloseIn(BaseModel):
    officer: str = "Duty officer"


@app.exception_handler(ApprovalRequired)
async def approval_required(request: Request, exc: ApprovalRequired):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.get("/api/health")
def health():
    return {"ok": True}


class LoginIn(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
def login(body: LoginIn, request: Request, response: Response):
    token, user = auth.login(body.username, body.password)
    # Behind the Cloudflare tunnel the browser talks HTTPS even though we see HTTP.
    https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_SECONDS, httponly=True, samesite="lax", secure=https)
    audit.log("Officer" if user["role"] == "officer" else "Loop", f"{user['display_name']} signed in", kind="human",
              approved_by=user["display_name"])
    return {"user": auth.public_user(user)}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    auth.logout(request.cookies.get(auth.COOKIE))
    response.delete_cookie(auth.COOKIE)
    return {"ok": True}


@app.get("/api/auth/me")
def me(request: Request):
    return {"user": auth.public_user(auth.require_user(request))}


@app.get("/api/state")
def state(officer=Depends(require_officer)):
    """Everything the dashboard needs in one call."""
    incident = db.one("SELECT * FROM incidents ORDER BY id LIMIT 1")
    all_tickets = [t for t in tickets.all_tickets() if t["kind"] != "duplicate"]
    blocked = geo.blocked_roads()
    return {
        "incident": incident,
        "ward": {k: scenario.ward()[k] for k in ("name", "center", "river", "helplines", "incident_name")},
        "clock": db.now_iso(),
        "clock_speed": float(db.get_setting("clock_speed", "1")),
        "automation": db.automation_on(),
        "auto_field": db.get_setting("auto_field", "off") == "on",
        "llm": llm.status(),
        "planner": planner_status(),
        "replay": replay_status(),
        "tickets": all_tickets,
        "teams": teams.all_teams(),
        "approvals": approvals.pending(),
        "camps": [dict(c, needs=db.loads(c["needs"], [])) for c in db.query("SELECT * FROM camps")],
        "blocked_roads": [{"road": r, "segments": geo.road_geometry(r)} for r in blocked],
        "watch_zones": db.loads(db.get_setting("watch_zones"), []),
        "bulletins": db.query("SELECT * FROM bulletins ORDER BY id DESC LIMIT 10"),
        "metrics": metrics(all_tickets),
    }


@app.get("/api/public/overview")
def public_overview():
    """What the public landing page may show: the ward map and night totals.
    No family, ticket, message, phone number or boat position."""
    w = scenario.ward()
    incident = db.one("SELECT level, status FROM incidents ORDER BY id LIMIT 1") or {"level": "none", "status": ""}
    all_tickets = [t for t in tickets.all_tickets() if t["kind"] != "duplicate"]
    camps = db.query("SELECT name, lat, lng, capacity, occupancy FROM camps")
    road_names = sorted({e["name"] for e in geo.edges()})
    return {
        "ward": {k: w[k] for k in ("name", "city", "incident_name", "center", "river")},
        "incident": {"level": incident["level"], "status": incident["status"]},
        "clock": db.now_iso(),
        "roads": [{"road": r, "segments": geo.road_geometry(r)} for r in road_names],
        "blocked_roads": [{"road": r, "segments": geo.road_geometry(r)} for r in geo.blocked_roads()],
        "watch_zones": db.loads(db.get_setting("watch_zones"), []),
        "camps": camps,
        "landmarks": [{"name": lm["name"], "lat": lm["lat"], "lng": lm["lng"]} for lm in scenario.landmarks()],
        "totals": {
            "reports_in": db.one("SELECT COUNT(*) n FROM messages WHERE direction = 'in'")["n"],
            "families_safe": metrics(all_tickets)["safe"],
            "boats_out": sum(1 for t in teams.all_teams() if t["status"] != "free"),
            "boats": len(teams.all_teams()),
            "people_in_camps": sum(c["occupancy"] for c in camps),
        },
    }


def planner_status():
    from .agents import planner
    return {"scope": planner.scope(), "provider": llm.planner_provider(), "model": llm.planner_model(),
            "max_steps": planner.MAX_STEPS}


def metrics(all_tickets):
    rescue_kinds = ("rescue", "welfare", "supplies")
    wasted = db.one("""SELECT COUNT(*) n FROM approvals a JOIN tickets t ON t.id = a.ticket_id
                       WHERE a.kind = 'dispatch' AND a.status = 'approved'
                       AND (t.kind IN ('duplicate', 'verify') OR a.decided_at > IFNULL(t.safe_at, '9999'))""")["n"]
    return {
        "reports_in": db.one("SELECT COUNT(*) n FROM messages WHERE direction = 'in'")["n"],
        "tickets": sum(1 for t in all_tickets if t["kind"] in rescue_kinds and t["id"] != "P-0398"),
        "open_p1": sum(1 for t in all_tickets if t["priority"] == "P1" and t["status"] not in ("safe", "closed")),
        "waiting_approvals": db.one("SELECT COUNT(*) n FROM approvals WHERE status = 'pending'")["n"],
        "wasted_trips": wasted,
        "safe": sum(1 for t in all_tickets if t["status"] in ("safe", "closed") and t["id"] != "P-0398"),
        "verify": sum(1 for t in all_tickets if t["status"] == "verify"),
    }


def replay_status():
    from . import replay
    return replay.status()


@app.get("/api/tickets/{ticket_id}")
def ticket_detail(ticket_id: str, officer=Depends(require_officer)):
    t = tickets.get(ticket_id)
    if not t:
        raise HTTPException(404, "No such ticket")
    t["reports"] = db.query("""
        SELECT tr.reason, tr.confidence, tr.created_at, m.text, m.channel, m.language, rp.phone, rp.name
        FROM ticket_reports tr JOIN reports r ON r.id = tr.report_id
        JOIN messages m ON m.id = r.message_id JOIN reporters rp ON rp.id = tr.reporter_id
        WHERE tr.ticket_id = ? ORDER BY tr.created_at""", (ticket_id,))
    t["history"] = audit_for(ticket_id)
    from .agents.planner import runs_for_ticket
    t["agent_runs"] = runs_for_ticket(ticket_id)
    return t


def audit_for(ticket_id):
    return db.query("SELECT * FROM audit_log WHERE ticket_id = ? AND kind != 'tool' ORDER BY id", (ticket_id,))


@app.post("/api/tickets/{ticket_id}/close")
def close_ticket(ticket_id: str, body: CloseIn, officer=Depends(require_officer)):
    """Closing without the family's reply: the officer's tap is the approval."""
    if not tickets.get(ticket_id):
        raise HTTPException(404, "No such ticket")
    with orchestrator._lock:
        approval = approvals.create_approval("close", f"Close {ticket_id} without the family's reply?",
                                             ticket_id=ticket_id, agent="Officer")
        if approval is None:
            raise HTTPException(409, "Automation is off, so no approval could be created")
    return orchestrator.handle_approval(approval["id"], "approve", officer["display_name"])


class DowngradeIn(BaseModel):
    priority: str = "P2"
    officer: str = "Duty officer"


@app.post("/api/tickets/{ticket_id}/downgrade")
def downgrade_ticket(ticket_id: str, body: DowngradeIn, officer=Depends(require_officer)):
    """Agents can never lower a P1. The officer can, and the tap is recorded as an approval."""
    t = tickets.get(ticket_id)
    if not t:
        raise HTTPException(404, "No such ticket")
    if body.priority not in ("P2", "P3"):
        raise HTTPException(400, "Priority must be P2 or P3")
    with orchestrator._lock:
        approval = approvals.create_approval("downgrade", f"Downgrade {ticket_id} from {t['priority']} to {body.priority}?",
                                             ticket_id=ticket_id, payload={"priority": body.priority}, agent="Officer")
        if approval is None:
            raise HTTPException(409, "Automation is off, so no approval could be created")
    return orchestrator.handle_approval(approval["id"], "approve", officer["display_name"])


@app.get("/api/activity")
def activity(limit: int = 80, officer=Depends(require_officer)):
    return db.query("SELECT * FROM audit_log WHERE kind != 'tool' ORDER BY id DESC LIMIT ?", (limit,))


@app.get("/api/audit")
def audit_log(limit: int = 300, officer=Depends(require_officer)):
    return audit.recent(limit)


@app.post("/api/messages")
def post_message(body: MessageIn):
    if not body.text.strip():
        raise HTTPException(400, "Message is empty")
    return orchestrator.handle_message(body.phone, body.text.strip(), channel=body.channel, name=body.name, area=body.area)


@app.get("/api/chat/{phone}")
def chat_thread(phone: str):
    r = db.one("SELECT * FROM reporters WHERE phone = ?", (phone,))
    return messaging.thread(r["id"]) if r else []


@app.post("/api/approvals/{approval_id}")
def decide(approval_id: int, body: DecisionIn, officer=Depends(require_officer)):
    if body.decision not in ("approve", "reject"):
        raise HTTPException(400, "Decision must be approve or reject")
    try:
        return orchestrator.handle_approval(approval_id, body.decision, officer["display_name"], team_id=body.team_id)
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.get("/api/volunteer/{team_id}")
def volunteer_view(team_id: str, request: Request):
    auth.require_team(request, team_id)
    team = teams.get(team_id)
    if not team:
        raise HTTPException(404, "No such team")
    task = None
    if team["ticket_id"]:
        t = tickets.get(team["ticket_id"])
        # Volunteers need the place and the needs, but not reporters' phone numbers.
        task = {k: t[k] for k in ("id", "title", "area", "landmark", "priority", "reasons", "people", "vulnerable",
                                  "medical", "danger", "water_level", "status", "lat", "lng", "notes")}
    route = teams.active_route(team_id)
    return {"team": team, "task": task, "route": route, "messages": messaging.team_thread(team_id),
            "blocked_roads": [{"road": r, "segments": geo.road_geometry(r)} for r in geo.blocked_roads()]}


@app.post("/api/volunteer/{team_id}")
def volunteer_action(team_id: str, body: VolunteerIn, request: Request):
    auth.require_team(request, team_id)
    try:
        return orchestrator.handle_volunteer(team_id, body.action, road=body.road, otp=body.otp)
    except (ValueError, KeyError) as e:
        raise HTTPException(409, str(e))


@app.get("/api/family")
def family_lookup(ticket: str | None = None, name: str | None = None, area: str | None = None):
    """'Is my family safe?' Returns only status and camp, never an address or phone."""
    matches = []
    if ticket:
        t = tickets.get(ticket.strip().upper())
        if t and t["kind"] in ("rescue", "welfare"):
            matches = [t]
    elif name:
        from rapidfuzz import fuzz
        for t in tickets.all_tickets():
            if t["kind"] not in ("rescue", "welfare"):
                continue
            name_ok = fuzz.partial_ratio(name.lower(), t["title"].lower()) >= 80
            area_ok = not area or fuzz.partial_ratio(area.lower(), (t["area"] or "").lower()) >= 70
            if name_ok and area_ok:
                matches.append(t)
    results = []
    for t in matches[:5]:
        db.insert("lookups", query=json.dumps({"ticket": ticket, "name": name, "area": area}),
                  ticket_id=t["id"], created_at=db.now_iso())
        results.append(tickets.public_status(t))
    if results:
        audit.log("Loop", f"Family lookup matched {', '.join(r['ticket_id'] for r in results)}",
                  tool="family_lookup", kind="action", ticket_id=results[0]["ticket_id"])
    return {"results": results}


@app.post("/api/settings")
def update_settings(body: SettingsIn, officer=Depends(require_officer)):
    if body.automation is not None:
        db.set_setting("automation", "on" if body.automation else "off")
        audit.log("Officer", f"Automation switched {'on' if body.automation else 'off'}", kind="human",
                  approved_by=officer["display_name"])
    if body.llm_mode in ("rules", "ollama", "groq"):
        db.set_setting("llm_mode", body.llm_mode)
        if body.llm_mode == "ollama":
            llm.warm_up()
        audit.log("Officer", f"LLM mode set to {body.llm_mode}", kind="human", approved_by=officer["display_name"])
    if body.listen_llm is not None:
        db.set_setting("listen_llm", "on" if body.listen_llm else "off")
    if body.ollama_model is not None and body.ollama_model.replace(":", "").replace(".", "").replace("-", "").isalnum():
        db.set_setting("ollama_model", body.ollama_model)
    if body.planner_scope in ("off", "judgment", "all"):
        db.set_setting("planner_scope", body.planner_scope)
        audit.log("Officer", f"Planner scope set to {body.planner_scope}", kind="human", approved_by=officer["display_name"])
    if body.auto_field is not None:
        db.set_setting("auto_field", "on" if body.auto_field else "off")
    events.publish("changed", {"what": "settings"})
    return {"automation": db.automation_on(), "llm": llm.status(), "auto_field": db.get_setting("auto_field")}


class ReplayIn(BaseModel):
    action: str
    speed: float | None = None


@app.post("/api/replay")
def replay_control(body: ReplayIn, officer=Depends(require_officer)):
    from . import replay
    speed = body.speed if body.speed in (1, 5, 10, 30) else None
    if body.action == "start":
        replay.start(speed or 10)
    elif body.action == "pause":
        replay.pause()
    elif body.action == "resume":
        replay.resume(speed)
    elif body.action == "speed" and speed:
        replay.set_speed(speed)
    elif body.action == "reset":
        replay.stop()
        orchestrator.reset()
    else:
        raise HTTPException(400, "Unknown replay action")
    return replay.status()


@app.post("/api/reset")
def reset(officer=Depends(require_officer)):
    from . import replay
    replay.stop()
    orchestrator.reset()
    return {"ok": True}


@app.get("/api/stream")
async def stream(request: Request, phone: str | None = None, team: str | None = None):
    if team:
        auth.require_team(request, team)
    elif not phone:
        auth.require_officer(request)
    reporter_id = None
    if phone:
        r = db.one("SELECT id FROM reporters WHERE phone = ?", (phone,))
        reporter_id = r["id"] if r else None

    def accept(kind, data):
        if kind == "message":
            nonlocal reporter_id
            if phone and reporter_id is None:
                r = db.one("SELECT id FROM reporters WHERE phone = ?", (phone,))
                reporter_id = r["id"] if r else None
            return phone is not None and data.get("reporter_id") == reporter_id
        if kind == "team_message":
            return team is not None and data.get("team_id") == team
        # Only the officer's full stream carries agent activity; citizens and teams just hear "something changed".
        return (phone is None and team is None) or kind == "changed"

    queue = events.subscribe(accept)

    async def gen():
        try:
            yield "retry: 2000\n\n"
            last_ping = time.time()
            while not await request.is_disconnected():
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=10)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    pass
                if time.time() - last_ping > 10:
                    yield ": ping\n\n"
                    last_ping = time.time()
        finally:
            events.unsubscribe(queue)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# When the frontend has been built, serve it from the same port so a single
# tunnel URL works for the dashboard and the citizen chat.
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        file = FRONTEND_DIST / path
        if path and file.is_file():
            return FileResponse(file)
        return FileResponse(FRONTEND_DIST / "index.html")
