"""Sign-in: who can reach which part of Pukaar."""
import os

import pytest
from fastapi.testclient import TestClient

from app import auth, db

from .helpers import KAMLA_PHONE, KAMLA_VOICE, at, login


@pytest.fixture
def c():
    os.environ["PUKAAR_NO_TICKER"] = "1"
    from app.main import app
    with TestClient(app) as client:
        yield client


OFFICER_ONLY = [
    ("get", "/api/state", None),
    ("get", "/api/activity", None),
    ("get", "/api/audit", None),
    ("get", "/api/tickets/P-0401", None),
    ("post", "/api/approvals/1", {"decision": "approve"}),
    ("post", "/api/settings", {"automation": False}),
    ("post", "/api/replay", {"action": "pause"}),
    ("post", "/api/reset", None),
    ("post", "/api/tickets/P-0401/close", {}),
    ("post", "/api/tickets/P-0401/downgrade", {"priority": "P2"}),
]


@pytest.mark.parametrize("method,path,body", OFFICER_ONLY)
def test_control_room_needs_a_signed_in_officer(c, method, path, body):
    send = getattr(c, method)
    r = send(path, json=body) if body is not None else send(path)
    assert r.status_code == 401
    login(c, "boat1")
    r = send(path, json=body) if body is not None else send(path)
    assert r.status_code == 403


def test_nothing_changed_while_refused(c):
    c.post("/api/settings", json={"automation": False})
    assert db.automation_on()


def test_full_event_stream_needs_an_officer(c):
    assert c.get("/api/stream").status_code == 401
    assert c.get("/api/stream", params={"team": "boat1"}).status_code == 401


def test_volunteers_see_only_their_own_team(c):
    assert c.get("/api/volunteer/boat1").status_code == 401
    login(c, "boat1")
    assert c.get("/api/volunteer/boat1").status_code == 200
    assert c.get("/api/volunteer/boat2").status_code == 403
    assert c.post("/api/volunteer/boat2", json={"action": "accept"}).status_code == 403


def test_officers_can_open_any_team(c):
    login(c, "rao")
    assert c.get("/api/volunteer/boat2").status_code == 200


def test_citizens_and_families_need_no_account(c):
    at("21:40")
    assert c.post("/api/messages", json={"phone": KAMLA_PHONE, "text": KAMLA_VOICE}).status_code == 200
    assert c.get(f"/api/chat/{KAMLA_PHONE}").status_code == 200
    assert c.get("/api/family", params={"name": "Kamla"}).status_code == 200


def test_approval_is_recorded_under_the_signed_in_officer_not_the_typed_name(c):
    at("21:40")
    c.post("/api/messages", json={"phone": KAMLA_PHONE, "text": KAMLA_VOICE})
    login(c, "rao")
    approval = c.get("/api/state").json()["approvals"][0]
    r = c.post(f"/api/approvals/{approval['id']}", json={"decision": "approve", "officer": "Someone Else"})
    assert r.status_code == 200
    approvers = {row["approved_by"] for row in c.get("/api/audit").json() if row["approved_by"]}
    assert "Officer Rao" in approvers and "Someone Else" not in approvers


def test_wrong_password_and_unknown_user_get_the_same_answer(c):
    a = c.post("/api/auth/login", json={"username": "rao", "password": "nope"})
    b = c.post("/api/auth/login", json={"username": "nobody", "password": "nope"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_repeated_wrong_passwords_lock_the_account_for_a_minute(c):
    for _ in range(auth.MAX_FAILURES):
        c.post("/api/auth/login", json={"username": "rao", "password": "nope"})
    r = c.post("/api/auth/login", json={"username": "rao", "password": auth.DEFAULT_OFFICER_PASSWORD})
    assert r.status_code == 429


def test_logout_ends_the_session(c):
    login(c)
    assert c.get("/api/auth/me").json()["user"]["name"] == "Officer Rao"
    c.post("/api/auth/logout")
    assert c.get("/api/auth/me").status_code == 401
    assert c.get("/api/state").status_code == 401


def test_session_token_and_password_are_not_stored_in_clear(c):
    login(c)
    token = c.cookies.get(auth.COOKIE)
    stored = db.query("SELECT * FROM sessions")
    users = db.query("SELECT * FROM users")
    assert token and all(token not in str(s) for s in stored)
    assert all(auth.DEFAULT_OFFICER_PASSWORD not in str(u) for u in users)


def test_resetting_the_night_keeps_accounts_and_sessions(c):
    login(c)
    assert c.post("/api/reset").status_code == 200
    assert c.get("/api/state").status_code == 200


def test_password_from_environment_replaces_the_demo_password(c, monkeypatch):
    monkeypatch.setenv("PUKAAR_OFFICER_PASSWORD", "river-at-night-42")
    auth.ensure_accounts()
    assert c.post("/api/auth/login", json={"username": "rao", "password": auth.DEFAULT_OFFICER_PASSWORD}).status_code == 401
    assert c.post("/api/auth/login", json={"username": "rao", "password": "river-at-night-42"}).status_code == 200


def test_public_overview_needs_no_login_and_names_no_family(c):
    at("21:40")
    c.post("/api/messages", json={"phone": KAMLA_PHONE, "text": KAMLA_VOICE})
    r = c.get("/api/public/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["totals"]["reports_in"] == 1 and body["roads"] and body["camps"]
    text = str(body)
    assert "Kamla" not in text and "+91" not in text and "P-0" not in text
    assert "tickets" not in body and "teams" not in body
