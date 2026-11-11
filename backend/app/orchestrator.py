"""The planner. Every event comes here, and the planner decides which agents
run and in what order, writing each plan to the audit log.

Events are handled one at a time under a lock, so the replay, the citizen
chat, the volunteer screens and the officer never step on each other.
"""
import threading

from . import db, events, nlp, scenario, simulation
from .agents.dispatch import Dispatch
from .agents.listen import Listen
from .agents.loop import Loop, camp_name
from .agents.saathi import Saathi, ticket_for
from .agents.triage import Triage
from .agents.watch import Watch
from .i18n import t
from .tools import approvals, audit, geo, messaging, teams, tickets

_lock = threading.RLock()

listen, triage, dispatch, loop, saathi, watch = Listen(), Triage(), Dispatch(), Loop(), Saathi(), Watch()


def plan(summary, ticket_id=None):
    audit.log("Planner", summary, kind="plan", ticket_id=ticket_id)


def handle_message(phone, text, channel="chat", name=None, area=None, meta=None):
    """A message from a citizen, through the chat page or the replay."""
    with _lock:
        language = nlp.detect_language(text)
        reporter = messaging.get_or_create_reporter(phone, name=name, language=language, channel=channel, area=area)
        message = messaging.record_incoming(reporter["id"], text, channel, language, meta=meta)
        heard = listen.run({"reporter": reporter, "message": message, "channel": channel})
        fields = heard["fields"]
        reporter = messaging.get_or_create_reporter(phone, language=fields["language"])
        steps = ["Listen"]

        if heard["waiting"]:
            plan(f"Planner: message #{message['id']} needs a location, so Listen asked and is holding the report")
            return {"intent": fields["intent"], "waiting": True, "report_id": heard["report_id"]}

        result = _route_by_intent(reporter, heard, fields, text, steps)
        plan(f"Planner: routed message #{message['id']} ({fields['intent']}) to " + ", then ".join(steps),
             ticket_id=result.get("ticket_id"))
        return {"intent": fields["intent"], **result, "report_id": heard["report_id"]}


def _route_by_intent(reporter, heard, fields, text, steps):
    intent = fields["intent"]
    if intent in ("rescue", "welfare", "supplies", "rumour", "road_report", "power_report", "safe_report") \
            or heard.get("followup_answer"):
        decision = triage.run(heard)
        steps.append("Triage")
    else:
        decision = {"action": "none"}
    ticket_id = decision.get("ticket_id")

    if Saathi.should_answer(fields, text) and intent not in ("faq", "rumour", "status_query"):
        saathi.run({"text": text, "language": reporter["language"], "fields": fields, "reporter_id": reporter["id"],
                    "ticket_id": ticket_id or ticket_for(reporter["id"])})
        steps.append("Saathi")

    action = decision["action"]
    if action == "created":
        ask = heard.get("needs_people")
        loop.run({"type": "created", "reporter": reporter, "ticket_id": ticket_id, "ask_people": ask})
        if ask:
            listen.ask_people(heard["report_id"], ticket_id, reporter["language"], loop.ack_text(reporter, ticket_id))
            steps.append("Listen (follow-up)")
    elif action == "merged":
        loop.run({"type": "merged", "reporter": reporter, "ticket_id": ticket_id, "reports": decision["reports"]})
    elif action in ("already_safe", "verify", "info", "family_confirmed"):
        loop.run({"type": action, "reporter": reporter, **decision})
    elif intent == "faq":
        loop.run({"type": "faq", "reporter": reporter, "topic": fields.get("faq", "unknown")})
    elif intent == "status_query":
        loop.run({"type": "status_query", "reporter": reporter})
    elif intent == "other" and "Saathi" not in steps:
        loop.send_text(reporter, t("faq_unknown", reporter["language"]), kind="faq")
    if action in ("already_safe", "verify", "info", "family_confirmed", "merged", "created") or intent in ("faq", "status_query", "other"):
        steps.append("Loop")

    if action in ("created", "merged", "updated"):
        if dispatch.run():
            steps.append("Dispatch")
    return {"action": action, "ticket_id": ticket_id, "priority": decision.get("priority")}


def handle_approval(approval_id, decision, officer, team_id=None):
    """The officer approved or rejected something in the dashboard."""
    with _lock:
        approval = approvals.get(approval_id)
        if team_id and approval and approval["kind"] == "dispatch" and team_id != approval["team_id"]:
            _change_team(approval, team_id)
        approval = approvals.decide(approval_id, decision, officer)
        if approval["status"] == "approved":
            _apply(approval)
        else:
            _rejected(approval)
        dispatch.run()
        return approval


