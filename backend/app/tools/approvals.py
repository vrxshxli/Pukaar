"""Approvals: the human gate.

Agents can create approval requests. Only an officer, through the API, can
approve one, and only an approved approval unlocks dispatching a team,
sending a bulletin, downgrading a P1, closing without the family, or
applying an uncertain merge.
"""
from .. import db, events
from . import audit
from .registry import tool


class ApprovalRequired(PermissionError):
    pass


def get(approval_id):
    row = db.one("SELECT * FROM approvals WHERE id = ?", (approval_id,))
    return decode(row) if row else None


def decode(row):
    row["payload"] = db.loads(row["payload"], {})
    row["reasons"] = db.loads(row["reasons"], [])
    return row


def pending():
    return [decode(r) for r in db.query("SELECT * FROM approvals WHERE status = 'pending' ORDER BY id")]


def require_approved(approval, kind, ticket_id=None, team_id=None):
    """Raise unless this approval is approved and covers exactly this action."""
    if isinstance(approval, int):
        approval = get(approval)
    if not approval or approval.get("status") != "approved" or approval.get("kind") != kind:
        raise ApprovalRequired(f"'{kind}' needs an approved officer approval")
    if not approval.get("decided_by"):
        raise ApprovalRequired("approval has no deciding officer")
    if ticket_id is not None and approval.get("ticket_id") != ticket_id:
        raise ApprovalRequired("approval is for a different ticket")
    if team_id is not None and approval.get("team_id") != team_id:
        raise ApprovalRequired("approval is for a different team")
    return approval


@tool("create_approval",
      "Ask the duty officer to approve an action (dispatch a team, pre-position boats, send a bulletin, merge, downgrade or close). Nothing happens until the officer approves.",
      {"type": "object", "properties": {
          "kind": {"type": "string", "enum": ["dispatch", "preposition", "bulletin", "merge", "downgrade", "close"]},
          "ticket_id": {"type": "string"}, "team_id": {"type": "string"},
          "title": {"type": "string"}, "reasons": {"type": "array", "items": {"type": "string"}}},
       "required": ["kind", "title"]},
      model_safe=False)
def create_approval(kind, title, ticket_id=None, team_id=None, payload=None, reasons=None, agent="Dispatch"):
    if not db.automation_on():
        audit.log(agent, f"Would propose: {title} (automation is off, nothing proposed)", tool="create_approval",
                  kind="held", input={"kind": kind, "ticket_id": ticket_id, "team_id": team_id}, ticket_id=ticket_id)
        return None
    existing = db.one("""SELECT * FROM approvals WHERE status = 'pending' AND kind = ?
                         AND IFNULL(ticket_id,'') = IFNULL(?, '') AND IFNULL(team_id,'') = IFNULL(?, '')
                         AND (ticket_id IS NOT NULL OR team_id IS NOT NULL OR title = ?)""",
                      (kind, ticket_id, team_id, title))
    if existing:
        return decode(existing)
    approval_id = db.insert("approvals", kind=kind, ticket_id=ticket_id, team_id=team_id, title=title,
                            payload=payload or {}, reasons=reasons or [], status="pending", created_by=agent,
                            created_at=db.now_iso())
    events.publish("changed", {"what": "approvals"})
    return get(approval_id)


def supersede(approval_id, why):
    db.update("approvals", "id", approval_id, status="superseded", decided_at=db.now_iso(), decided_by=None)
    audit.log("Dispatch", f"Withdrew proposal #{approval_id}: {why}", kind="action")
    events.publish("changed", {"what": "approvals"})


def decide(approval_id, decision, officer):
    """Record the officer's decision. Applying the effect is the orchestrator's job."""
    approval = get(approval_id)
    if not approval:
        raise ValueError("no such approval")
    if approval["status"] != "pending":
        raise ValueError(f"approval is already {approval['status']}")
    if not officer:
        raise ApprovalRequired("an officer name is required")
    status = "approved" if decision == "approve" else "rejected"
    db.update("approvals", "id", approval_id, status=status, decided_by=officer, decided_at=db.now_iso())
    audit.log("Officer", f"{officer} {status} #{approval_id}: {approval['title']}", tool="decide_approval",
              kind="human", ticket_id=approval["ticket_id"], approved_by=officer if status == "approved" else None)
    events.publish("changed", {"what": "approvals"})
    return get(approval_id)


def change_team(approval_id, team_id, payload, reasons, title):
    db.update("approvals", "id", approval_id, team_id=team_id, payload=payload, reasons=reasons, title=title)
    return get(approval_id)
