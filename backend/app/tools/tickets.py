"""Tickets: create, match, merge, score and change status.

Status changes that matter for safety (downgrading a P1, closing without the
family) go through `approvals.require_approved`, so no agent can do them alone.
"""
import random
from datetime import datetime

from .. import db, events, nlp, scenario
from . import geo
from .registry import tool

AUTO_MERGE_AT = 0.6
SUGGEST_MERGE_AT = 0.35
OPEN_STATUSES = ("open", "proposed", "assigned", "en_route", "verify", "info")
P1_AT, P2_AT = 50, 30


def get(ticket_id):
    row = db.one("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    return decode(row) if row else None


def decode(row):
    for key in ("reasons", "vulnerable", "danger", "notes"):
        row[key] = db.loads(row.get(key), [])
    return row


def all_tickets():
    rows = db.query("""
        SELECT t.*, COUNT(tr.report_id) AS report_count,
               COUNT(DISTINCT tr.reporter_id) AS reporter_count
        FROM tickets t LEFT JOIN ticket_reports tr ON tr.ticket_id = t.id
        GROUP BY t.id ORDER BY t.priority_score DESC, t.created_at""")
    return [decode(r) for r in rows]


def linked_reporters(ticket_id):
    return db.query("""
        SELECT DISTINCT r.* FROM reporters r
        JOIN ticket_reports tr ON tr.reporter_id = r.id
        WHERE tr.ticket_id = ? ORDER BY tr.created_at""", (ticket_id,))


def touch(ticket_id, **values):
    values["updated_at"] = db.now_iso()
    db.update("tickets", "id", ticket_id, **values)
    events.publish("changed", {"what": "tickets", "ticket_id": ticket_id})


def next_ticket_id():
    n = int(db.get_setting("ticket_counter", "400")) + 1
    db.set_setting("ticket_counter", n)
    return f"P-{n:04d}"


def _minutes_between(a, b):
    return abs((datetime.fromisoformat(a) - datetime.fromisoformat(b)).total_seconds()) / 60


@tool("find_similar_tickets",
      "Find existing tickets that may be about the same family as a new report. Returns candidates with a match score between 0 and 1 and the reasons.",
      {"type": "object", "properties": {"report_id": {"type": "integer"}}, "required": ["report_id"]})
def find_similar_tickets(report_id, embed_fn=None):
    report = db.one("SELECT * FROM reports WHERE id = ?", (report_id,))
    fields = db.loads(report["fields"], {})
    candidates = []
    for t in db.query("SELECT * FROM tickets WHERE status != 'closed' OR household_id IS NOT NULL"):
        t = decode(t)
        score, reasons = match_score(report, fields, t, embed_fn)
        if score > 0.2:
            candidates.append({"ticket_id": t["id"], "score": round(score, 2), "reasons": reasons,
                               "status": t["status"], "title": t["title"]})
    return sorted(candidates, key=lambda c: c["score"], reverse=True)[:5]


def match_score(report, fields, ticket, embed_fn=None):
    """Add up the evidence that a report and a ticket are the same family."""
    score, reasons = 0.0, []
    same_sender = db.one(
        "SELECT 1 FROM ticket_reports WHERE ticket_id = ? AND reporter_id = ?",
        (ticket["id"], report["reporter_id"]))
    if same_sender:
        score += 0.6
        reasons.append("same sender")

    hint = fields.get("household_hint")
    if hint and ticket.get("household_id"):
        if hint == ticket["household_id"]:
            score += 0.5
            reasons.append("same family name")
        else:
            score -= 0.6
            reasons.append("different family name")

    if fields.get("landmark") and fields["landmark"] == ticket.get("landmark"):
        score += 0.35
        reasons.append("same landmark")
    t_lane = (ticket.get("area") or "").split(",")[0]
    if fields.get("lane") and t_lane:
        if fields["lane"] == t_lane:
            score += 0.25
            reasons.append(f"same lane ({t_lane})")
        elif t_lane.startswith("Lane") and fields["lane"].startswith("Lane"):
            score -= 0.4
            reasons.append("different lane")

    if report["lat"] is not None and ticket.get("lat") is not None:
        d = geo.haversine_m(report["lat"], report["lng"], ticket["lat"], ticket["lng"])
        if d < 60:
            score += 0.15
            reasons.append(f"{round(d)} m apart")
        elif d > 400:
            score -= 0.3

    if fields.get("people") and ticket.get("people") and not fields.get("people_implied"):
        if abs(fields["people"] - ticket["people"]) >= 3:
            score -= 0.2
            reasons.append("different number of people")

    if score > 0 and ticket.get("created_at"):
        minutes = _minutes_between(report["created_at"], ticket["last_update_at"] or ticket["created_at"])
        if minutes <= 30:
            score += 0.1
            reasons.append(f"{round(minutes)} minutes apart")

    if embed_fn and score > 0.2:
        first = db.one("""SELECT m.text FROM messages m JOIN reports r ON r.message_id = m.id
                          JOIN ticket_reports tr ON tr.report_id = r.id WHERE tr.ticket_id = ?
                          ORDER BY r.id LIMIT 1""", (ticket["id"],))
        msg = db.one("SELECT text FROM messages WHERE id = ?", (report["message_id"],))
        if first and msg:
            sim = embed_fn(first["text"], msg["text"])
            if sim is not None and sim > 0.75:
                score += 0.1
                reasons.append(f"similar meaning ({sim:.2f})")
    return score, reasons


def merge_reason_text(reasons, languages):
    parts = [r for r in reasons if r not in ("different lane", "different family name")]
    if len(set(languages)) > 1:
        names = " and ".join(sorted({nlp_language_name(l) for l in languages}))
        parts.insert(0, f"in {names}")
    return ", ".join(parts)


def nlp_language_name(code):
    from ..i18n import LANGUAGE_NAMES
    return LANGUAGE_NAMES.get(code, code)


@tool("create_ticket",
      "Open a new ticket from a report.",
      {"type": "object", "properties": {"report_id": {"type": "integer"}, "kind": {"type": "string"}},
       "required": ["report_id"]})
def create_ticket(report_id, kind="rescue", status="open", verify_reason=None):
    report = db.one("SELECT * FROM reports WHERE id = ?", (report_id,))
    fields = db.loads(report["fields"], {})
    ticket_id = next_ticket_id()
    now = db.now_iso()
    lane = fields.get("lane")
    household = scenario.household_by_id(fields.get("household_hint")) if fields.get("household_hint") else None
    title = fields.get("name") or _default_title(kind, fields, lane)
    db.insert("tickets", id=ticket_id, title=title,
              area=f"{lane}, Shanti Nagar" if lane else "Location unknown",
              landmark=fields.get("landmark"), lat=report["lat"], lng=report["lng"], kind=kind,
              priority="P3", priority_score=0, reasons=[], status=status,
              people=fields.get("people"), vulnerable=fields.get("vulnerable", []),
              medical=", ".join(fields.get("medical", [])) or None,
              water_level=fields.get("water_level"), danger=fields.get("danger", []),
              battery=fields.get("battery"), rising=1 if fields.get("rising") else 0, verify_reason=verify_reason,
              household_id=household["id"] if household else None,
              otp=f"{random.Random(ticket_id).randint(1000, 9999)}",
              created_at=now, updated_at=now, last_update_at=now, notes=[])
    link_report(ticket_id, report, "first report", 1.0)
    events.publish("changed", {"what": "tickets", "ticket_id": ticket_id})
    return {"ticket_id": ticket_id, "title": title}


def _default_title(kind, fields, lane):
    where = lane or "unknown location"
    if kind == "supplies":
        return f"Supplies needed, {where}"
    if kind == "verify":
        return {"dam_burst": "“Dam has burst” claim", "camp_flooded": "“Camp 3 flooded” claim",
                "power_cut_days": "“Power cut for 3 days” claim", "army_vip": "“Boats only for VIPs” claim",
                "whole_area_drown": "“Whole area will drown” claim"}.get(fields.get("claim"), "Unverified claim")
    if kind == "info":
        return f"Field report, {where}"
    if kind == "welfare":
        return f"Welfare check, {where}"
    if "elderly" in fields.get("vulnerable", []) and "child" in fields.get("vulnerable", []):
        return f"Elder and child, {where}"
    return f"Household, {where}"


def link_report(ticket_id, report, reason, confidence):
    db.execute("""INSERT OR IGNORE INTO ticket_reports
                  (ticket_id, report_id, reporter_id, reason, confidence, created_at)
                  VALUES (?, ?, ?, ?, ?, ?)""",
               (ticket_id, report["id"], report["reporter_id"], reason, confidence, db.now_iso()))
    db.update("reports", "id", report["id"], ticket_id=ticket_id)


@tool("merge_into_ticket",
      "Merge a report into an existing ticket and fill in any details the ticket was missing.",
      {"type": "object", "properties": {
          "report_id": {"type": "integer"}, "ticket_id": {"type": "string"},
          "reason": {"type": "string"}, "confidence": {"type": "number"}},
       "required": ["report_id", "ticket_id", "reason"]})
def merge_into_ticket(report_id, ticket_id, reason, confidence=1.0):
    report = db.one("SELECT * FROM reports WHERE id = ?", (report_id,))
    fields = db.loads(report["fields"], {})
    ticket = get(ticket_id)
    link_report(ticket_id, report, reason, confidence)
    updates = {"last_update_at": db.now_iso()}
    # Fill gaps and combine lists. We never lower what we already know.
    if fields.get("people") and (not ticket["people"] or
                                 (not fields.get("people_implied") and fields["people"] > ticket["people"])):
        updates["people"] = fields["people"]
    updates["vulnerable"] = sorted(set(ticket["vulnerable"]) | set(fields.get("vulnerable", [])))
    updates["danger"] = sorted(set(ticket["danger"]) | set(fields.get("danger", [])))
    medical = set(filter(None, (ticket["medical"] or "").split(", "))) | set(fields.get("medical", []))
    updates["medical"] = ", ".join(sorted(medical)) or None
    updates["water_level"] = higher_water(ticket["water_level"], fields.get("water_level"))
    if fields.get("battery") is not None:
        updates["battery"] = fields["battery"]
    if fields.get("rising"):
        updates["rising"] = 1
    if fields.get("household_hint") and not ticket["household_id"]:
        updates["household_id"] = fields["household_hint"]
        updates["title"] = fields["name"]
    elif fields.get("name") and ticket["title"].startswith(("Household", "Elder and child")):
        updates["title"] = fields["name"]
    if ticket["lat"] is None and report["lat"] is not None:
        updates.update(lat=report["lat"], lng=report["lng"], landmark=fields.get("landmark"),
                       area=f"{fields.get('lane')}, Shanti Nagar")
    elif fields.get("landmark") and not ticket["landmark"]:
        updates["landmark"] = fields["landmark"]
    touch(ticket_id, **updates)
    count = db.one("SELECT COUNT(*) AS n FROM ticket_reports WHERE ticket_id = ?", (ticket_id,))["n"]
    return {"ticket_id": ticket_id, "reports": count}


WATER_ORDER = [None, "ankle", "knee", "entering", "waist", "chest", "neck", "roof"]


def higher_water(a, b):
    return a if WATER_ORDER.index(a if a in WATER_ORDER else None) >= WATER_ORDER.index(b if b in WATER_ORDER else None) else b


@tool("score_priority",
      "Score a ticket's priority (P1, P2, P3) with an additive rule set and return the reasons.",
      {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]})
