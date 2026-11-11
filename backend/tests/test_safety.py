"""The safety rules from the brief, each proved in the backend rather than the UI.

Agents do the paperwork; humans send the boats.
"""
import json
import os
import re

import pytest
from fastapi.testclient import TestClient

from app import db, llm, orchestrator
from app.agents.loop import Loop
from app.agents.saathi import Saathi
from app.tools import approvals, playbooks, teams, tickets
from app.tools.approvals import ApprovalRequired

from .helpers import DAUGHTER_PHONE, KAMLA_DAUGHTER, KAMLA_NEIGHBOUR, KAMLA_PHONE, KAMLA_VOICE, NEIGHBOUR_PHONE, at, login


def kamla_ticket():
    at("21:38")
    first = orchestrator.handle_message(KAMLA_PHONE, KAMLA_VOICE)
    at("21:41")
    orchestrator.handle_message(DAUGHTER_PHONE, KAMLA_DAUGHTER)
    at("21:44")
    orchestrator.handle_message(NEIGHBOUR_PHONE, KAMLA_NEIGHBOUR)
    return first["ticket_id"]


def dispatch_approval(ticket_id):
    return next(a for a in approvals.pending() if a["kind"] == "dispatch" and a["ticket_id"] == ticket_id)


def team_status(team_id):
    return db.one("SELECT status FROM teams WHERE id = ?", (team_id,))["status"]


def sent_messages(kind=None):
    sql = "SELECT * FROM messages WHERE direction = 'out' AND status = 'sent'"
    return db.query(sql + (" AND kind = ?" if kind else ""), (kind,) if kind else ())


# 1. No agent can set a team to en_route without an approved approval.

def test_team_cannot_go_en_route_without_any_approval():
    with pytest.raises(ApprovalRequired):
        teams.set_status("boat1", "en_route", approval=None, ticket_id="P-0401")
    assert team_status("boat1") == "free"


def test_pending_or_rejected_approval_does_not_unlock_dispatch():
    ticket_id = kamla_ticket()
    proposal = dispatch_approval(ticket_id)
    with pytest.raises(ApprovalRequired):
        teams.set_status(proposal["team_id"], "en_route", approval=proposal, ticket_id=ticket_id)
    orchestrator.handle_approval(proposal["id"], "reject", "Officer Rao")
    with pytest.raises(ApprovalRequired):
        teams.set_status(proposal["team_id"], "en_route", approval=approvals.get(proposal["id"]), ticket_id=ticket_id)
    assert team_status(proposal["team_id"]) == "free"


def test_approval_for_one_ticket_cannot_move_a_team_to_another():
    ticket_id = kamla_ticket()
    proposal = dispatch_approval(ticket_id)
    orchestrator.handle_approval(proposal["id"], "approve", "Officer Rao")
    with pytest.raises(ApprovalRequired):
        teams.set_status(proposal["team_id"], "en_route", approval=approvals.get(proposal["id"]), ticket_id="P-9999")
    with pytest.raises(ApprovalRequired):
        teams.set_status("boat3", "en_route", approval=approvals.get(proposal["id"]), ticket_id=ticket_id)


def test_dispatch_agent_only_proposes_and_volunteer_cannot_jump_the_gate():
    ticket_id = kamla_ticket()
    orchestrator.dispatch.run()
    orchestrator.tick()
    assert all(t["status"] == "free" for t in teams.all_teams())
    with pytest.raises(ValueError):
        orchestrator.handle_volunteer("boat1", "accept")
    proposal = dispatch_approval(ticket_id)
    orchestrator.handle_approval(proposal["id"], "approve", "Officer Rao")
    orchestrator.handle_volunteer(proposal["team_id"], "accept")
    assert team_status(proposal["team_id"]) == "en_route"


def test_an_approval_without_an_officer_is_refused():
    ticket_id = kamla_ticket()
    proposal = dispatch_approval(ticket_id)
    with pytest.raises(ApprovalRequired):
        approvals.decide(proposal["id"], "approve", officer="")
    forged = {**proposal, "status": "approved", "decided_by": None}
    with pytest.raises(ApprovalRequired):
        teams.set_status(proposal["team_id"], "en_route", approval=forged, ticket_id=ticket_id)


def test_model_cannot_reach_tools_that_act():
    from app.tools import registry
    offered = {t["function"]["name"] for t in registry.ollama_schemas(list(registry.TOOLS))}
    for acting in ("send_message", "create_approval", "draft_bulletin", "propose_preposition", "ask_followup"):
        assert acting not in offered


# 2. Public bulletins are never marked sent without approval.

