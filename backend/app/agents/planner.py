"""The LLM Planner: plans its own steps, calls one tool at a time, observes, replans.

For an event (a citizen's rescue report, a rumour, a crew reporting a blocked
lane) it receives the event plus relevant memory and answers in JSON with an
ordered plan, the next tool call and a reason. The loop runs that one call,
shows the model the result, and asks again, until the model says it is done
or the step limit is reached.

Guardrails, all enforced here, outside the model:
- Only tools from tools/registry.py that are allowed for this kind of event.
- Every step is validated against its JSON schema AND the current state
  (for example, a merge only into a ticket that find_similar_tickets scored at
  or above the auto-merge bar). An invalid step is rejected and logged, and
  the rules take over from the state reached so far.
- No tool the Planner can reach dispatches a team, closes or downgrades a
  ticket, or sends a bulletin. Those still need an officer approval through
  approvals.require_approved, exactly as before.
- A timeout, a rate limit after retries, or bad JSON hands the event to the
  rules, and the fallback is written to the audit log.
"""
import json
import os
import time

from .. import db, events, llm
from ..tools import audit, geo, memory, registry, tickets  # noqa: F401  (memory registers its tools)
from .base import Agent

MAX_STEPS = int(os.environ.get("PLANNER_MAX_STEPS", "6"))
SCOPES = ("off", "judgment", "all")
JUDGMENT_INTENTS = {"rescue", "welfare", "rumour"}
ALL_INTENTS = JUDGMENT_INTENTS | {"supplies"}

MESSAGE_TOOLS = ["find_similar_tickets", "create_ticket", "merge_into_ticket", "flag_for_verification",
                 "score_priority", "escalate_danger", "geocode_landmark", "search_playbook"] + memory.MEMORY_TOOLS
ROAD_TOOLS = ["mark_road_blocked", "replan_routes", "list_free_teams", "memory_area", "memory_episodes"]
# Never offered to the Planner, whatever it asks for: these act on the world past the approval gate.
FORBIDDEN = {"create_approval", "send_message", "ask_followup", "draft_bulletin", "propose_preposition", "answer_faq",
             "extract_report", "read_alerts", "get_rainfall", "compute_route"}
DANGERS = {"gas", "fire", "electrical", "unconscious", "breathing", "needs medic"}


class PlanRejected(Exception):
    """A proposed step failed validation. The rules take over."""


def scope():
    value = db.get_setting("planner_scope", os.environ.get("PLANNER_SCOPE", "judgment"))
    return value if value in SCOPES else "judgment"


