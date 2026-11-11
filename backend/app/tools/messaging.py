"""Messages in and out of the chat channels.

Nothing leaves the control room while the automation switch is off: outgoing
messages are stored as 'held' and shown in the audit log instead.
"""
from .. import db, events
from . import audit
from .registry import tool


def get_or_create_reporter(phone, name=None, language=None, channel="chat", area=None):
    row = db.one("SELECT * FROM reporters WHERE phone = ?", (phone,))
    if row:
        if language and language != row["language"]:
            db.update("reporters", "id", row["id"], language=language)
            row["language"] = language
        return row
    rid = db.insert("reporters", phone=phone, name=name, language=language or "en", channel=channel,
                    area=area, created_at=db.now_iso())
    return db.one("SELECT * FROM reporters WHERE id = ?", (rid,))


def record_incoming(reporter_id, text, channel, language, meta=None):
    msg = dict(reporter_id=reporter_id, direction="in", channel=channel, text=text, language=language,
               kind="incoming", status="received", created_at=db.now_iso(), meta=meta or {})
    msg["id"] = db.insert("messages", **msg)
    events.publish("message", msg)
    return msg


@tool("send_message",
      "Send a message to one reporter in the chat channel.",
      {"type": "object", "properties": {
          "reporter_id": {"type": "integer"}, "text": {"type": "string"},
          "kind": {"type": "string"}, "ticket_id": {"type": "string"}},
       "required": ["reporter_id", "text"]},
      model_safe=False)
def send_message(reporter_id, text, kind="status", ticket_id=None, agent="Loop"):
    reporter = db.one("SELECT * FROM reporters WHERE id = ?", (reporter_id,))
    on = db.automation_on()
    msg = dict(reporter_id=reporter_id, direction="out", channel=reporter["channel"] if reporter else "chat",
               text=text, language=reporter["language"] if reporter else "en", ticket_id=ticket_id, kind=kind,
               status="sent" if on else "held", created_at=db.now_iso(), meta={"agent": agent})
    msg["id"] = db.insert("messages", **msg)
    if on:
        events.publish("message", msg)
    else:
        audit.log(agent, f"Held a {kind} message to reporter {reporter_id} (automation is off)",
                  tool="send_message", kind="held", input={"text": text}, ticket_id=ticket_id)
    return {"message_id": msg["id"], "status": msg["status"]}


@tool("ask_followup",
      "Ask the reporter one follow-up question in their language when a critical detail is missing.",
      {"type": "object", "properties": {
          "report_id": {"type": "integer"},
          "missing": {"type": "string", "enum": ["location", "people"]}},
       "required": ["report_id", "missing"]},
      model_safe=False)
def ask_followup(report_id, missing, text):
    report = db.one("SELECT * FROM reports WHERE id = ?", (report_id,))
    db.update("reports", "id", report_id, status=f"awaiting_{missing}")
    return send_message(report["reporter_id"], text, kind="followup", ticket_id=report["ticket_id"], agent="Listen")


def send_team_message(team_id, text, ticket_id=None, agent="Dispatch"):
    on = db.automation_on()
    msg = dict(reporter_id=None, direction="out", channel="volunteer", text=text, language="en",
               ticket_id=ticket_id, kind="task", status="sent" if on else "held", created_at=db.now_iso(),
               meta={"team_id": team_id, "agent": agent})
    msg["id"] = db.insert("messages", **msg)
    if on:
        events.publish("team_message", {**msg, "team_id": team_id})
    return {"message_id": msg["id"], "status": msg["status"]}


def thread(reporter_id, limit=200):
    rows = db.query("SELECT * FROM messages WHERE reporter_id = ? AND status != 'held' ORDER BY id LIMIT ?",
                    (reporter_id, limit))
    for r in rows:
        r["meta"] = db.loads(r["meta"], {})
    return rows


def team_thread(team_id, limit=100):
    rows = db.query("""SELECT * FROM messages WHERE channel = 'volunteer' AND status != 'held'
                       AND json_extract(meta, '$.team_id') = ? ORDER BY id DESC LIMIT ?""", (team_id, limit))
    return list(reversed(rows))