def test_bulletin_stays_draft_until_approved_and_reject_sends_nothing():
    kamla_ticket()
    drafts = Loop().draft_bulletins()
    assert len(drafts) == 2
    assert {b["status"] for b in db.query("SELECT status FROM bulletins")} == {"draft"}
    assert sent_messages("bulletin") == []

    with pytest.raises(ApprovalRequired):
        orchestrator._send_bulletin(approvals.get(drafts[0]["approval_id"]))
    assert sent_messages("bulletin") == []

    orchestrator.handle_approval(drafts[0]["approval_id"], "reject", "Officer Rao")
    assert db.one("SELECT status FROM bulletins WHERE approval_id = ?", (drafts[0]["approval_id"],))["status"] == "rejected"
    assert sent_messages("bulletin") == []

    orchestrator.handle_approval(drafts[1]["approval_id"], "approve", "Officer Rao")
    assert db.one("SELECT status FROM bulletins WHERE approval_id = ?", (drafts[1]["approval_id"],))["status"] == "sent"
    assert len(sent_messages("bulletin")) > 0


# 3. Turning the kill switch off stops all outgoing messages and new proposals.

def test_kill_switch_stops_messages_and_proposals():
    db.set_setting("automation", "off")
    ticket_id = kamla_ticket()
    at("21:50")
    orchestrator.tick()
    orchestrator.handle_message("+91 90000 05500", "गैस की बदबू आ रही है, गली 7 मस्जिद के पास, क्या करें?")
    assert sent_messages() == []
    assert approvals.pending() == []
    held = db.query("SELECT * FROM messages WHERE direction = 'out' AND status = 'held'")
    assert held, "outgoing messages should be kept as held for the audit trail"
    assert db.query("SELECT 1 FROM audit_log WHERE kind = 'held'")
    # Agents keep doing the paperwork: the ticket exists and is ranked.
    assert tickets.get(ticket_id)["priority"] == "P1"

    db.set_setting("automation", "on")
    orchestrator.handle_message("+91 90000 05501", "Where is the nearest relief camp?")
    assert sent_messages()


def test_kill_switch_via_api_and_close_endpoint_refuses_when_off():
    os.environ["PUKAAR_NO_TICKER"] = "1"
    from app.main import app
    with TestClient(app) as c:
        login(c)
        assert c.post("/api/settings", json={"automation": False}).json()["automation"] is False
        at("21:40")
        c.post("/api/messages", json={"phone": KAMLA_PHONE, "text": KAMLA_VOICE})
        assert c.get("/api/state").json()["approvals"] == []
        assert c.get(f"/api/chat/{KAMLA_PHONE}").json()[-1]["direction"] == "in"


# 4. Saathi's gas-leak reply starts with an emergency number and only uses playbook text.

@pytest.mark.parametrize("text,lang", [
    ("गली 7 में गैस की बदबू आ रही है, क्या करें?", "hi"),
    ("There is a gas smell in the kitchen and water inside, what should I do?", "en"),
    ("घरात गॅसचा वास येत आहे, काय करू?", "mr"),
])
def test_saathi_gas_reply_starts_with_emergency_number_and_quotes_playbook(text, lang):
    from app import nlp
    from app.i18n import TEMPLATES, playbook_language
    fields = nlp.extract(text)
    reply = Saathi().compose(text, fields["language"], fields)
    lines = reply["text"].split("\n")
    assert re.match(r"^(112|101|108|1906)\b", lines[0]), lines[0]
    assert lines[0].startswith("1906")

    book = playbooks.playbooks()["gas_leak"]
    pb_lang = playbook_language(fields["language"])
    allowed_steps = set(book["steps"][pb_lang])
    template_texts = {v for entry in TEMPLATES.values() for v in entry.values()}
    for line in lines[1:]:
        step = re.match(r"^\d+\. (.*)$", line)
        if step:
            assert step.group(1) in allowed_steps, line
        else:
            is_title = line == book["title"][pb_lang]
            is_template = any(_fits_template(line, tpl) for tpl in template_texts)
            assert is_title or is_template, f"line not from playbook or templates: {line}"


def _fits_template(line, template):
    pattern = re.escape(template)
    pattern = re.sub(r"\\\{[a-z_]+\\\}", ".+", pattern)
    return re.fullmatch(pattern, line) is not None


def test_saathi_says_when_a_question_is_not_covered():
    reply = Saathi().compose("How do I renew my passport?", "en", {"danger": [], "medical": []})
    assert "112" in reply["text"] and reply["playbook"] is None


def test_saathi_puts_ambulance_first_for_unconscious_and_never_diagnoses():
    reply = Saathi().compose("my grandmother is unconscious, what do I do", "en", {"danger": [], "medical": ["unconscious"]})
    assert reply["text"].startswith("108")
    assert "unconscious" in reply["escalate"]


def test_gas_message_raises_ticket_and_notes_danger_for_team():
    at("22:20")
    r = orchestrator.handle_message("+91 90000 00707", "गली 7 मस्जिद के पास गैस की बदबू आ रही है और पानी अंदर है, क्या करें? 4 लोग हैं")
    t = tickets.get(r["ticket_id"])
    assert "gas" in t["danger"] and t["priority"] == "P1"
    assert any("Danger for the rescue team: gas" in n for n in t["notes"])


