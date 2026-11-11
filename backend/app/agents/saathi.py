"""Saathi, the safety companion.

Saathi answers only with steps copied from the approved playbooks. For fire,
gas, electrical danger, someone unconscious or another medical emergency,
the very first line is the emergency number. It never diagnoses.
"""
from .. import llm, nlp
from ..i18n import playbook_language, t
from ..tools import playbooks, tickets  # noqa: F401  (registers search_playbook, escalate_danger)
from .base import Agent

MEDICAL_EMERGENCY = {"unconscious", "breathing"}


class Saathi(Agent):
    name = "Saathi"
    tools = ["search_playbook", "escalate_danger"]

    @staticmethod
    def should_answer(fields, text):
        question = any(m in (text or "").lower() for m in nlp.QUESTION_MARKERS)
        danger = bool(fields.get("danger")) or bool(MEDICAL_EMERGENCY & set(fields.get("medical", [])))
        return question or danger or fields.get("intent") == "question"

    def run(self, event):
        text, lang = event["text"], event["language"]
        fields = event.get("fields", {})
        reply = self.compose(text, lang, fields)
        if event.get("ticket_id"):
            for danger in reply["escalate"]:
                self.call("escalate_danger", summary=f"Saathi flagged {danger} on {event['ticket_id']} for the rescue team",
                          ticket_id=event["ticket_id"], danger=danger)
        self.call("send_message", summary=f"Saathi answered from the {reply['playbook'] or 'no'} playbook",
                  ticket_id=event.get("ticket_id"), reporter_id=event["reporter_id"], text=reply["text"],
                  kind="saathi", agent=self.name)
        return reply

    def compose(self, text, lang, fields=None):
        fields = fields or {}
        pb_lang = playbook_language(lang)
        medical = MEDICAL_EMERGENCY & set(fields.get("medical", []))
        hazard = None
        for danger in ("gas", "fire", "electrical"):
            if danger in fields.get("danger", []):
                hazard = {"gas": "gas_leak"}.get(danger, danger)
                break
        if not hazard and not playbooks.match_hazards(text):
            # Keywords found nothing; in Ollama mode the model may still recognise the hazard.
            hazard = llm.pick_playbook(text)
        found = self.call("search_playbook", summary="Saathi searched the playbooks",
                          question=text, language=pb_lang, hazard=hazard)

        lines, escalate = [], []
        if medical:
            lines.append(t("call_now", lang, number="108", label=t("medical_emergency", lang)))
            lines.append(t("also_call", lang, number="112"))
            escalate += sorted(medical)
        if found["covered"]:
            if found["danger"] and not medical:
                lines.append(t("call_now", lang, number=found["emergency"], label=found["emergency_label"]))
                if found.get("emergency_also"):
                    lines.append(t("also_call", lang, number=found["emergency_also"]))
            lines.append(found["title"])
            lines += [f"{i}. {step}" for i, step in enumerate(found["steps"], 1)]
            lines.append(t("saathi_footer", lang))
            if found["danger"]:
                escalate.append({"gas_leak": "gas"}.get(found["playbook"], found["playbook"]))
        elif not medical:
            lines.append(t("not_covered", lang))
        if escalate:
            lines.append(t("danger_noted", lang))
        return {"text": "\n".join(lines), "playbook": found.get("playbook"), "escalate": escalate,
                "steps": found.get("steps", [])}


def first_line(text):
    return text.split("\n", 1)[0]


def ticket_for(reporter_id):
    from .. import db
    row = db.one("""SELECT t.id FROM tickets t JOIN ticket_reports tr ON tr.ticket_id = t.id
                    WHERE tr.reporter_id = ? AND t.status NOT IN ('closed') AND t.kind IN ('rescue','welfare')
                    ORDER BY t.created_at DESC LIMIT 1""", (reporter_id,))
    return row["id"] if row else None

