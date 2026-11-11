"""Dispatch: picks the best free team and asks the officer to approve.

Dispatch never changes a team's status. It only creates approval requests;
the team moves when the officer approves and the volunteer accepts.
"""
from .. import db, scenario
from ..tools import approvals, geo, teams, tickets
from .base import Agent

MEDICAL_NEEDS = {"unconscious", "breathing", "injured", "fever", "dialysis", "needs medic"}


class Dispatch(Agent):
    name = "Dispatch"
    tools = ["list_free_teams", "compute_route", "create_approval", "replan_routes"]

    def run(self, event=None):
        proposals = []
        for ticket in self._waiting_tickets():
            proposal = self.propose_for(ticket)
            if proposal:
                proposals.append(proposal)
        return proposals

    def _waiting_tickets(self):
        rows = db.query("""SELECT * FROM tickets WHERE status = 'open' AND kind IN ('rescue','welfare','supplies')
                           AND lat IS NOT NULL ORDER BY priority_score DESC, created_at""")
        out = []
        for t in rows:
            held = db.one("""SELECT 1 FROM approvals WHERE status = 'pending' AND ticket_id = ?
                             AND kind IN ('dispatch','merge')""", (t["id"],))
            if not held:
                out.append(tickets.decode(t))
        return out

    def propose_for(self, ticket, support=False):
        kind = "van" if ticket["kind"] == "supplies" else "boat"
        free = teams.list_free_teams(kind=kind)
        free = [f for f in free if not self._rejected_before(ticket["id"], f["id"])]
        if not free and ticket["priority"] == "P1" and kind == "boat":
            free = self._free_up_for_p1(ticket)
        if not free:
            self._note_waiting(ticket)
            return None

        goal = geo.nearest_node(ticket["lat"], ticket["lng"])
        needs_medic = bool(MEDICAL_NEEDS & set(filter(None, (ticket["medical"] or "").split(", "))))
        options = []
        for team in free:
            route = geo.compute_route(team["node"], goal, kind=kind)
            if not route["found"]:
                continue
            cost, why = self._team_cost(team, route, needs_medic, ticket)
            options.append((cost, team, route, why))
        if not options:
            self._note_waiting(ticket)
            return None
        options.sort(key=lambda o: o[0])
        _, team, route, why = options[0]

        self.call("compute_route", summary=f"Dispatch routed {team['name']} to {ticket['id']}: {route['summary']}",
                  ticket_id=ticket["id"], from_node=team["node"], to_node=goal, kind=kind)
        title = f"Send {team['name']} to {ticket['title']}?"
        payload = {"route": route, "why_team": "; ".join(why), "goal": goal, "support": support,
                   "alternatives": [{"team_id": o[1]["id"], "name": o[1]["name"], "eta_min": o[2]["eta_min"]}
                                    for o in options[1:4]]}
        approval = self.call("create_approval", summary=f"Dispatch proposed {team['name']} for {ticket['id']}",
                             ticket_id=ticket["id"], kind="dispatch", title=title, team_id=team["id"],
                             payload=payload, reasons=why, agent=self.name)
        if approval is None:
            return None
        if ticket["status"] == "open":
            tickets.touch(ticket["id"], status="proposed")
        self.log(f"Dispatch proposed {team['name']} for {ticket['id']} ({ticket['priority']}): " + "; ".join(why),
                 ticket_id=ticket["id"])
        return approval

    def _team_cost(self, team, route, needs_medic, ticket):
        has_medic = "medic" in team["skills"]
        cost = route["eta_min"]
        why = []
        if needs_medic and has_medic:
            why.append("Medic on board")
        elif needs_medic:
            cost += 20
            why.append("No medic on board (none free)")
        elif has_medic and ticket["priority"] != "P1":
            # Keep the medic boat free for the most urgent medical calls.
            cost += 6
        why.append(f"{route['length_m'] / 1000:.1f} km, about {route['eta_min']} min")
        why.append(f"{team['hours_on_duty']:g} h on duty")
        if team["hours_on_duty"] >= 6:
            cost += 6
        if route["avoids"]:
            why.append("Route avoids flooded " + ", ".join(route["avoids"]))
        return cost, why

    @staticmethod
    def _rejected_before(ticket_id, team_id):
        return db.one("""SELECT 1 FROM approvals WHERE kind = 'dispatch' AND status = 'rejected'
                         AND ticket_id = ? AND team_id = ?""", (ticket_id, team_id)) is not None

    def _free_up_for_p1(self, ticket):
        """If every boat is only proposed for lower-priority work, take one back for this P1."""
        row = db.one("""SELECT a.* FROM approvals a JOIN tickets t ON t.id = a.ticket_id
                        WHERE a.kind = 'dispatch' AND a.status = 'pending' AND t.priority != 'P1'
                        ORDER BY t.priority_score LIMIT 1""")
        if not row:
            return []
        approvals.supersede(row["id"], f"{ticket['id']} is P1 and needs this boat more")
        tickets.touch(row["ticket_id"], status="open")
        return [f for f in teams.list_free_teams(kind="boat") if f["id"] == row["team_id"]]

    def _note_waiting(self, ticket):
        notes = ticket["notes"]
        if "Waiting for a free team" not in notes:
            tickets.touch(ticket["id"], notes=notes + ["Waiting for a free team"])
            self.log(f"Dispatch: no free team for {ticket['id']} ({ticket['priority']}) yet; it stays at the top of the queue",
                     ticket_id=ticket["id"])

    def replan(self, road):
        result = self.call("replan_routes", summary=f"Dispatch checked every route that uses {road}", road=road)
        for r in result["replanned"]:
            if r["found"]:
                self.log(f"Dispatch rerouted {r['team']} for {r['ticket_id'] or 'pre-positioning'}: {r['summary']} "
                         f"(was {r['old_eta']:g} min, now {r['eta_min']:g} min)", ticket_id=r["ticket_id"])
        return result["replanned"]

    @staticmethod
    def medic_team():
        return next((t for t in scenario.teams() if "medic" in t["skills"]), None)