# 5. Family lookup never returns an address or phone number.

def test_family_lookup_returns_only_status_and_camp():
    os.environ["PUKAAR_NO_TICKER"] = "1"
    from app.main import app
    with TestClient(app) as c:
        at("21:40")
        c.post("/api/messages", json={"phone": KAMLA_PHONE, "text": KAMLA_VOICE})
        c.post("/api/messages", json={"phone": "+91 90000 05900", "text": "help water at waist, gali 3, 4 people, old man with us"})
        queries = [{"name": "Kamla"}, {"name": "Pinto", "area": "Lane 2"}, {"ticket": "P-0401"}, {"ticket": "P-0402"},
                   {"name": "Household"}, {"ticket": "P-0398"}]
        seen = 0
        for q in queries:
            body = c.get("/api/family", params=q).json()
            for result in body["results"]:
                seen += 1
                assert set(result) <= {"ticket_id", "title", "status", "safe_at", "camp", "updated_at"}
                text = json.dumps(result, ensure_ascii=False)
                assert "+91" not in text and not re.search(r"\d{5}\s?\d{5}", text)
                assert "Lane" not in text and "गली" not in text and "temple" not in text.lower()
                assert "lat" not in result and "lng" not in result
        assert seen >= 3
        assert db.one("SELECT COUNT(*) n FROM lookups")["n"] >= 3


# 6. Low-confidence duplicates are not merged automatically.

def test_uncertain_duplicate_goes_to_officer_not_merged():
    at("22:00")
    first = orchestrator.handle_message("+91 90000 06001", "Help! water is at knee level at Lane 5. We are 3 people.")
    at("22:25")
    second = orchestrator.handle_message("+91 90000 06002", "A family is stuck at Lane 5, water is at knee level. 3 people inside.")
    assert second["action"] == "created"
    assert first["ticket_id"] != second["ticket_id"]
    links = db.query("SELECT ticket_id FROM ticket_reports WHERE ticket_id IN (?, ?)", (first["ticket_id"], second["ticket_id"]))
    assert len(links) == 2
    merge = [a for a in approvals.pending() if a["kind"] == "merge"]
    assert merge and merge[0]["payload"]["into"] == first["ticket_id"]
    orchestrator.handle_approval(merge[0]["id"], "approve", "Officer Rao")
    assert db.one("SELECT COUNT(*) n FROM ticket_reports WHERE ticket_id = ?", (first["ticket_id"],))["n"] == 2


def test_different_family_names_on_same_landmark_never_merge():
    at("22:00")
    a = orchestrator.handle_message("+91 90000 06101", "The Gupta family is stuck behind Hanuman temple, Lane 4, water at waist level.")
    at("22:05")
    b = orchestrator.handle_message("+91 90000 06102", "Yadav family gali 4 mandir ke peeche phasi hai, paani kamar tak hai")
    assert a["ticket_id"] != b["ticket_id"]
    assert not [x for x in approvals.pending() if x["kind"] == "merge"]


def test_new_family_near_a_rescued_one_is_not_told_it_was_rescued():
    at("22:30")
    r = orchestrator.handle_message("+91 90000 06201", "Help! water is at waist level at Lane 2. We are 3 people.")
    assert r["action"] == "created" and r["ticket_id"] != "P-0398"


# 7. Rules mode works with Ollama stopped.

def test_full_flow_in_rules_mode_with_ollama_stopped(monkeypatch):
    monkeypatch.setattr(llm, "HOST", "http://127.0.0.1:9")
    llm._state["checked_at"] = 0
    db.set_setting("llm_mode", "ollama")
    assert llm.status()["effective"] == "rules"
    ticket_id = kamla_ticket()
    assert tickets.get(ticket_id)["priority"] == "P1"
    assert db.one("SELECT COUNT(*) n FROM ticket_reports WHERE ticket_id = ?", (ticket_id,))["n"] == 3
    proposal = dispatch_approval(ticket_id)
    orchestrator.handle_approval(proposal["id"], "approve", "Officer Rao")
    assert team_status(proposal["team_id"]) == "assigned"


# Other human gates from the deck.

def test_p1_cannot_be_downgraded_or_closed_without_approval():
    ticket_id = kamla_ticket()
    with pytest.raises(ApprovalRequired):
        tickets.downgrade(ticket_id, "P3", approval=None)
    with pytest.raises(ApprovalRequired):
        tickets.set_status(ticket_id, "closed", by="agent")
    # Re-scoring with fewer risk factors never lowers a P1 on its own.
    tickets.touch(ticket_id, vulnerable=[], medical=None, water_level=None, rising=0)
    assert tickets.score_priority(ticket_id)["priority"] == "P1"
    assert tickets.get(ticket_id)["status"] != "closed"