def _change_team(approval, team_id):
    team = teams.get(team_id)
    if not team or team["status"] != "free":
        raise ValueError("that team is not free")
    ticket = tickets.get(approval["ticket_id"])
    goal = approval["payload"]["goal"]
    route = geo.compute_route(team["node"], goal, kind=team["kind"])
    reasons = [f"Officer chose {team['name']}", f"{route['length_m'] / 1000:.1f} km, about {route['eta_min']} min",
               f"{team['hours_on_duty']:g} h on duty"]
    payload = {**approval["payload"], "route": route, "why_team": "; ".join(reasons)}
    approvals.change_team(approval["id"], team_id, payload, reasons, f"Send {team['name']} to {ticket['title']}?")


def _apply(approval):
    kind = approval["kind"]
    if kind == "dispatch":
        _apply_dispatch(approval)
    elif kind == "preposition":
        team = teams.get(approval["team_id"])
        route = geo.compute_route(team["node"], approval["payload"]["to_node"], kind=team["kind"])
        teams.save_route(team["id"], None, route, status="active")
        teams.set_status(team["id"], "repositioning", approval=approval)
        audit.log("Dispatch", f"{team['name']} is moving to its pre-position: {route['summary']}",
                  approved_by=approval["decided_by"])
    elif kind == "bulletin":
        _send_bulletin(approval)
    elif kind == "merge":
        _apply_merge(approval)
    elif kind == "downgrade":
        tickets.downgrade(approval["ticket_id"], approval["payload"]["priority"], approval)
    elif kind == "close":
        tickets.set_status(approval["ticket_id"], "closed", by="officer", approval=approval)
        loop.status_update(tickets.get(approval["ticket_id"]))


def _apply_dispatch(approval):
    ticket = tickets.get(approval["ticket_id"])
    team = teams.get(approval["team_id"])
    route = geo.compute_route(team["node"], approval["payload"]["goal"], kind=team["kind"])
    teams.save_route(team["id"], ticket["id"], route, status="planned")
    teams.set_status(team["id"], "assigned", approval=approval, ticket_id=ticket["id"])
    tickets.touch(ticket["id"], status="assigned", team_id=team["id"], last_update_at=db.now_iso(),
                  notes=[n for n in ticket["notes"] if n != "Waiting for a free team"])
    people = f"{ticket['people']} people" if ticket["people"] else "people count unknown"
    extra = ", ".join(ticket["vulnerable"] + ([ticket["medical"]] if ticket["medical"] else []))
    danger = (" DANGER: " + ", ".join(ticket["danger"]) + ".") if ticket["danger"] else ""
    messaging.send_team_message(team["id"],
                                f"New task, {ticket['priority']}: {ticket['title']}, {ticket['area']}. {people}"
                                f"{' (' + extra + ')' if extra else ''}.{danger} Route: {route['summary']}.",
                                ticket_id=ticket["id"])
    loop.status_update(tickets.get(ticket["id"]))


def _send_bulletin(approval):
    bulletin = db.one("SELECT * FROM bulletins WHERE approval_id = ?", (approval["id"],))
    approvals.require_approved(approval, "bulletin")
    db.update("bulletins", "id", bulletin["id"], status="sent", sent_at=db.now_iso())
    sent = 0
    for r in db.query("SELECT * FROM reporters"):
        lang = r["language"] if r["language"] in ("hi", "mr") else bulletin["language"]
        if lang == bulletin["language"] or r["language"] == "en":
            messaging.send_message(r["id"], bulletin["text"], kind="bulletin", agent="Loop")
            sent += 1
    audit.log("Loop", f"Ward bulletin ({bulletin['language'].upper()}) sent to {sent} reporters after approval",
              approved_by=approval["decided_by"])


