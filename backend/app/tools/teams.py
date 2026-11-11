"""Rescue teams and their routes.

A team only moves to 'assigned' or 'en_route' when it carries an approved
dispatch approval. Agents can read teams and plan routes, but cannot send one.
"""
from .. import db, events
from . import approvals, geo
from .registry import tool

MAX_HOURS = 8.0
GATED = ("assigned", "en_route", "repositioning")


def get(team_id):
    row = db.one("SELECT * FROM teams WHERE id = ?", (team_id,))
    if row:
        row["skills"] = db.loads(row["skills"], [])
    return row


def all_teams():
    rows = db.query("SELECT * FROM teams ORDER BY id")
    for r in rows:
        r["skills"] = db.loads(r["skills"], [])
        r["route"] = active_route(r["id"])
    return rows


def has_pending_proposal(team_id):
    return db.one("SELECT 1 FROM approvals WHERE team_id = ? AND status = 'pending' AND kind IN ('dispatch','preposition')",
                  (team_id,)) is not None


@tool("list_free_teams",
      "List rescue teams that are free right now, with their skills, location and hours on duty.",
      {"type": "object", "properties": {"kind": {"type": "string", "enum": ["boat", "van"]}}})
def list_free_teams(kind=None, include_proposed=False):
    out = []
    for t in all_teams():
        if t["status"] != "free" or (kind and t["kind"] != kind):
            continue
        if t["hours_on_duty"] >= MAX_HOURS:
            continue
        if not include_proposed and has_pending_proposal(t["id"]):
            continue
        out.append({"id": t["id"], "name": t["name"], "kind": t["kind"], "skills": t["skills"],
                    "node": t["node"], "hours_on_duty": t["hours_on_duty"]})
    return out


def set_status(team_id, status, approval=None, ticket_id=None, **extra):
    """The single place a team's status changes."""
    if status in GATED:
        kind = "preposition" if status == "repositioning" else "dispatch"
        approvals.require_approved(approval, kind, team_id=team_id,
                                   ticket_id=ticket_id if kind == "dispatch" else None)
    values = {"status": status, **extra}
    if ticket_id is not None or status == "free":
        values["ticket_id"] = ticket_id
    db.update("teams", "id", team_id, **values)
    events.publish("changed", {"what": "teams", "team_id": team_id})


def active_route(team_id):
    row = db.one("SELECT * FROM routes WHERE team_id = ? AND status IN ('planned','active') ORDER BY id DESC LIMIT 1",
                 (team_id,))
    if row:
        for k in ("nodes", "coords", "roads"):
            row[k] = db.loads(row[k], [])
    return row


def save_route(team_id, ticket_id, route, status="planned"):
    db.execute("UPDATE routes SET status = 'replaced' WHERE team_id = ? AND status IN ('planned','active')", (team_id,))
    return db.insert("routes", team_id=team_id, ticket_id=ticket_id, nodes=route["nodes"], coords=route["coords"],
                     roads=route["roads"], length_m=route["length_m"], eta_min=route["eta_min"], status=status,
                     progress=0, created_at=db.now_iso())


@tool("replan_routes",
      "Recompute every active route that uses a road that is now blocked.",
      {"type": "object", "properties": {"road": {"type": "string"}}})
def replan_routes(road=None):
    changed = []
    blocked = geo.blocked_roads()
    for r in db.query("SELECT * FROM routes WHERE status IN ('planned','active')"):
        roads = db.loads(r["roads"], [])
        if not set(roads) & set(blocked):
            continue
        team = get(r["team_id"])
        start = team["node"] if r["status"] == "planned" else nearest_route_node(r, team)
        nodes = db.loads(r["nodes"], [])
        new = geo.compute_route(start, nodes[-1], kind=team["kind"], blocked=blocked)
        if not new["found"]:
            changed.append({"team_id": team["id"], "ticket_id": r["ticket_id"], "found": False})
            continue
        status = r["status"]
        save_route(team["id"], r["ticket_id"], new, status=status)
        if status == "active":
            db.update("teams", "id", team["id"], node=start)
        changed.append({"team_id": team["id"], "team": team["name"], "ticket_id": r["ticket_id"], "found": True,
                        "old_eta": r["eta_min"], "eta_min": new["eta_min"], "summary": new["summary"],
                        "avoids": [b for b in blocked if b in roads]})
    if changed:
        events.publish("changed", {"what": "teams"})
    return {"replanned": changed}


def nearest_route_node(route, team):
    """The route node the team is closest to right now, where a new route can start."""
    nodes = db.loads(route["nodes"], [])
    return min(nodes, key=lambda n: geo.haversine_m(team["lat"], team["lng"],
                                                    geo.nodes()[n]["lat"], geo.nodes()[n]["lng"]))