class Planner(Agent):
    name = "Planner"

    # ---- which events get the LLM ------------------------------------------------------------
    def handles(self, kind, intent=None):
        if scope() == "off" or llm.planner_provider() is None:
            return False
        if kind == "message":
            return intent in (ALL_INTENTS if scope() == "all" else JUDGMENT_INTENTS)
        return kind == "road_blocked"

    # ---- events ---------------------------------------------------------------------------------
    def run_message(self, reporter, heard, text):
        """Decide what one citizen report means. Returns a Triage-style decision, or None for rules."""
        fields = heard["fields"]
        listen = {k: fields.get(k) for k in ("intent", "language", "people", "people_implied", "vulnerable", "medical",
                                             "danger", "water_level", "rising", "lane", "landmark", "location_found",
                                             "name", "claim", "repost")}
        mem = {
            "short_term": memory.memory_ticket_context(reporter_id=reporter["id"]),
            "long_term": {"blocked_roads": [b["road"] for b in memory.memory_area()["blocked_roads"]]},
            "episodic": memory.memory_episodes(query=fields.get("lane") or "", limit=3)["episodes"],
        }
        event = {"event": "citizen_message", "report_id": heard["report_id"], "reporter_id": reporter["id"],
                 "text": text, "listen": listen,
                 "typical_plan": ["find_similar_tickets", "merge_into_ticket OR create_ticket OR flag_for_verification",
                                  "score_priority", "done"]}
        state = {"report_id": heard["report_id"], "fields": fields, "candidates": {}, "decision": None,
                 "scored": False, "kind": "message"}
        goal = ("Decide what this report means for the family. Look for an existing ticket first. "
                "Then exactly one of: merge into a strong match, create a new ticket, or (for a rumour) flag it for "
                "verification. Score the ticket after creating or merging. Escalate a danger the report mentions.")
        return self._run("message", event, mem, MESSAGE_TOOLS, state, goal)

    def run_road_blocked(self, road, team):
        """A crew reported a blocked lane. Returns {"replanned": [...]} or None for rules."""
        mem = {"long_term": memory.memory_area(), "episodic": memory.memory_episodes(query=road, limit=3)["episodes"]}
        event = {"event": "lane_blocked", "road": road, "reported_by": team["name"]}
        state = {"road": road, "source": team["name"], "marked": False, "replanned": None, "kind": "road"}
        goal = (f"{road} is reported blocked by {team['name']}. Record it in area memory with mark_road_blocked, "
                "then replan every route that uses it with replan_routes. Check memory first if it helps.")
        return self._run("road_blocked", event, mem, ROAD_TOOLS, state, goal)

    # ---- the loop -------------------------------------------------------------------------------
    def _run(self, kind, event, mem, allowed, state, goal):
        provider, model = llm.planner_provider(), llm.planner_model()
        run_id = db.insert("agent_runs", event=json.dumps(event, ensure_ascii=False, default=str), provider=provider,
                           model=model, status="running", plan="[]", steps="[]",
                           memory=json.dumps(mem, ensure_ascii=False, default=str), started_at=db.now_iso())
        run = {"id": run_id, "steps": [], "plan": [], "ticket_id": None}
        self.last_run_id = run_id
        messages = [{"role": "system", "content": self._system(allowed, goal)},
                    {"role": "user", "content": json.dumps({**event, "memory": mem}, ensure_ascii=False, default=str)}]
        self.log(f"Planner ({provider}, {model}) started on {kind.replace('_', ' ')}", kind="agent_plan",
                 input={"run": run_id, "event": event})
        try:
            for step_no in range(1, MAX_STEPS + 1):
                reply = llm.chat_json(messages, provider=provider)
                plan, nxt, done = self._read_reply(reply)
                if plan:
                    run["plan"] = plan
                if done or nxt is None:
                    missing = self._missing(kind, state)
                    if missing and not run.get("nudged"):
                        run["nudged"] = True
                        run["steps"].append({"n": step_no, "tool": "replan", "args": {}, "why": missing,
                                             "result": "asked the model to continue", "at": db.now_iso()})
                        self._save(run)
                        messages.append({"role": "assistant", "content": json.dumps(reply, ensure_ascii=False)})
                        messages.append({"role": "user", "content": json.dumps(
                            {"not_done": missing, "steps_left": MAX_STEPS - step_no + 1}, ensure_ascii=False)})
                        continue
                    self._check_done(kind, state)
                    return self._finish(run, state, reply.get("summary") or "done")
                tool_name, args, why = self._validate(nxt, allowed, state)
                self._save(run, plan=run["plan"])
                result = registry.call(tool_name, self.name, args, summary=f"Planner step {step_no}: {tool_name}",
                                       ticket_id=state.get("ticket_id"))
                self._observe(tool_name, args, result, state)
                run["ticket_id"] = state.get("ticket_id")
                run["steps"].append({"n": step_no, "tool": tool_name, "args": args, "why": why,
                                     "result": _brief(result), "at": db.now_iso()})
                self.log(f"Planner step {step_no}: {tool_name} because {why}", kind="agent_step",
                         ticket_id=state.get("ticket_id"), input={"run": run_id, "args": args}, result=_brief(result))
                self._save(run)
                messages.append({"role": "assistant", "content": json.dumps(reply, ensure_ascii=False)})
                messages.append({"role": "user", "content": json.dumps(
                    {"result_of": tool_name, "result": _brief(result, 1600), "steps_left": MAX_STEPS - step_no,
                     "state": self._state_hint(kind, state)}, ensure_ascii=False, default=str)})
            # Out of steps: keep what was decided, the rules do the rest.
            self._check_done(kind, state)
            return self._finish(run, state, f"stopped at the {MAX_STEPS}-step limit")
        except (llm.LLMError, PlanRejected) as e:
            return self._fallback(run, state, e)
        except Exception as e:  # a tool raised on arguments that passed validation
            return self._fallback(run, state, PlanRejected(f"{type(e).__name__}: {str(e)[:120]}"))

    def _system(self, allowed, goal):
        specs = [{"name": n, "description": registry.TOOLS[n].description, "parameters": registry.TOOLS[n].parameters}
                 for n in allowed]
        return (
            "You are the Planner agent in Pukaar, the flood control room of Ward 12, Shanti Nagar, Mumbai.\n"
            f"Goal: {goal}\n"
            "You work in steps. Each reply is ONE JSON object and nothing else:\n"
            '{"plan": [{"tool": "<name>", "why": "<short reason>"}, ...], '
            '"next": {"tool": "<name>", "args": {...}, "why": "<short reason>"} or null, '
            '"done": false, "summary": "<one line when done>"}\n'
            "plan = the remaining steps in order. next = the one tool to run now. After each tool you get its result "
            "and may change the plan. Set done to true and next to null when the goal is met.\n"
            "Rules: use only these tools, with arguments that match their parameters. You cannot dispatch boats, "
            "close or downgrade tickets, or send bulletins; a duty officer approves those separately. Merge only into "
            f"a ticket that find_similar_tickets returned with a score of at least {tickets.AUTO_MERGE_AT}; otherwise "
            "create a new ticket (the officer is asked about weaker matches automatically). Never merge into a ticket "
            "whose status is safe or closed. Keep reasons short and concrete.\n"
            f"Tools: {json.dumps(specs, ensure_ascii=False)}"
        )

    @staticmethod
    def _read_reply(reply):
        plan = reply.get("plan") if isinstance(reply.get("plan"), list) else []
        plan = [{"tool": str(p.get("tool", ""))[:40], "why": str(p.get("why", ""))[:160]}
                for p in plan if isinstance(p, dict)][:MAX_STEPS]
        nxt = reply.get("next")
        if nxt is not None and not isinstance(nxt, dict):
            raise llm.LLMError("bad_json", "next is not an object")
        return plan, nxt, bool(reply.get("done"))

    # ---- guardrails -----------------------------------------------------------------------------
    def _validate(self, nxt, allowed, state):
        tool_name = str(nxt.get("tool", ""))
        args = nxt.get("args") or {}
        why = str(nxt.get("why", "")).strip()[:200] or "no reason given"
        if tool_name in FORBIDDEN or tool_name not in allowed or tool_name not in registry.TOOLS:
            raise PlanRejected(f"tool '{tool_name}' is not allowed for this event")
        if not isinstance(args, dict):
            raise PlanRejected("args must be an object")
        schema = registry.TOOLS[tool_name].parameters
        props = schema.get("properties", {})
        args = {k: v for k, v in args.items() if k in props}
        for key, value in list(args.items()):
            if props[key].get("type") == "integer" and isinstance(value, str) and value.strip().isdigit():
                args[key] = int(value.strip())
        for key in schema.get("required", []):
            if key not in args:
                raise PlanRejected(f"{tool_name} is missing '{key}'")
        for key, value in args.items():
            if not _type_ok(props[key].get("type"), value):
                raise PlanRejected(f"{tool_name}.{key} has the wrong type")
            if props[key].get("enum") and value not in props[key]["enum"]:
                raise PlanRejected(f"{tool_name}.{key} must be one of {props[key]['enum']}")
        check = getattr(self, f"_check_{tool_name}", None)
        if check:
            args = check(args, state) or args
        return tool_name, args, why

    def _decided(self, state):
        if state.get("decision"):
            raise PlanRejected(f"this report was already handled ({state['decision']['action']})")

    def _same_report(self, args, state):
        if int(args.get("report_id", -1)) != state["report_id"]:
            raise PlanRejected("that is not this event's report")

    def _check_find_similar_tickets(self, args, state):
        self._same_report(args, state)
        return {"report_id": state["report_id"]}

    def _check_create_ticket(self, args, state):
        self._same_report(args, state)
        self._decided(state)
        intent = state["fields"].get("intent")
        kind = args.get("kind") or ("supplies" if intent == "supplies" else "welfare" if intent == "welfare" else "rescue")
        if intent == "rumour":
            raise PlanRejected("a rumour goes to Verify, not to a new rescue ticket")
        if kind not in ("rescue", "welfare", "supplies"):
            raise PlanRejected(f"ticket kind '{kind}' is not allowed")
        return {"report_id": state["report_id"], "kind": kind}

    def _check_merge_into_ticket(self, args, state):
        self._same_report(args, state)
        self._decided(state)
        cand = state["candidates"].get(args.get("ticket_id"))
        if not cand:
            raise PlanRejected("merge target was not returned by find_similar_tickets")
        if cand["score"] < tickets.AUTO_MERGE_AT:
            raise PlanRejected(f"match score {cand['score']} is below the {tickets.AUTO_MERGE_AT} auto-merge bar")
        if cand["status"] in ("safe", "closed"):
            raise PlanRejected("cannot merge into a family that is already safe")
        # The recorded confidence and reason come from the matcher, not the model.
        return {"report_id": state["report_id"], "ticket_id": args["ticket_id"],
                "reason": tickets.merge_reason_text(cand["reasons"], [state["fields"].get("language")]),
                "confidence": cand["score"]}

    def _check_flag_for_verification(self, args, state):
        self._same_report(args, state)
        self._decided(state)
        if state["fields"].get("intent") != "rumour":
            raise PlanRejected("only a rumour can be sent to Verify; a rescue call is never parked")
        reason = tickets.check_claim(state["fields"].get("claim")) or str(args.get("reason", ""))[:200] or \
            "Unverified claim with no official source."
        return {"report_id": state["report_id"], "reason": reason}

    def _check_score_priority(self, args, state):
        if not state.get("ticket_id") or args.get("ticket_id") != state["ticket_id"]:
            raise PlanRejected("score only the ticket this run created or merged into")

    def _check_escalate_danger(self, args, state):
        if not state.get("ticket_id") or args.get("ticket_id") != state["ticket_id"]:
            raise PlanRejected("escalate only this run's ticket")
        if args.get("danger") not in DANGERS:
            raise PlanRejected(f"unknown danger '{args.get('danger')}'")

    def _check_mark_road_blocked(self, args, state):
        road = geo.normalise_road_name(str(args.get("road", "")))
        if road != state["road"]:
            raise PlanRejected("that is not the road the crew reported")
        return {"road": road, "source": state["source"]}

    def _check_replan_routes(self, args, state):
        if not state["marked"]:
            raise PlanRejected("mark the road blocked before replanning")
        return {"road": state["road"]}

    def _state_hint(self, kind, state):
        if kind == "road_blocked":
            return {"marked": state["marked"], "replanned": state["replanned"] is not None,
                    "still_to_do": self._missing(kind, state) or "nothing: set done true"}
        top = sorted(state["candidates"].values(), key=lambda c: -c["score"])[:3]
        return {"decided": bool(state.get("decision")), "ticket_id": state.get("ticket_id"),
                "scored": state["scored"],
                "candidates": [{"ticket_id": c["ticket_id"], "score": c["score"], "status": c["status"]} for c in top],
                "still_to_do": self._missing(kind, state)
                or ("score_priority" if not state["scored"] and state.get("decision", {}).get("action") != "verify"
                    else "nothing: set done true")}

    @staticmethod
    def _missing(kind, state):
        if kind == "message" and not state.get("decision"):
            return ("The report is not decided yet. Call merge_into_ticket for a candidate with a score of at least "
                    f"{tickets.AUTO_MERGE_AT}, flag_for_verification for a rumour, or create_ticket otherwise.")
        if kind == "road_blocked" and not state["marked"]:
            return "Call mark_road_blocked for the reported road first."
        if kind == "road_blocked" and state["replanned"] is None:
            return "Call replan_routes for the road now."
        return None

    def _check_done(self, kind, state):
        if kind == "message" and not state.get("decision"):
            raise PlanRejected("finished without deciding the report")
        if kind == "road_blocked" and (not state["marked"] or state["replanned"] is None):
            raise PlanRejected("finished without marking and replanning the road")

    # ---- observing results ----------------------------------------------------------------------
    def _observe(self, tool_name, args, result, state):
        if tool_name == "find_similar_tickets":
            state["candidates"] = {c["ticket_id"]: c for c in result}
        elif tool_name == "create_ticket":
            state["ticket_id"] = result["ticket_id"]
            state["decision"] = {"action": "created", "ticket_id": result["ticket_id"]}
        elif tool_name == "merge_into_ticket":
            state["ticket_id"] = args["ticket_id"]
            state["decision"] = {"action": "merged", "ticket_id": args["ticket_id"], "reports": result.get("reports"),
                                 "reason": args["reason"]}
        elif tool_name == "flag_for_verification":
            state["ticket_id"] = result["ticket_id"]
            state["decision"] = {"action": "verify", "ticket_id": result["ticket_id"], "reason": args["reason"]}
        elif tool_name in ("score_priority", "escalate_danger"):
            state["scored"] = True
            if state.get("decision"):
                state["decision"]["priority"] = result.get("priority")
        elif tool_name == "mark_road_blocked":
            state["marked"] = True
        elif tool_name == "replan_routes":
            state["replanned"] = result.get("replanned", [])

    # ---- ending ---------------------------------------------------------------------------------
    def _finish(self, run, state, summary):
        outcome = self._complete(state)
        run["ticket_id"] = state.get("ticket_id")
        self._save(run, status="done", outcome=summary)
        self.log(f"Planner finished: {summary}", kind="agent_done", ticket_id=state.get("ticket_id"),
                 input={"run": run["id"]}, result=outcome)
        return outcome

    def _fallback(self, run, state, error):
        kind = getattr(error, "kind", "invalid_step")
        reason = f"{kind}: {getattr(error, 'detail', '') or error}"[:200]
        run["ticket_id"] = state.get("ticket_id")
        self._save(run, status="rules", outcome=f"Rules took over ({reason})")
        audit.log("Planner", f"Rules took over: {reason}", kind="agent_fallback", ticket_id=state.get("ticket_id"),
                  input={"run": run["id"], "kind": kind})
        # Keep what the Planner already decided; the rules finish from there.
        return self._complete(state) if state.get("decision") or state.get("marked") else None

    def _complete(self, state):
        if state["kind"] == "road":
            if state["marked"] and state["replanned"] is None:
                state["replanned"] = registry.call("replan_routes", "Dispatch", {"road": state["road"]},
                                                   summary=f"Rules replanned routes through {state['road']}")["replanned"]
            return {"replanned": state["replanned"] or []}
        decision = state.get("decision")
        if decision and decision["action"] in ("created", "merged") and not state["scored"]:
            decision["priority"] = tickets.score_priority(decision["ticket_id"])["priority"]
        if decision and decision["action"] == "created":
            best = max(state["candidates"].values(), key=lambda c: c["score"], default=None)
            if best and tickets.SUGGEST_MERGE_AT <= best["score"] < tickets.AUTO_MERGE_AT and \
                    best["status"] not in ("safe", "closed") and best["ticket_id"] != decision["ticket_id"]:
                from .triage import Triage
                Triage()._suggest_merge(decision["ticket_id"], best)
        return decision

    def _save(self, run, status=None, outcome=None, plan=None):
        values = {"steps": json.dumps(run["steps"], ensure_ascii=False, default=str)}
        if run.get("ticket_id"):
            values["ticket_id"] = run["ticket_id"]
        if plan is not None:
            values["plan"] = json.dumps(plan, ensure_ascii=False)
        if status:
            values["status"] = status
            values["ended_at"] = db.now_iso()
        if outcome:
            values["outcome"] = outcome
        db.update("agent_runs", "id", run["id"], **values)
        events.publish("changed", {"what": "agent", "run": run["id"]})


def attach_ticket(run_id, ticket_id):
    """A run that handed over to the rules still belongs on the ticket the rules then made."""
    if run_id and ticket_id:
        db.execute("UPDATE agent_runs SET ticket_id = ? WHERE id = ? AND ticket_id IS NULL", (ticket_id, run_id))


def _type_ok(kind, value):
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool) or (isinstance(value, str) and value.isdigit())
    if kind == "string":
        return isinstance(value, str)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "array":
        return isinstance(value, list)
    if kind == "object":
        return isinstance(value, dict)
    return True


def _brief(value, limit=600):
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return value
    return text[: limit - 1] + "…"


def runs_for_ticket(ticket_id):
    rows = db.query("SELECT * FROM agent_runs WHERE ticket_id = ? ORDER BY id", (ticket_id,))
    for r in rows:
        for key in ("event", "plan", "steps", "memory"):
            r[key] = db.loads(r[key], [] if key in ("plan", "steps") else {})
    return rows
