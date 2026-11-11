"""Shared base for agents: a name, and tool calls that land in the audit log."""
from ..tools import audit, registry


class Agent:
    name = "Agent"
    tools: list[str] = []

    def call(self, tool_name, summary=None, ticket_id=None, **kwargs):
        return registry.call(tool_name, self.name, kwargs, summary=summary, ticket_id=ticket_id)

    def log(self, summary, ticket_id=None, kind="action", **extra):
        return audit.log(self.name, summary, kind=kind, ticket_id=ticket_id, **extra)

    def run(self, event):
        raise NotImplementedError
