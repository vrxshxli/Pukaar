"""Moves teams along their routes on the game clock.

It does not decide anything. It reports what happened (a team arrived, a
team has been waiting) and the orchestrator decides what to do about it.
"""
from datetime import datetime

from . import db, events
from .tools import geo, teams

AUTO_ACCEPT_AFTER_MIN = 1
AUTO_OTP_AFTER_MIN = 4


def auto_field():
    """In the replay, volunteers accept tasks and enter OTPs on their own."""
    return db.get_setting("auto_field", "off") == "on"


def _minutes_since(iso, now):
    return (now - datetime.fromisoformat(iso)).total_seconds() / 60


def tick():
    now = db.now_game()
    happened = []
    for route in db.query("SELECT * FROM routes WHERE status = 'active'"):
        team = teams.get(route["team_id"])
        coords = db.loads(route["coords"], [])
        progress = min(1.0, _minutes_since(route["created_at"], now) / max(route["eta_min"], 1))
        lat, lng = point_along(coords, progress)
        db.update("routes", "id", route["id"], progress=progress)
        db.update("teams", "id", team["id"], lat=lat, lng=lng)
        if progress >= 1.0:
            db.update("routes", "id", route["id"], status="done")
            db.update("teams", "id", team["id"], node=db.loads(route["nodes"], [])[-1])
            happened.append({"type": "arrived", "team_id": team["id"], "ticket_id": route["ticket_id"],
                             "team_status": team["status"], "route_id": route["id"],
                             "trip_min": route["eta_min"]})
    if auto_field():
        happened += _auto_field_actions(now)
    if happened or db.query("SELECT 1 FROM routes WHERE status = 'active' LIMIT 1"):
        events.publish("changed", {"what": "teams"})
    return happened


def _auto_field_actions(now):
    out = []
    for team in db.query("SELECT * FROM teams WHERE status IN ('assigned', 'on_scene')"):
        approval = db.one("""SELECT * FROM approvals WHERE kind = 'dispatch' AND status = 'approved'
                             AND team_id = ? AND ticket_id = ? ORDER BY id DESC LIMIT 1""",
                          (team["id"], team["ticket_id"]))
        if not approval:
            continue
        waited = _minutes_since(approval["decided_at"], now)
        if team["status"] == "assigned" and waited >= AUTO_ACCEPT_AFTER_MIN:
            out.append({"type": "auto_accept", "team_id": team["id"]})
        if team["status"] == "on_scene":
            route = db.one("SELECT * FROM routes WHERE team_id = ? AND status = 'done' ORDER BY id DESC LIMIT 1",
                           (team["id"],))
            arrived_min = _minutes_since(route["created_at"], now) - route["eta_min"] if route else 99
            if arrived_min >= AUTO_OTP_AFTER_MIN:
                out.append({"type": "auto_otp", "team_id": team["id"]})
    return out


def point_along(coords, fraction):
    """The point a given fraction of the way along a polyline."""
    if not coords:
        return None, None
    if len(coords) == 1 or fraction <= 0:
        return coords[0]
    lengths = [geo.haversine_m(*coords[i], *coords[i + 1]) for i in range(len(coords) - 1)]
    target = sum(lengths) * fraction
    for i, seg in enumerate(lengths):
        if target <= seg or i == len(lengths) - 1:
            f = 0 if seg == 0 else min(1.0, target / seg)
            a, b = coords[i], coords[i + 1]
            return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]
        target -= seg
    return coords[-1]
