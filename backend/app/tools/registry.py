"""Tool registry shared by rules mode and Ollama tool calling.

Each tool is a plain function with a name, a description and a JSON schema
for its arguments. Agents call tools through `call`, which also writes the
audit log, so nothing an agent does goes unrecorded.
"""
import inspect
from dataclasses import dataclass
from typing import Callable

from . import audit


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    fn: Callable
    # Tools that change the outside world are never offered to the model.
    model_safe: bool = True


TOOLS: dict[str, Tool] = {}


def tool(name, description, parameters=None, model_safe=True):
    def register(fn):
        TOOLS[name] = Tool(name, description, parameters or {"type": "object", "properties": {}}, fn, model_safe)
        return fn
    return register


def call(name, caller, args=None, summary=None, ticket_id=None):
    """Run a tool on behalf of an agent and record it in the audit log."""
    kwargs = dict(args or {})
    fn = TOOLS[name].fn
    # ticket_id is used for the audit log, and also passed on if the tool wants it.
    if ticket_id is not None and "ticket_id" in inspect.signature(fn).parameters:
        kwargs["ticket_id"] = ticket_id
    result = fn(**kwargs)
    audit.log(caller, summary or f"{caller} called {name}", tool=name, kind="tool",
              input=kwargs, result=result, ticket_id=ticket_id or kwargs.get("ticket_id"))
    return result


def ollama_schemas(names):
    """Tool definitions in the format Ollama's chat API expects."""
    out = []
    for name in names:
        t = TOOLS[name]
        if not t.model_safe:
            continue
        out.append({"type": "function", "function": {
            "name": t.name, "description": t.description, "parameters": t.parameters}})
    return out
