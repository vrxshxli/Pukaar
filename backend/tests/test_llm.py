from app import db, llm, orchestrator
from app.tools import tickets

from .helpers import KAMLA_PHONE, KAMLA_VOICE, at


def test_rules_mode_works_with_ollama_stopped(monkeypatch):
    # Point the client at a port where nothing listens, as if Ollama were stopped.
    monkeypatch.setattr(llm, "HOST", "http://127.0.0.1:9")
    llm._state["checked_at"] = 0
    db.set_setting("llm_mode", "ollama")
    status = llm.status()
    assert status["effective"] == "rules" and status["fallback"] is True
    at("21:40")
    r = orchestrator.handle_message(KAMLA_PHONE, KAMLA_VOICE)
    assert r["action"] == "created"
    assert tickets.get(r["ticket_id"])["area"].startswith("Lane 4")
    assert llm.status()["fallbacks"] >= 1


def test_model_fields_cannot_override_script_or_invent_names():
    rules = {"language": "hi", "intent": "rescue", "people": 2, "people_implied": True, "vulnerable": ["child"],
             "medical": [], "danger": [], "water_level": "knee", "name": None, "location_found": True, "battery": None}
    merged = llm.merge_fields(rules, {"language": "mr", "intent": "rescue", "people": 1, "name": "पानी घुटनों तक आ गया है…",
                                      "vulnerable": ["elderly", "alien"], "danger": ["gas"]})
    assert merged["language"] == "hi"
    assert merged["people"] == 2
    assert merged["name"] is None
    assert merged["vulnerable"] == ["child", "elderly"]
    assert merged["danger"] == ["gas"]


def test_model_safe_tools_exclude_anything_that_acts():
    from app.tools import registry
    exposed = {t["function"]["name"] for t in registry.ollama_schemas(list(registry.TOOLS))}
    assert not exposed & {"send_message", "create_approval", "ask_followup", "draft_bulletin", "propose_preposition"}
    assert "geocode_landmark" in exposed and "search_playbook" in exposed
