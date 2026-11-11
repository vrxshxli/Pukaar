from app import db, orchestrator
from app.tools import approvals, tickets

from .helpers import (DAUGHTER_PHONE, KAMLA_DAUGHTER, KAMLA_NEIGHBOUR, KAMLA_PHONE, KAMLA_VOICE,
                      NEIGHBOUR_PHONE, at, outgoing)


def send_kamla_messages():
    at("21:38")
    first = orchestrator.handle_message(KAMLA_PHONE, KAMLA_VOICE, channel="voice")
    at("21:41")
    second = orchestrator.handle_message(DAUGHTER_PHONE, KAMLA_DAUGHTER, channel="post")
    at("21:44")
    third = orchestrator.handle_message(NEIGHBOUR_PHONE, KAMLA_NEIGHBOUR, channel="sms")
    return first, second, third


def test_kamla_three_messages_become_one_p1_ticket():
    first, second, third = send_kamla_messages()
    assert first["action"] == "created"
    assert second["action"] == "merged" and third["action"] == "merged"
    assert first["ticket_id"] == second["ticket_id"] == third["ticket_id"]
    t = tickets.get(first["ticket_id"])
    assert t["priority"] == "P1"
    assert t["title"] == "Kamla Devi household"
    assert {"elderly", "child"} <= set(t["vulnerable"])
    assert "fever" in t["medical"]
    assert db.one("SELECT COUNT(*) n FROM ticket_reports WHERE ticket_id = ?", (t["id"],))["n"] == 3
    merges = db.query("SELECT reason FROM ticket_reports WHERE ticket_id = ? AND reason != 'first report'", (t["id"],))
    assert all("same landmark" in m["reason"] for m in merges)


def test_kamla_gets_hindi_and_daughter_gets_english():
    send_kamla_messages()
    kamla = outgoing(KAMLA_PHONE)
    assert any("कितने लोग" in m for m in kamla), kamla
    assert any("जुड़ गए" in m for m in kamla)
    assert any("linked to ticket" in m for m in outgoing(DAUGHTER_PHONE))
    assert any("jud gaye" in m for m in outgoing(NEIGHBOUR_PHONE))


def test_dispatch_proposes_medic_boat_and_waits_for_officer():
    first, *_ = send_kamla_messages()
    pending = [a for a in approvals.pending() if a["kind"] == "dispatch" and a["ticket_id"] == first["ticket_id"]]
    assert len(pending) == 1
    assert pending[0]["team_id"] == "boat1"
    assert "Medic on board" in pending[0]["reasons"]
    assert db.one("SELECT status FROM teams WHERE id = 'boat1'")["status"] == "free"


def test_full_rescue_loop_with_lane6_block_and_otp():
    first, *_ = send_kamla_messages()
    ticket_id = first["ticket_id"]
    approval = next(a for a in approvals.pending() if a["ticket_id"] == ticket_id)
    orchestrator.handle_approval(approval["id"], "approve", "Officer Rao")
    assert db.one("SELECT status FROM teams WHERE id = 'boat1'")["status"] == "assigned"

    orchestrator.handle_volunteer("boat1", "accept")
    assert tickets.get(ticket_id)["status"] == "en_route"
    assert any("OTP" in m for m in outgoing(KAMLA_PHONE))

    result = orchestrator.handle_volunteer("boat1", "blocked", road="Lane 6")
    assert result["road"] == "Lane 6"

    otp = tickets.get(ticket_id)["otp"]
    assert orchestrator.handle_volunteer("boat1", "otp", otp="0000")["ok"] is False
    done = orchestrator.handle_volunteer("boat1", "otp", otp=otp)
    assert done["ok"] and tickets.get(ticket_id)["status"] == "safe"
    assert any("safe at" in m for m in outgoing(DAUGHTER_PHONE))

    orchestrator.handle_message(KAMLA_PHONE, "1")
    assert tickets.get(ticket_id)["status"] in ("safe", "closed")


def test_pinto_repost_gets_auto_reply_and_no_new_ticket():
    at("22:10")
    before = db.one("SELECT COUNT(*) n FROM tickets")["n"]
    r = orchestrator.handle_message("+91 90000 05200", "FWD: Pinto family Lane 2 trapped with grandma, 4 people, please share!!")
    assert r["action"] == "already_safe" and r["ticket_id"] == "P-0398"
    assert db.one("SELECT COUNT(*) n FROM tickets")["n"] == before
    assert any("8:12 PM" in m and "Camp 3" in m for m in outgoing("+91 90000 05200"))


def test_dam_rumour_goes_to_verify():
    at("22:30")
    r = orchestrator.handle_message("+91 90000 05300", "Powai dam has burst!! whole kurla will drown, forward to all")
    t = tickets.get(r["ticket_id"])
    assert t["status"] == "verify" and "river gauge" in t["verify_reason"]
    assert not [a for a in approvals.pending() if a["ticket_id"] == t["id"]]


def test_missing_location_triggers_one_followup_then_merges_answer():
    at("22:00")
    r = orchestrator.handle_message("+91 90000 05400", "help!! water is at waist level, 3 people and my old father")
    assert r["waiting"] is True
    assert db.one("SELECT COUNT(*) n FROM tickets WHERE status = 'open'")["n"] == 0
    at("22:02")
    r2 = orchestrator.handle_message("+91 90000 05400", "Lane 8 near the water tank")
    t = tickets.get(r2["ticket_id"])
    assert t["area"].startswith("Lane 8") and t["people"] == 3 and t["water_level"] == "waist"


def test_red_alert_proposes_preposition_and_bulletins():
    at("21:36")
    orchestrator.tick()
    kinds = sorted(a["kind"] for a in approvals.pending())
    assert kinds.count("preposition") == 2 and kinds.count("bulletin") == 2


def test_gas_leak_question_gets_saathi_answer():
    at("22:20")
    orchestrator.handle_message("+91 90000 05500", "गली 7 मस्जिद के पास गैस की बदबू आ रही है और पानी अंदर है, क्या करें? 4 लोग हैं")
    msgs = outgoing("+91 90000 05500")
    saathi = next(m for m in msgs if m.startswith("1906"))
    assert "माचिस" in saathi