def score_priority(ticket_id):
    t = get(ticket_id)
    reports = db.one("SELECT COUNT(DISTINCT reporter_id) AS n FROM ticket_reports WHERE ticket_id = ?", (ticket_id,))["n"]
    score, reasons = priority_rules(t, reports)
    priority = "P1" if score >= P1_AT else "P2" if score >= P2_AT else "P3"
    # An agent may raise a P1 but never lower one; that needs the officer.
    if t["priority"] == "P1" and priority != "P1" and t["priority_score"]:
        priority, score = "P1", max(score, t["priority_score"])
    if t["kind"] in ("verify", "info"):
        priority = "P3"
    touch(ticket_id, priority=priority, priority_score=score, reasons=reasons)
    return {"ticket_id": ticket_id, "priority": priority, "score": score, "reasons": reasons}


def priority_rules(t, reporter_count=1):
    score, reasons = 10, []

    def add(points, reason):
        nonlocal score
        score += points
        reasons.append(reason)

    water = t["water_level"]
    water_points = {"roof": (25, "On the roof"), "neck": (35, "Water at neck height"),
                    "chest": (30, "Water at chest height"), "waist": (20, "Water at waist height"),
                    "knee": (12, "Water at knee height"), "entering": (15, "Water entering the house"),
                    "ankle": (5, "Water at ankle height")}
    if water in water_points:
        add(*water_points[water])
    if t.get("rising"):
        add(8, "Water rising")
    vulnerable = set(t["vulnerable"])
    medical = set(filter(None, (t["medical"] or "").split(", ")))
    household = scenario.household_by_id(t["household_id"]) if t["household_id"] else None
    if "elderly" in vulnerable:
        age = next((m["age"] for m in household["members"] if m.get("age", 0) >= 60), None) if household else None
        add(15, f"Elder, {age}" if age else "Elderly person")
    if "child" in vulnerable:
        small = household and any(m.get("age", 99) <= 5 for m in household["members"])
        add(15 if small else 12, "Small child" if small else "Child")
    if "pregnant" in vulnerable:
        add(15, "Pregnant woman")
    if "disabled" in vulnerable:
        add(15, "Cannot walk unaided")
    medical_points = {"unconscious": (40, "Someone unconscious"), "breathing": (35, "Breathing trouble"),
                      "dialysis": (25, "Needs dialysis"), "injured": (20, "Injured person"),
                      "fever": (10, "Child with fever" if "child" in vulnerable else "Fever"),
                      "chronic": (8, "Chronic illness, needs medicine")}
    for key, (points, reason) in medical_points.items():
        if key in medical:
            add(points, reason)
    for d in t["danger"]:
        add(30, {"gas": "Gas leak reported", "fire": "Fire reported", "electrical": "Live wire in water"}.get(d, d))
    if t["battery"] is not None and t["battery"] <= 20:
        add(8, f"Phone at {t['battery']}%")
    if t["people"] and t["people"] >= 5:
        add(8, f"{t['people']} people")
    if t["kind"] == "welfare":
        add(15, "No contact, welfare check")
    if reporter_count >= 3:
        add(5, f"{reporter_count} separate reporters")
    if t["kind"] == "supplies":
        score = min(score, P2_AT - 1)
        reasons.insert(0, "Supplies request")
    return score, reasons


