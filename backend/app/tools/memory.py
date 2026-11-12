"""Memory the Planner can read. Every tool here is read-only and phone-free.

Short-term  memory_ticket_context   this family's ticket, its reports and the conversation
Long-term   memory_area             blocked lanes (area memory), watch zones, field reports
            memory_household        the household registry (who lives where, who is vulnerable)
            memory_camps            relief camps, capacity and needs
Episodic    memory_episodes         past decisions and their outcomes from the audit log
"""
from .. import db, scenario
from . import geo
from .registry import tool


def _ticket_row(ticket_id):
    from . import tickets
    return tickets.get(ticket_id) if ticket_id else None


@tool("memory_ticket_context",
      "Short-term memory: one ticket (or the tickets of one reporter) with its linked reports and the latest messages. Read-only.",
      {"type": "object", "properties": {"ticket_id": {"type": "string"}, "reporter_id": {"type": "integer"}}})
def memory_ticket_context(ticket_id=None, reporter_id=None):
    ids = []
    if ticket_id:
        ids = [ticket_id]
    elif reporter_id is not None:
        ids = [r["ticket_id"] for r in db.query(
            """SELECT DISTINCT ticket_id FROM ticket_reports WHERE reporter_id = ? ORDER BY ticket_id DESC LIMIT 3""",
            (reporter_id,))]
    out = []
    for tid in ids:
        t = _ticket_row(tid)
        if not t:
            continue
        reports = db.query("""SELECT m.text, r.language, tr.reason FROM ticket_reports tr
                              JOIN reports r ON r.id = tr.report_id JOIN messages m ON m.id = r.message_id
                              WHERE tr.ticket_id = ? ORDER BY tr.rowid DESC LIMIT 5""", (tid,))
        out.append({"ticket_id": tid, "title": t["title"], "status": t["status"], "priority": t["priority"],
                    "score": t["priority_score"], "reasons": t["reasons"], "people": t["people"],
                    "area": t["area"], "team_id": t["team_id"], "reports": reports})
    thread = []
    if reporter_id is not None:
        thread = db.query("""SELECT direction, text, kind FROM messages WHERE reporter_id = ?
                             ORDER BY id DESC LIMIT 6""", (reporter_id,))
    return {"tickets": out, "conversation": list(reversed(thread))}


@tool("memory_area",
      "Long-term area memory: lanes reported blocked (with confirmations), watch zones and recent road or power reports. Read-only.",
      {"type": "object", "properties": {}})
def memory_area():
    blocked = [{"road": r["ref"], "source": r["source"], "confirmations": r["confirmations"], "since": r["created_at"]}
               for r in db.query("""SELECT * FROM area_events WHERE kind = 'road_blocked' ORDER BY id DESC""")
               if r["ref"] in geo.blocked_roads()]
    zones = [z["name"] for z in db.loads(db.get_setting("watch_zones"), [])]
    field = db.query("""SELECT id, title, area FROM tickets WHERE kind = 'info' ORDER BY created_at DESC LIMIT 5""")
    incident = db.one("SELECT level, status, note FROM incidents ORDER BY id LIMIT 1")
    return {"blocked_roads": blocked, "watch_zones": zones, "field_reports": field, "incident": incident}


@tool("memory_household",
      "Long-term memory: search the household registry by family name, lane or landmark. Returns members and status, never phone numbers. Read-only.",
      {"type": "object", "properties": {"name": {"type": "string"}, "lane": {"type": "string"},
                                        "landmark": {"type": "string"}}})
def memory_household(name=None, lane=None, landmark=None):
    out = []
    for h in scenario.households():
        if name and name.lower() not in (h.get("name", "") + " " + h.get("head", "")).lower():
            continue
        if lane and (h.get("lane") or "").lower() != lane.lower():
            continue
        if landmark and h.get("landmark") != landmark:
            continue
        live = db.one("SELECT status, safe_camp FROM households WHERE id = ?", (h["id"],)) or {}
        out.append({"household_id": h["id"], "name": h["name"], "lane": h.get("lane"), "landmark": h.get("landmark"),
                    "members": [{k: m.get(k) for k in ("name", "age", "note") if m.get(k) is not None} for m in h["members"]],
                    "status": live.get("status") or h.get("status"), "safe_camp": live.get("safe_camp")})
        if len(out) >= 5:
            break
    return {"households": out}


@tool("memory_camps", "Long-term memory: relief camps with occupancy, capacity and needs. Read-only.",
      {"type": "object", "properties": {}})
def memory_camps():
    return {"camps": [dict(c, needs=db.loads(c["needs"], [])) for c in db.query("SELECT * FROM camps")]}


@tool("memory_episodes",
      "Episodic memory: past decisions and outcomes (merges, dispatches, reroutes, rumours held, families made safe), newest first. Filter by words or ticket. Read-only.",
      {"type": "object", "properties": {"query": {"type": "string", "description": "words to look for, e.g. 'Lane 6' or 'rerouted'"},
                                        "ticket_id": {"type": "string"}, "limit": {"type": "integer"}}})
def memory_episodes(query=None, ticket_id=None, limit=6):
    sql = "SELECT at, agent, summary, ticket_id FROM audit_log WHERE kind IN ('action', 'human', 'agent_done')"
    params = []
    if ticket_id:
        sql += " AND ticket_id = ?"
        params.append(ticket_id)
    for word in (query or "").split()[:4]:
        sql += " AND summary LIKE ?"
        params.append(f"%{word}%")
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(max(1, min(int(limit or 6), 12)))
    return {"episodes": db.query(sql, tuple(params))}


MEMORY_TOOLS = ["memory_ticket_context", "memory_area", "memory_household", "memory_camps", "memory_episodes"]
