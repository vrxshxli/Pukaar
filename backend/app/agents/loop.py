"""Loop: closes the circle with everyone who reported a family."""
from datetime import datetime, timedelta

from .. import db, scenario
from ..i18n import t
from ..tools import registry, tickets
from .base import Agent

STALE_AFTER_MIN = 20


def _clock(iso):
    """'2026-07-14T20:12:00' becomes '8:12 PM'."""
    return datetime.fromisoformat(iso).strftime("%I:%M %p").lstrip("0")


def camp_name(camp_id):
    camp = scenario.camp_by_id(camp_id) if camp_id else None
    return camp["name"].split(" (")[0] if camp else "a relief camp"


@registry.tool("answer_faq",
               "Answer a general question (helplines, relief camps, how to check on family) from the ward FAQ.",
               {"type": "object", "properties": {
                   "topic": {"type": "string", "enum": ["helplines", "camps", "family"]},
                   "language": {"type": "string"}}, "required": ["topic"]})
def answer_faq(topic, language="en"):
    if topic == "helplines":
        return t("faq_helplines", language)
    if topic == "camps":
        camps = "; ".join(f"{c['name']}" for c in scenario.camps())
        return t("faq_camps", language, camps=camps)
    if topic == "family":
        return t("faq_family", language)
    return t("faq_unknown", language)


@registry.tool("draft_bulletin",
               "Draft a ward bulletin in a language. It is only sent after the officer approves it.",
               {"type": "object", "properties": {"language": {"type": "string", "enum": ["en", "hi", "mr"]}},
                "required": ["language"]}, model_safe=False)
def draft_bulletin(language="mr"):
    from ..tools import approvals
    camps = ", ".join(c["name"].split(" (")[0] for c in scenario.camps())
    text = t("bulletin", language, time=_clock(db.now_iso()), camps=camps)
    approval = approvals.create_approval(
        "bulletin", f"Send ward bulletin ({language.upper()}) to all of Ward 12?",
        payload={"text": text, "language": language},
        reasons=["Red alert in effect", "Lists open camps", "No names or addresses"], agent="Loop")
    if approval is None:
        return None
    bulletin_id = db.insert("bulletins", text=text, language=language, area="Ward 12", status="draft",
                            approval_id=approval["id"], created_at=db.now_iso())
    return {"bulletin_id": bulletin_id, "approval_id": approval["id"], "text": text}