@tool("flag_for_verification",
      "Send a claim that contradicts sensor or alert data to the Verify lane, with the reason.",
      {"type": "object", "properties": {"report_id": {"type": "integer"}, "reason": {"type": "string"}},
       "required": ["report_id", "reason"]})
def flag_for_verification(report_id, reason):
    report = db.one("SELECT * FROM reports WHERE id = ?", (report_id,))
    fields = db.loads(report["fields"], {})
    # Repeats of the same rumour join one Verify ticket instead of piling up.
    existing = None
    if fields.get("claim"):
        for t in db.query("SELECT * FROM tickets WHERE kind = 'verify' AND status = 'verify'"):
            first = db.one("""SELECT r.fields FROM reports r JOIN ticket_reports tr ON tr.report_id = r.id
                              WHERE tr.ticket_id = ? ORDER BY r.id LIMIT 1""", (t["id"],))
            if first and db.loads(first["fields"], {}).get("claim") == fields["claim"]:
                existing = t
                break
    if existing:
        link_report(existing["id"], report, "same claim repeated", 0.9)
        touch(existing["id"], last_update_at=db.now_iso())
        return {"ticket_id": existing["id"], "repeat": True}
    created = create_ticket(report_id, kind="verify", status="verify", verify_reason=reason)
    score_priority(created["ticket_id"])
    return {"ticket_id": created["ticket_id"], "repeat": False}


