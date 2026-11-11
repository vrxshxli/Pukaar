"""The audit log. Every agent action, plan step and human decision lands here."""
import json

from .. import db, events


def log(agent, summary, tool=None, kind="action", input=None, result=None,
        ticket_id=None, approved_by=None):
    entry = {
        "at": db.now_iso(),
        "agent": agent,
        "tool": tool,
        "kind": kind,
        "summary": summary,
        "input": _short(input),
        "result": _short(result),
        "ticket_id": ticket_id,
        "approved_by": approved_by,
    }
    entry["id"] = db.insert("audit_log", **entry)
    events.publish("activity", entry)
    return entry


def recent(limit=200, kind=None):
    if kind:
        return db.query("SELECT * FROM audit_log WHERE kind = ? ORDER BY id DESC LIMIT ?", (kind, limit))
    return db.query("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))


def _short(value, limit=400):
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[: limit - 1] + "…"
