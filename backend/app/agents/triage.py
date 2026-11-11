"""Triage: one ticket per family, an explainable priority, and a Verify lane."""
from .. import db, llm
from ..tools import approvals, tickets
from .base import Agent

SAFE_MATCH_AT = 0.5


class Triage(Agent):
    name = "Triage"
    tools = ["find_similar_tickets", "create_ticket", "merge_into_ticket", "score_priority", "flag_for_verification"]

    def run(self, event):
        report_id, fields = event["report_id"], event["fields"]
        if event.get("followup_answer") and event.get("ticket_id"):
            return self._refresh(event["ticket_id"], report_id)
        intent = fields["intent"]
        if intent == "rumour":
            return self._rumour(report_id, fields)
        if intent in ("road_report", "power_report"):
            return self._field_report(report_id, fields)
        if intent == "supplies":
            return self._needs_ticket(report_id, fields, kind="supplies")
        if intent in ("rescue", "welfare"):
            return self._needs_ticket(report_id, fields, kind=intent)
        if intent == "safe_report":
            return self._safe_report(report_id)
        return {"action": "none"}

    def _needs_ticket(self, report_id, fields, kind):
        embed = llm.similarity if llm.mode() == "ollama" else None
        candidates = self.call("find_similar_tickets", summary="Triage looked for existing tickets about this family",
                               report_id=report_id, embed_fn=embed)
        candidates = [c for c in candidates if self._same_kind(c, kind)]
        best = candidates[0] if candidates else None

        if best and best["status"] in ("safe", "closed") and best["score"] >= SAFE_MATCH_AT and \
                self._identity_evidence(best, fields):
            report = db.one("SELECT * FROM reports WHERE id = ?", (report_id,))
            tickets.link_report(best["ticket_id"], report, "repost about a family already safe", best["score"])
            self.log(f"Triage matched a repost to {best['ticket_id']} ({best['title']}), already safe: "
                     + ", ".join(best["reasons"]), ticket_id=best["ticket_id"])
            return {"action": "already_safe", "ticket_id": best["ticket_id"]}

        if best and best["score"] >= tickets.AUTO_MERGE_AT and best["status"] not in ("safe", "closed"):
            return self._merge(report_id, best)

        created = self.call("create_ticket", summary=f"Triage opened a {kind} ticket", report_id=report_id, kind=kind)
        ticket_id = created["ticket_id"]
        scored = self.call("score_priority", summary=f"Triage scored {ticket_id}", ticket_id=ticket_id)
        self.log(f"Triage opened {ticket_id} as {scored['priority']}: " + ", ".join(scored["reasons"] or ["no risk factors yet"]),
                 ticket_id=ticket_id)

        if best and best["score"] >= tickets.SUGGEST_MERGE_AT and best["status"] not in ("safe", "closed"):
            self._suggest_merge(ticket_id, best)
        return {"action": "created", "ticket_id": ticket_id, "priority": scored["priority"]}

    @staticmethod
    def _identity_evidence(candidate, fields):
        """Only call something a repost about a rescued family when we know it is that family.
        A new family on the same lane must never be told they were already rescued."""
        strong = {"same sender", "same family name", "matches the household registry"}
        return bool(strong & set(candidate["reasons"])) or bool(fields.get("repost") and fields.get("name"))

    @staticmethod
    def _same_kind(candidate, kind):
        t = tickets.get(candidate["ticket_id"])
        if kind == "supplies":
            return t["kind"] == "supplies"
        return t["kind"] in ("rescue", "welfare")

    def _merge(self, report_id, best):
        languages = [r["language"] for r in db.query(
            """SELECT r.language FROM reports r JOIN ticket_reports tr ON tr.report_id = r.id
               WHERE tr.ticket_id = ?""", (best["ticket_id"],))]
        this_lang = db.one("SELECT language FROM reports WHERE id = ?", (report_id,))["language"]
        reason = tickets.merge_reason_text(best["reasons"], languages + [this_lang])
        merged = self.call("merge_into_ticket", summary=f"Triage merged a report into {best['ticket_id']}",
                           report_id=report_id, ticket_id=best["ticket_id"], reason=reason, confidence=best["score"])
        before = tickets.get(best["ticket_id"])["priority"]
        scored = self.call("score_priority", summary=f"Triage re-scored {best['ticket_id']}", ticket_id=best["ticket_id"])
        self.log(f"Triage merged {merged['reports']} reports into {best['ticket_id']}: {reason}"
                 + (f". Priority now {scored['priority']}" if scored["priority"] != before else ""),
                 ticket_id=best["ticket_id"])
        return {"action": "merged", "ticket_id": best["ticket_id"], "reports": merged["reports"],
                "reason": reason, "priority": scored["priority"]}

    def _suggest_merge(self, ticket_id, best):
        reason = ", ".join(best["reasons"])
        approvals.create_approval(
            "merge", f"Possible duplicate: merge {ticket_id} into {best['ticket_id']}?",
            ticket_id=ticket_id, payload={"into": best["ticket_id"], "score": best["score"]},
            reasons=[f"Match score {best['score']:.2f}, below the {tickets.AUTO_MERGE_AT} auto-merge bar", reason],
            agent=self.name)
        self.log(f"Triage was not sure {ticket_id} and {best['ticket_id']} are the same family "
                 f"(score {best['score']:.2f}: {reason}), so it asked the officer", ticket_id=ticket_id)

    def _refresh(self, ticket_id, report_id):
        report = db.one("SELECT * FROM reports WHERE id = ?", (report_id,))
        tickets.merge_into_ticket(report_id, ticket_id, "answer to follow-up question", 1.0)
        scored = self.call("score_priority", summary=f"Triage re-scored {ticket_id} after the follow-up answer",
                           ticket_id=ticket_id)
        return {"action": "updated", "ticket_id": ticket_id, "priority": scored["priority"], "report": report["id"]}

    def _rumour(self, report_id, fields):
        reason = tickets.check_claim(fields.get("claim")) or "Unverified claim with no official source."
        flagged = self.call("flag_for_verification", summary="Triage sent a claim to the Verify lane",
                            report_id=report_id, reason=reason)
        if not flagged["repeat"]:
            self.log(f"Triage sent {flagged['ticket_id']} to Verify: {reason}", ticket_id=flagged["ticket_id"])
        else:
            self.log(f"Triage linked another copy of the same claim to {flagged['ticket_id']}",
                     ticket_id=flagged["ticket_id"])
        return {"action": "verify", "ticket_id": flagged["ticket_id"], "reason": reason}

    def _field_report(self, report_id, fields):
        road = fields.get("road") or fields.get("lane")
        kind = "road" if fields["intent"] == "road_report" else "power"
        existing = None
        if road:
            for t in db.query("SELECT * FROM tickets WHERE kind = 'info' AND status = 'info' AND area LIKE ?",
                              (f"{road}%",)):
                existing = t
                break
        if existing:
            tickets.merge_into_ticket(report_id, existing["id"], f"same {kind} report for {road}", 0.8)
            return {"action": "info", "ticket_id": existing["id"], "road": road, "kind": kind}
        created = tickets.create_ticket(report_id, kind="info", status="info")
        tickets.touch(created["ticket_id"], title=f"{'Road' if kind == 'road' else 'Power'} report, {road or 'ward'}",
                      area=f"{road}, Shanti Nagar" if road else "Ward 12")
        self.log(f"Triage logged a {kind} report for {road or 'the ward'} as {created['ticket_id']}",
                 ticket_id=created["ticket_id"])
        return {"action": "info", "ticket_id": created["ticket_id"], "road": road, "kind": kind}

    def _safe_report(self, report_id):
        report = db.one("SELECT * FROM reports WHERE id = ?", (report_id,))
        mine = db.one("""SELECT t.* FROM tickets t JOIN ticket_reports tr ON tr.ticket_id = t.id
                         WHERE tr.reporter_id = ? AND t.status != 'closed' ORDER BY t.created_at DESC LIMIT 1""",
                      (report["reporter_id"],))
        if not mine:
            return {"action": "none"}
        tickets.link_report(mine["id"], report, "family says they are safe", 1.0)
        if mine["status"] == "safe":
            return {"action": "family_confirmed", "ticket_id": mine["id"]}
        self.log(f"Triage noted the family on {mine['id']} says they are safe; the officer can close it",
                 ticket_id=mine["id"])
        return {"action": "family_says_safe", "ticket_id": mine["id"]}