def check_claim(claim):
    """Compare a claim with the river gauge and the camp list. Returns a reason if it contradicts them."""
    s = scenario.sensors()
    now = db.now_game().strftime("%H:%M")
    reading = s["readings"][0]
    for r in s["readings"]:
        if _clock_order(r["time"]) <= _clock_order(now):
            reading = r
    if claim in ("dam_burst", "whole_area_drown"):
        if reading["level_m"] < s["danger_level_m"]:
            return (f"Contradicts the river gauge: Mithi at {reading['level_m']} m at {reading['time']}, "
                    f"below the {s['danger_level_m']} m danger level. No dam failure in the alert feed.")
    if claim == "camp_flooded":
        return "Contradicts the camp list: Camp 3 is open and reporting normally."
    if claim in ("power_cut_days", "army_vip"):
        return "No official source for this claim in the alert feed or ward notices."
    return None


def _clock_order(hhmm):
    h, m = (int(x) for x in hhmm.split(":"))
    return (h + 24 if h < 12 else h) * 60 + m


def set_status(ticket_id, status, by="agent", approval=None):
    """Change a ticket's status. Closing without the family needs an approval."""
    from . import approvals
    ticket = get(ticket_id)
    if status == "closed" and by != "family":
        approvals.require_approved(approval, "close", ticket_id=ticket_id)
    touch(ticket_id, status=status, last_update_at=db.now_iso())
    return {"ticket_id": ticket_id, "from": ticket["status"], "to": status}