def _apply_merge(approval):
    source, target = approval["ticket_id"], approval["payload"]["into"]
    for link in db.query("SELECT * FROM ticket_reports WHERE ticket_id = ?", (source,)):
        db.execute("DELETE FROM ticket_reports WHERE ticket_id = ? AND report_id = ?", (source, link["report_id"]))
        tickets.merge_into_ticket(link["report_id"], target, f"merged by officer from {source}", 1.0)
    tickets.touch(source, status="closed", kind="duplicate", household_id=None,
                  notes=tickets.get(source)["notes"] + [f"Merged into {target} by {approval['decided_by']}"])
    for other in db.query("SELECT id FROM approvals WHERE ticket_id = ? AND status = 'pending'", (source,)):
        approvals.supersede(other["id"], f"{source} was merged into {target}")
    tickets.score_priority(target)
    count = db.one("SELECT COUNT(*) AS n FROM ticket_reports WHERE ticket_id = ?", (target,))["n"]
    for r in tickets.linked_reporters(target):
        loop.send(r, "linked", target, count=count, ticket=target)


def _rejected(approval):
    if approval["kind"] == "dispatch":
        ticket = tickets.get(approval["ticket_id"])
        if ticket["status"] == "proposed":
            tickets.touch(ticket["id"], status="open")
    elif approval["kind"] == "bulletin":
        db.execute("UPDATE bulletins SET status = 'rejected' WHERE approval_id = ?", (approval["id"],))


def handle_volunteer(team_id, action, road=None, otp=None):
    """A volunteer tapped a button in the volunteer view."""
    with _lock:
        team = teams.get(team_id)
        if not team:
            raise ValueError("no such team")
        handler = {"accept": _accept, "blocked": _blocked, "reached": _reached, "otp": _otp,
                   "need_medic": _need_medic}[action]
        return handler(team, road=road, otp=otp)


def _approved_dispatch(team):
    return db.one("""SELECT * FROM approvals WHERE kind = 'dispatch' AND status = 'approved'
                     AND team_id = ? AND ticket_id = ? ORDER BY id DESC LIMIT 1""", (team["id"], team["ticket_id"]))


def _accept(team, **_):
    approval = _approved_dispatch(team)
    if team["status"] != "assigned":
        raise ValueError("this team has no task waiting to be accepted")
    route = teams.active_route(team["id"])
    db.update("routes", "id", route["id"], status="active", created_at=db.now_iso())
    teams.set_status(team["id"], "en_route", approval=approvals.decode(approval) if approval else None,
                     ticket_id=team["ticket_id"])
    tickets.touch(team["ticket_id"], status="en_route", last_update_at=db.now_iso())
    plan(f"Planner: {team['name']} accepted {team['ticket_id']}, so Loop tells the family", ticket_id=team["ticket_id"])
    loop.status_update(tickets.get(team["ticket_id"]))
    return {"ok": True, "status": "en_route"}


def _blocked(team, road=None, **_):
    road = geo.normalise_road_name(road or "")
    if not road:
        raise ValueError("which road is blocked?")
    plan(f"Planner: {team['name']} reported {road} blocked, so Watch updates area memory, then Dispatch replans")
    watch.road_blocked(road, source=team["name"])
    replanned = dispatch.replan(road)
    for r in replanned:
        if not r["found"]:
            continue
        messaging.send_team_message(r["team_id"], f"Noted. New route: {r['summary']}, about {r['eta_min']} min. "
                                                  f"{road} is now blocked for all teams.", ticket_id=r["ticket_id"])
        if r["ticket_id"]:
            loop.status_update(tickets.get(r["ticket_id"]), event={"rerouted": True, "road": road})
    if not any(r["team_id"] == team["id"] for r in replanned):
        messaging.send_team_message(team["id"], f"Noted. {road} is now blocked for all teams.")
    return {"ok": True, "road": road, "replanned": replanned}


def _reached(team, **_):
    if team["status"] not in ("en_route", "on_scene"):
        raise ValueError("this team is not on a rescue")
    route = teams.active_route(team["id"])
    if route:
        db.update("routes", "id", route["id"], status="done", progress=1)
        goal = geo.nodes()[route["nodes"][-1]]
        db.update("teams", "id", team["id"], lat=goal["lat"], lng=goal["lng"], node=route["nodes"][-1])
    teams.set_status(team["id"], "on_scene", ticket_id=team["ticket_id"])
    messaging.send_team_message(team["id"], "Reached. Ask the family for their OTP and enter it here.",
                                ticket_id=team["ticket_id"])
    audit.log("Dispatch", f"{team['name']} reached {team['ticket_id']}", ticket_id=team["ticket_id"])
    return {"ok": True, "status": "on_scene"}


