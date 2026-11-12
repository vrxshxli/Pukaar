"""The LLM Planner: its loop, its guardrails, and its fallbacks to rules.

A scripted fake model stands in for Groq or Ollama, so these tests are fast,
free and deterministic.
"""
import json

import pytest

from app import db, llm, orchestrator
from app.agents import planner as planner_mod
from app.tools import approvals, tickets

from .helpers import DAUGHTER_PHONE, KAMLA_DAUGHTER, KAMLA_PHONE, KAMLA_VOICE, at


class Script:
    """Replies in order; a reply may be a function of the conversation so far."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, messages, provider=None):
        self.calls.append(messages)
        if not self.replies:
            raise llm.LLMError("bad_json", "script ran out")
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r(messages) if callable(r) else r


def step(tool, args, why="because"):
    return {"plan": [{"tool": tool, "why": why}], "next": {"tool": tool, "args": args, "why": why}, "done": False}


DONE = {"plan": [], "next": None, "done": True, "summary": "decided"}


@pytest.fixture
def llm_on(monkeypatch):
    # Until a test installs a script, any model call fails fast: no test ever reaches the network.
    monkeypatch.setattr(llm, "chat_json", Script(*[llm.LLMError("unavailable", "no script")] * 5))
    monkeypatch.setattr(llm, "planner_provider", lambda: "groq")
    monkeypatch.setattr(llm, "planner_model", lambda: "test-model")
    db.set_setting("planner_scope", "judgment")


def use(monkeypatch, script):
    monkeypatch.setattr(llm, "chat_json", script)
    return script


def report_of(messages):
    return json.loads(messages[1]["content"])["report_id"]


def last_run():
    return db.one("SELECT * FROM agent_runs ORDER BY id DESC LIMIT 1")


def kinds():
    return [r["kind"] for r in db.query("SELECT kind FROM audit_log WHERE kind LIKE 'agent_%' ORDER BY id")]


def test_planner_plans_calls_tools_and_finishes(monkeypatch, llm_on):
    at("21:40")
    use(monkeypatch, Script(
        lambda m: step("find_similar_tickets", {"report_id": report_of(m)}, "look for this family first"),
        lambda m: step("memory_household", {"lane": "Lane 4"}, "check the registry"),
        lambda m: step("create_ticket", {"report_id": report_of(m)}, "no match, new family"),
        lambda m: step("score_priority", {"ticket_id": "P-0401"}, "rank it"),
        DONE))
    r = orchestrator.handle_message(KAMLA_PHONE, KAMLA_VOICE)
    assert r["action"] == "created" and r["ticket_id"] == "P-0401"
    run = last_run()
    assert run["status"] == "done" and run["ticket_id"] == "P-0401"
    steps = json.loads(run["steps"])
    assert [s["tool"] for s in steps] == ["find_similar_tickets", "memory_household", "create_ticket", "score_priority"]
    assert all(s["why"] for s in steps)
    assert kinds()[0] == "agent_plan" and kinds()[-1] == "agent_done" and kinds().count("agent_step") == 4
    assert json.loads(run["memory"])["short_term"] is not None


def test_planner_merges_only_through_the_matchers_score(monkeypatch, llm_on):
    at("21:40")
    orchestrator.handle_message(KAMLA_PHONE, KAMLA_VOICE)  # scope judgment, but no script yet: falls back to rules
    use(monkeypatch, Script(
        lambda m: step("find_similar_tickets", {"report_id": report_of(m)}),
        lambda m: step("merge_into_ticket", {"report_id": report_of(m), "ticket_id": "P-0401", "reason": "trust me",
                                             "confidence": 0.99}),
        DONE))
    r = orchestrator.handle_message(DAUGHTER_PHONE, KAMLA_DAUGHTER)
    assert r["action"] == "merged" and r["ticket_id"] == "P-0401"
    link = db.one("SELECT reason, confidence FROM ticket_reports WHERE ticket_id = 'P-0401' ORDER BY rowid DESC LIMIT 1")
    assert link["reason"] != "trust me" and link["confidence"] >= tickets.AUTO_MERGE_AT  # the matcher's, not the model's


@pytest.mark.parametrize("error", [llm.LLMError("timeout", "slow"), llm.LLMError("rate_limit", "429"),
                                   llm.LLMError("bad_json", "garbage")])
def test_planner_falls_back_to_rules_and_logs_why(monkeypatch, llm_on, error):
    at("21:40")
    use(monkeypatch, Script(error))
    r = orchestrator.handle_message(KAMLA_PHONE, KAMLA_VOICE)
    assert r["action"] == "created" and tickets.get(r["ticket_id"])["priority"] in ("P1", "P2")  # rules did the job
    fallback = db.one("SELECT summary FROM audit_log WHERE kind = 'agent_fallback'")
    assert fallback and error.kind in fallback["summary"]
    assert last_run()["status"] == "rules" and last_run()["ticket_id"] == r["ticket_id"]


def test_forbidden_tool_is_rejected_and_rules_take_over(monkeypatch, llm_on):
    at("21:40")
    use(monkeypatch, Script(lambda m: step("send_message", {"reporter_id": 1, "text": "boat coming"})))
    r = orchestrator.handle_message(KAMLA_PHONE, KAMLA_VOICE)
    assert r["action"] == "created"
    assert db.one("SELECT 1 FROM messages WHERE text = 'boat coming'") is None
    assert "not allowed" in db.one("SELECT summary FROM audit_log WHERE kind = 'agent_fallback'")["summary"]


def test_weak_merge_is_rejected(monkeypatch, llm_on):
    at("21:40")
    orchestrator.handle_message("+91 90000 05900", "help water at waist, gali 3, 4 people, old man with us")
    use(monkeypatch, Script(
        lambda m: step("find_similar_tickets", {"report_id": report_of(m)}),
        lambda m: step("merge_into_ticket", {"report_id": report_of(m), "ticket_id": "P-0401", "reason": "same lane?"})))
    r = orchestrator.handle_message(KAMLA_PHONE, KAMLA_VOICE)
    assert r["ticket_id"] != "P-0401"  # Kamla is not merged into the Lane 3 family
    assert db.one("SELECT summary FROM audit_log WHERE kind = 'agent_fallback'")["summary"]


@pytest.mark.parametrize("tool", ["create_approval", "propose_preposition", "draft_bulletin", "ask_followup", "set_status"])
def test_planner_cannot_reach_the_approval_gate(monkeypatch, llm_on, tool):
    at("21:40")
    use(monkeypatch, Script(lambda m: step(tool, {"kind": "dispatch", "title": "go", "team_id": "boat1",
                                                   "ticket_id": "P-0401", "status": "approved"})))
    orchestrator.handle_message(KAMLA_PHONE, KAMLA_VOICE)
    assert db.one("SELECT 1 FROM approvals WHERE status = 'approved'") is None
    assert db.one("SELECT 1 FROM teams WHERE status IN ('assigned', 'en_route')") is None
    pending = approvals.pending()
    assert all(a["created_by"] != "Planner" for a in pending)  # Dispatch's own proposal may exist, never the model's


def test_step_limit_stops_the_loop(monkeypatch, llm_on):
    at("21:40")
    script = use(monkeypatch, Script(*[step("memory_area", {}, "look again") for _ in range(20)]))
    r = orchestrator.handle_message(KAMLA_PHONE, KAMLA_VOICE)
    assert len(script.calls) == planner_mod.MAX_STEPS
    assert r["action"] == "created"  # rules finished the job
    assert last_run()["status"] == "rules"


def test_planner_never_lowers_a_p1(monkeypatch, llm_on):
    at("21:40")
    r = orchestrator.handle_message(KAMLA_PHONE, KAMLA_VOICE)
    tickets.touch(r["ticket_id"], priority="P1", priority_score=72)
    use(monkeypatch, Script(lambda m: step("score_priority", {"ticket_id": r["ticket_id"]})))
    orchestrator.handle_message(DAUGHTER_PHONE, KAMLA_DAUGHTER)
    assert tickets.get(r["ticket_id"])["priority"] == "P1"


def test_planner_handles_a_blocked_lane(monkeypatch, llm_on):
    at("21:40")
    use(monkeypatch, Script(
        step("memory_area", {}, "has this lane flooded before?"),
        step("mark_road_blocked", {"road": "Lane 6"}, "record it"),
        step("replan_routes", {"road": "Lane 6"}, "move every boat off it"),
        DONE))
    out = orchestrator.handle_volunteer("boat1", "blocked", road="Lane 6")
    assert out["ok"]
    from app.tools import geo
    assert "Lane 6" in geo.blocked_roads()
    assert last_run()["status"] == "done"


def test_scope_off_and_rules_mode_keep_the_planner_out(monkeypatch):
    at("21:40")
    called = []
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: called.append(1))
    orchestrator.handle_message(KAMLA_PHONE, KAMLA_VOICE)  # rules mode by default: no provider
    db.set_setting("planner_scope", "off")
    monkeypatch.setattr(llm, "planner_provider", lambda: "groq")
    orchestrator.handle_message(DAUGHTER_PHONE, KAMLA_DAUGHTER)
    assert called == []


def test_groq_retries_on_rate_limit_then_succeeds(monkeypatch):
    import httpx
    responses = [httpx.Response(429, headers={"retry-after": "2"}, text="slow down"),
                 httpx.Response(200, json={"choices": [{"message": {"content": '{"done": true}'}}]})]
    monkeypatch.setattr(httpx, "post", lambda *a, **k: responses.pop(0))
    waits = []
    assert llm._groq_chat([{"role": "user", "content": "hi"}], sleep=waits.append) == '{"done": true}'
    assert waits == [2.0]


def test_groq_gives_up_after_retries(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(429, text="slow down"))
    with pytest.raises(llm.LLMError) as e:
        llm._groq_chat([{"role": "user", "content": "hi"}], sleep=lambda s: None)
    assert e.value.kind == "rate_limit"


def test_bad_json_is_detected():
    with pytest.raises(llm.LLMError) as e:
        llm._parse_json("sure, here is the plan!")
    assert e.value.kind == "bad_json"
    assert llm._parse_json('```json\n{"done": true}\n```') == {"done": True}