def downgrade(ticket_id, priority, approval):
    from . import approvals
    approvals.require_approved(approval, "downgrade", ticket_id=ticket_id)
    touch(ticket_id, priority=priority)


GENERIC_TITLES = ("Household,", "Elder and child,", "Welfare check,")


def public_title(ticket):
    """A family name if we have one; never a lane or landmark."""
    title = ticket["title"] or ""
    return "Family (name not given)" if title.startswith(GENERIC_TITLES) or "Lane" in title else title


def public_status(ticket):
    """What the family lookup page may show: status and camp only."""
    camp = scenario.camp_by_id(ticket["safe_camp"]) if ticket.get("safe_camp") else None
    return {
        "title": public_title(ticket),
        "ticket_id": ticket["id"],
        "status": ticket["status"],
        "safe_at": ticket.get("safe_at"),
        "camp": camp["name"] if camp else None,
        "updated_at": ticket.get("updated_at"),
    }


@tool("escalate_danger",
      "Raise a ticket's priority because of a danger (gas, fire, electrical, unconscious person) and note it for the rescue team.",
      {"type": "object", "properties": {"ticket_id": {"type": "string"}, "danger": {"type": "string"}},
       "required": ["ticket_id", "danger"]})
def escalate_danger(ticket_id, danger):
    t = get(ticket_id)
    note = f"Danger for the rescue team: {danger}"
    values = {"notes": t["notes"] + [note], "last_update_at": db.now_iso()}
    if danger in ("gas", "fire", "electrical"):
        values["danger"] = sorted(set(t["danger"]) | {danger})
    if danger in ("unconscious", "breathing"):
        medical = set(filter(None, (t["medical"] or "").split(", "))) | {danger}
        values["medical"] = ", ".join(sorted(medical))
    touch(ticket_id, **values)
    return score_priority(ticket_id)