def _otp(team, otp=None, **_):
    ticket = tickets.get(team["ticket_id"]) if team["ticket_id"] else None
    if not ticket or team["status"] not in ("en_route", "on_scene"):
        raise ValueError("this team has no family to confirm")
    if str(otp).strip() != ticket["otp"]:
        audit.log("Dispatch", f"Wrong OTP entered by {team['name']} for {ticket['id']}", ticket_id=ticket["id"])
        return {"ok": False, "error": "That OTP does not match. Ask the family to check their messages."}
    if team["status"] == "en_route":
        _reached(team)
    return complete_rescue(teams.get(team["id"]), ticket)


def complete_rescue(team, ticket):
    """OTP matched: the family is safe. The team takes them to the nearest camp."""
    start = team["node"]
    camps = []
    for c in scenario.camps():
        route = geo.compute_route(start, c["node"], kind=team["kind"])
        if route["found"]:
            camps.append((route["eta_min"], c, route))
    camps.sort(key=lambda x: x[0])
    _, camp, route = camps[0]
    now = db.now_iso()
    tickets.touch(ticket["id"], status="safe", safe_at=now, safe_camp=camp["id"], last_update_at=now)
    if ticket["household_id"]:
        db.update("households", "id", ticket["household_id"], status="safe", safe_camp=camp["id"], safe_at=now)
    if ticket["people"] and ticket["kind"] == "rescue":
        db.execute("UPDATE camps SET occupancy = occupancy + ? WHERE id = ?", (ticket["people"], camp["id"]))
    teams.save_route(team["id"], None, route, status="active")
    teams.set_status(team["id"], "returning", ticket_id=None)
    audit.log("Dispatch", f"{team['name']} confirmed {ticket['id']} by OTP; taking the family to {camp_name(camp['id'])}",
              ticket_id=ticket["id"])
    plan(f"Planner: {ticket['id']} is safe, so Loop tells all {len(tickets.linked_reporters(ticket['id']))} reporters",
         ticket_id=ticket["id"])
    loop.status_update(tickets.get(ticket["id"]))
    return {"ok": True, "status": "safe", "camp": camp["name"]}


def _need_medic(team, **_):
    ticket = tickets.get(team["ticket_id"]) if team["ticket_id"] else None
    if not ticket:
        raise ValueError("this team has no active ticket")
    tickets.escalate_danger(ticket["id"], "needs medic")
    medical = set(filter(None, (ticket["medical"] or "").split(", "))) | {"needs medic"}
    tickets.touch(ticket["id"], medical=", ".join(sorted(medical)))
    proposal = None
    if "medic" not in team["skills"]:
        proposal = dispatch.propose_for(tickets.get(ticket["id"]), support=True)
    plan(f"Planner: {team['name']} needs a medic at {ticket['id']}, so Dispatch proposed backup", ticket_id=ticket["id"])
    return {"ok": True, "proposal": proposal["id"] if proposal else None}


def tick():
    """Runs every second: alerts, team movement, stale tickets, waiting tickets."""
    with _lock:
        for action in watch.check_alerts():
            if action["type"] == "red_alert":
                plan("Planner: red alert, so Watch proposed pre-positioning and Loop drafted ward bulletins")
                loop.draft_bulletins()
        for happened in simulation.tick():
            _on_sim_event(happened)
        loop.reping_stale()
        dispatch.run()


def _on_sim_event(e):
    team = teams.get(e["team_id"])
    if e["type"] == "arrived":
        if team["status"] == "en_route":
            teams.set_status(team["id"], "on_scene", ticket_id=team["ticket_id"])
            messaging.send_team_message(team["id"], "You have arrived. Ask the family for their OTP and enter it here.",
                                        ticket_id=team["ticket_id"])
            audit.log("Dispatch", f"{team['name']} reached {team['ticket_id']}", ticket_id=team["ticket_id"])
        elif team["status"] == "repositioning":
            teams.set_status(team["id"], "free")
            audit.log("Dispatch", f"{team['name']} is in position and free for tasks")
        elif team["status"] == "returning":
            hours = round(team["hours_on_duty"] + e["trip_min"] / 60, 2)
            teams.set_status(team["id"], "free", hours_on_duty=hours)
            audit.log("Dispatch", f"{team['name']} dropped the family at camp and is free again ({hours:g} h on duty)")
    elif e["type"] == "auto_accept" and team["status"] == "assigned":
        _accept(team)
    elif e["type"] == "auto_otp" and team["status"] == "on_scene":
        ticket = tickets.get(team["ticket_id"])
        _otp(team, otp=ticket["otp"])


def reset():
    with _lock:
        db.reset()
        events.publish("changed", {"what": "all"})
