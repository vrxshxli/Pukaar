"""Listen: hears every channel and turns a message into a structured report."""
from datetime import datetime

from .. import db, llm, scenario
from ..i18n import LANGUAGE_NAMES, t
from ..tools import geo, registry
from .base import Agent

FOLLOWUP_WINDOW_MIN = 15
NEEDS_DETAILS = ("rescue", "welfare")


@registry.tool("extract_report",
               "Extract a structured report from a citizen message: language, people, vulnerable members, medical need, water level, location, danger and intent.",
               {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]})
def extract_report(text):
    fields, source = llm.extract(text)
    fields["extracted_by"] = source
    return fields


class Listen(Agent):
    name = "Listen"
    tools = ["extract_report", "geocode_landmark", "ask_followup"]

    def run(self, event):
        reporter, message = event["reporter"], event["message"]
        waiting = self._waiting_report(reporter["id"])
        if waiting:
            return self._merge_answer(waiting, message)

        fields = self.call("extract_report", text=message["text"],
                           summary=f"Listen read a {event.get('channel', 'chat')} message in "
                                   f"{LANGUAGE_NAMES.get(message['language'], message['language'])}")
        report_id = db.insert("reports", message_id=message["id"], reporter_id=reporter["id"],
                              language=fields["language"], fields=fields, location_text=fields.get("location_text"),
                              landmark=fields.get("landmark"), lat=fields.get("lat"), lng=fields.get("lng"),
                              geo_confidence=fields.get("geo_confidence"), status="complete",
                              created_at=db.now_iso())
        self.log(self._describe(fields), kind="action")

        if fields["intent"] in NEEDS_DETAILS and not fields.get("location_found"):
            self.call("ask_followup", summary="Listen asked where the family is", report_id=report_id,
                      missing="location", text=t("ask_location", fields["language"]))
            return {"report_id": report_id, "fields": fields, "waiting": True}
        return {"report_id": report_id, "fields": fields, "waiting": False,
                "needs_people": fields["intent"] in NEEDS_DETAILS and (not fields.get("people") or fields.get("people_implied"))}

    def ask_people(self, report_id, ticket_id, language, ack):
        """Ask how many people, in the same message as the acknowledgement."""
        db.update("reports", "id", report_id, ticket_id=ticket_id)
        text = f"{ack} {t('ask_people', language)}"
        return self.call("ask_followup", summary=f"Listen asked how many people are in {ticket_id}",
                         ticket_id=ticket_id, report_id=report_id, missing="people", text=text)

    def _waiting_report(self, reporter_id):
        row = db.one("""SELECT * FROM reports WHERE reporter_id = ? AND status LIKE 'awaiting_%'
                        ORDER BY id DESC LIMIT 1""", (reporter_id,))
        if not row:
            return None
        age = (db.now_game() - datetime.fromisoformat(row["created_at"])).total_seconds() / 60
        if age > FOLLOWUP_WINDOW_MIN:
            db.update("reports", "id", row["id"], status="complete")
            return None
        return row

    def _merge_answer(self, report, message):
        """Fold the answer to our follow-up question into the original report."""
        fields = db.loads(report["fields"], {})
        answer, _ = llm.extract(message["text"])
        missing = report["status"].replace("awaiting_", "")
        if missing == "location":
            g = geo.geocode_landmark(message["text"])
            if g["found"]:
                fields.update(location_found=True, lane=g["lane"], landmark=g["landmark"], lat=g["lat"],
                              lng=g["lng"], node=g["node"], geo_confidence=g["confidence"], location_text=g["why"])
        for key in ("people", "people_implied", "battery", "water_level", "name", "household_hint"):
            if answer.get(key) and not fields.get(key):
                fields[key] = answer[key]
        if answer.get("people") and fields.get("people_implied"):
            fields["people"], fields["people_implied"] = answer["people"], False
        for key in ("vulnerable", "medical", "danger"):
            fields[key] = sorted(set(fields.get(key, [])) | set(answer.get(key, [])))
        db.update("reports", "id", report["id"], fields=fields, status="complete", lat=fields.get("lat"),
                  lng=fields.get("lng"), landmark=fields.get("landmark"), geo_confidence=fields.get("geo_confidence"))
        self.log(f"Listen merged the answer to its {missing} question into report #{report['id']}",
                 ticket_id=report["ticket_id"])
        return {"report_id": report["id"], "fields": fields, "waiting": False, "followup_answer": True,
                "ticket_id": report["ticket_id"], "needs_people": False}

    @staticmethod
    def _describe(f):
        bits = [f"intent {f['intent']}"]
        if f.get("people"):
            bits.append(f"{f['people']} people" + (" (implied)" if f.get("people_implied") else ""))
        if f.get("vulnerable"):
            bits.append(", ".join(f["vulnerable"]))
        if f.get("medical"):
            bits.append("medical: " + ", ".join(f["medical"]))
        if f.get("water_level"):
            bits.append(f"water {f['water_level']}")
        if f.get("lane"):
            landmark = scenario.landmark_by_id(f["landmark"]) if f.get("landmark") else None
            bits.append(f"{f['lane']}" + (f" near {landmark['name']}" if landmark else "")
                        + f" (geo {f.get('geo_confidence', 0):.2f})")
        if f.get("danger"):
            bits.append("danger: " + ", ".join(f["danger"]))
        return "Listen extracted " + "; ".join(bits)
