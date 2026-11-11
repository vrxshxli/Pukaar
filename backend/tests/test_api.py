import os

from fastapi.testclient import TestClient

from .helpers import DAUGHTER_PHONE, KAMLA_DAUGHTER, KAMLA_NEIGHBOUR, KAMLA_PHONE, KAMLA_VOICE, NEIGHBOUR_PHONE, at


def client():
    os.environ["PUKAAR_NO_TICKER"] = "1"
    from app.main import app
    return TestClient(app)


def test_api_flow_from_messages_to_approval_and_lookup():
    with client() as c:
        at("21:40")
        for phone, text in [(KAMLA_PHONE, KAMLA_VOICE), (DAUGHTER_PHONE, KAMLA_DAUGHTER), (NEIGHBOUR_PHONE, KAMLA_NEIGHBOUR)]:
            assert c.post("/api/messages", json={"phone": phone, "text": text}).status_code == 200
        state = c.get("/api/state").json()
        kamla = next(t for t in state["tickets"] if t["title"] == "Kamla Devi household")
        assert kamla["report_count"] == 3 and kamla["priority"] == "P1"
        assert state["metrics"]["reports_in"] == 3 and state["metrics"]["tickets"] == 1
        approval = next(a for a in state["approvals"] if a["ticket_id"] == kamla["id"])
        r = c.post(f"/api/approvals/{approval['id']}", json={"decision": "approve", "officer": "Officer Rao"})
        assert r.status_code == 200 and r.json()["status"] == "approved"
        vol = c.get("/api/volunteer/boat1").json()
        assert vol["task"]["id"] == kamla["id"] and "phone" not in str(vol["task"])
        chat = c.get(f"/api/chat/{KAMLA_PHONE}").json()
        assert any(m["direction"] == "out" for m in chat)
        found = c.get("/api/family", params={"name": "Kamla", "area": "Lane 4"}).json()["results"]
        assert found and found[0]["ticket_id"] == kamla["id"]


def test_stream_endpoint_is_registered():
    from app.main import app
    assert any(getattr(r, "path", "") == "/api/stream" for r in app.routes)