class Loop(Agent):
    name = "Loop"
    tools = ["send_message", "draft_bulletin", "answer_faq"]

    def run(self, event):
        handler = getattr(self, f"on_{event['type']}", None)
        return handler(event) if handler else None

    def send(self, reporter, key, ticket_id=None, kind="status", **values):
        text = t(key, reporter["language"], **values)
        return self.call("send_message", summary=f"Loop sent '{key}' to {reporter['phone']} in {reporter['language']}",
                         ticket_id=ticket_id, reporter_id=reporter["id"], text=text, kind=kind, agent=self.name)

    def send_text(self, reporter, text, ticket_id=None, kind="status"):
        return self.call("send_message", summary=f"Loop replied to {reporter['phone']}", ticket_id=ticket_id,
                         reporter_id=reporter["id"], text=text, kind=kind, agent=self.name)

    def on_created(self, event):
        reporter, ticket_id = event["reporter"], event["ticket_id"]
        ticket = tickets.get(ticket_id)
        if ticket["kind"] == "supplies":
            return self.send(reporter, "supplies_ack", ticket_id, ticket=ticket_id)
        if event.get("ask_people"):
            return None  # Listen sends the acknowledgement together with its question.
        return self.send(reporter, "ack_new", ticket_id, ticket=ticket_id)

    def ack_text(self, reporter, ticket_id):
        return t("ack_new", reporter["language"], ticket=ticket_id)

    def on_merged(self, event):
        ticket_id, new_reporter = event["ticket_id"], event["reporter"]
        count = event["reports"]
        for r in tickets.linked_reporters(ticket_id):
            if r["id"] == new_reporter["id"]:
                self.send(r, "ack_new", ticket_id, ticket=ticket_id)
            self.send(r, "linked", ticket_id, count=count, ticket=ticket_id)
        self.log(f"Loop told {len(tickets.linked_reporters(ticket_id))} reporters that {count} reports are linked to {ticket_id}",
                 ticket_id=ticket_id)

    def on_already_safe(self, event):
        ticket = tickets.get(event["ticket_id"])
        self.send(event["reporter"], "already_safe", ticket["id"], kind="auto_reply", title=ticket["title"],
                  time=_clock(ticket["safe_at"]), camp=camp_name(ticket["safe_camp"]))
        self.log(f"Loop auto-replied to a repost about {ticket['title']}: rescued at {_clock(ticket['safe_at'])}, "
                 f"safe at {camp_name(ticket['safe_camp'])}", ticket_id=ticket["id"])

    def on_verify(self, event):
        return self.send(event["reporter"], "verify", event["ticket_id"])

    def on_info(self, event):
        if event.get("road"):
            return self.send(event["reporter"], "road_ack", event["ticket_id"], road=event["road"])
        return self.send(event["reporter"], "info_ack", event["ticket_id"])

    def on_faq(self, event):
        reporter = event["reporter"]
        text = self.call("answer_faq", summary=f"Loop answered a {event['topic']} question",
                         topic=event["topic"], language=reporter["language"])
        return self.send_text(reporter, text, kind="faq")

    def on_status_query(self, event):
        reporter = event["reporter"]
        row = db.one("""SELECT t.* FROM tickets t JOIN ticket_reports tr ON tr.ticket_id = t.id
                        WHERE tr.reporter_id = ? ORDER BY t.created_at DESC LIMIT 1""", (reporter["id"],))
        if not row:
            return self.send_text(reporter, t("faq_unknown", reporter["language"]), kind="faq")
        return self.status_update(tickets.decode(row), only=reporter)

    def on_family_confirmed(self, event):
        ticket_id = event["ticket_id"]
        tickets.set_status(ticket_id, "closed", by="family")
        for r in tickets.linked_reporters(ticket_id):
            self.send(r, "closed", ticket_id, ticket=ticket_id)
        self.log(f"Loop closed {ticket_id}: the family confirmed they are safe", ticket_id=ticket_id)

    def on_status(self, event):
        return self.status_update(tickets.get(event["ticket_id"]), event=event)

    def status_update(self, ticket, event=None, only=None):
        """Tell every linked reporter where their ticket stands, each in their language."""
        event = event or {}
        reporters = [only] if only else tickets.linked_reporters(ticket["id"])
        team = db.one("SELECT * FROM teams WHERE id = ?", (ticket["team_id"],)) if ticket["team_id"] else None
        route = db.one("SELECT * FROM routes WHERE ticket_id = ? AND status IN ('planned','active') ORDER BY id DESC LIMIT 1",
                       (ticket["id"],))
        for i, r in enumerate(reporters):
            status = ticket["status"]
            if status in ("assigned", "en_route") and team:
                eta = round(route["eta_min"] * (1 - (route["progress"] or 0))) if route else "?"
                key = "rerouted" if event.get("rerouted") else "team_coming"
                self.send(r, key, ticket["id"], team=team["name"], eta=max(eta, 1) if eta != "?" else eta,
                          title=ticket["title"], road=event.get("road", ""))
                if status == "en_route" and not event.get("rerouted") and not only and self._is_family(r, ticket, i):
                    self.send(r, "otp", ticket["id"], otp=ticket["otp"])
            elif status == "safe":
                self.send(r, "safe", ticket["id"], title=ticket["title"], time=_clock(ticket["safe_at"]),
                          camp=camp_name(ticket["safe_camp"]))
                if self._is_family(r, ticket, i) and not only:
                    self.send(r, "confirm_safe", ticket["id"], ticket=ticket["id"])
            elif status == "closed":
                self.send(r, "closed", ticket["id"], ticket=ticket["id"])
            else:
                self.send(r, "stale", ticket["id"], ticket=ticket["id"], priority=ticket["priority"])
        if not only:
            self.log(f"Loop updated {len(reporters)} reporter(s) on {ticket['id']}: {ticket['status']}",
                     ticket_id=ticket["id"])

    @staticmethod
    def _is_family(reporter, ticket, index):
        """The OTP goes to the family itself: the first reporter, or the registered phone."""
        household = scenario.household_by_id(ticket["household_id"]) if ticket["household_id"] else None
        if household and reporter["phone"] == household["phone"]:
            return True
        return index == 0

    def reping_stale(self):
        """Tell reporters on tickets with no news for a while that we have not forgotten them."""
        cutoff = (db.now_game() - timedelta(minutes=STALE_AFTER_MIN)).isoformat()
        rows = db.query("""SELECT * FROM tickets WHERE status IN ('open','proposed') AND kind IN ('rescue','welfare','supplies')
                           AND last_update_at < ?""", (cutoff,))
        for row in rows:
            ticket = tickets.decode(row)
            tickets.touch(ticket["id"], last_update_at=db.now_iso())
            self.status_update(ticket)
            self.log(f"Loop re-pinged {ticket['id']}: no update for {STALE_AFTER_MIN} minutes", ticket_id=ticket["id"])
        return len(rows)

    def draft_bulletins(self):
        drafted = []
        for lang in ("mr", "hi"):
            result = self.call("draft_bulletin", summary=f"Loop drafted a {lang.upper()} ward bulletin", language=lang)
            if result:
                drafted.append(result)
        return drafted
