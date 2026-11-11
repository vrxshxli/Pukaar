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
        self._rebalance_medic()
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
        needs_medic = self._needs_medic(ticket)
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
        for pre in db.query("SELECT id FROM approvals WHERE kind = 'preposition' AND status = 'pending' AND team_id = ?",
                            (team["id"],)):
            approvals.supersede(pre["id"], f"{team['name']} is needed for {ticket['id']}")
        if ticket["status"] == "open":
            tickets.touch(ticket["id"], status="proposed")
        self.log(f"Dispatch proposed {team['name']} for {ticket['id']} ({ticket['priority']}): " + "; ".join(why),
                 ticket_id=ticket["id"])
        return approval

    def _needs_medic(self, ticket):
        return bool(MEDICAL_NEEDS & set(filter(None, (ticket["medical"] or "").split(", "))))

    def _rebalance_medic(self):
        """New details can arrive after a proposal. If a medical ticket was proposed a boat
        without a medic while the medic boat waits on a non-medical proposal, swap them."""
        pending = db.query("""SELECT a.id, a.team_id, a.ticket_id FROM approvals a
                              WHERE a.kind = 'dispatch' AND a.status = 'pending'""")
        decoded = [(a, tickets.get(a["ticket_id"]), teams.get(a["team_id"])) for a in pending]
        needy = [(a, t) for a, t, tm in decoded if self._needs_medic(t) and "medic" not in tm["skills"]]
        spare = [(a, t) for a, t, tm in decoded if not self._needs_medic(t) and "medic" in tm["skills"]]
        if not needy:
            return
        medic_free = [f for f in teams.list_free_teams(kind="boat") if "medic" in f["skills"]]
        if not spare and not medic_free:
            return
        a, t = needy[0]
        approvals.supersede(a["id"], f"{t['id']} now needs a medic")
        tickets.touch(t["id"], status="open")
        if spare and not medic_free:
            b, other = spare[0]
            approvals.supersede(b["id"], f"the medic boat is needed for {t['id']}")
            tickets.touch(other["id"], status="open")
        self.propose_for(tickets.get(t["id"]))

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
