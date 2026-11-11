from app import db
from app.tools import alerts, geo, playbooks


def test_seed_loads_teams_camps_and_rescued_pinto_ticket():
    assert {t["id"] for t in db.query("SELECT id FROM teams")} == {"boat1", "boat2", "boat3", "van1"}
    assert len(db.query("SELECT * FROM camps")) == 2
    pinto = db.one("SELECT * FROM tickets WHERE household_id = 'pinto'")
    assert pinto["status"] == "safe" and pinto["safe_camp"] == "camp3"
    assert pinto["safe_at"].endswith("20:12:00")


def test_kamla_messages_geocode_to_hanuman_temple_on_lane_4():
    texts = [
        "पानी घुटनों तक आ गया है, पोते को बुखार है… गली चार, हनुमान मंदिर के पीछे",
        "Please help my mother Kamla Devi, Lane 4 behind Hanuman temple, Shanti Nagar. Water rising!!",
        "shantinagar gali 4 mandir ke peeche budhi amma aur bachcha phase hai",
    ]
    for text in texts:
        g = geo.geocode_landmark(text)
        assert g["found"] and g["landmark"] == "hanuman_temple" and g["lane"] == "Lane 4", text
        assert g["confidence"] >= 0.9


def test_lane_parsing_in_several_scripts():
    assert geo.parse_lane("gali no. 7 masjid ke paas") == 7
    assert geo.parse_lane("गली ९ में छत पर") == 9
    assert geo.parse_lane("lane nine roof") == 9
    assert geo.parse_lane("no lane here") is None


def test_unknown_place_is_not_found():
    assert geo.geocode_landmark("somewhere near the big tree")["found"] is False


def test_route_avoids_blocked_lane_6_and_gets_longer():
    open_route = geo.compute_route("staging", "L9_bot", blocked=[])
    assert "Lane 6" in open_route["roads"]
    detour = geo.compute_route("staging", "L9_bot", blocked=["Lane 6"])
    assert detour["found"] and "Lane 6" not in detour["roads"]
    assert detour["eta_min"] > open_route["eta_min"]


def test_blocked_road_memory_fades():
    geo.mark_road_blocked("lane 6")
    assert geo.blocked_roads() == ["Lane 6"]
    db.set_clock(db.game_time_on_night("23:30"), speed=0)
    assert geo.blocked_roads() == []


def test_alert_feed_respects_game_clock():
    db.set_clock(db.game_time_on_night("21:20"), speed=0)
    assert [a["level"] for a in alerts.read_alerts()] == ["Yellow", "Orange"]
    db.set_clock(db.game_time_on_night("21:40"), speed=0)
    assert alerts.read_alerts()[-1]["level"] == "Red"


def test_playbook_search_prefers_gas_and_speaks_hindi():
    r = playbooks.search_playbook("गैस की बदबू आ रही है और पानी अंदर है", "hi")
    assert r["playbook"] == "gas_leak" and r["emergency"] == "1906"
    assert all(any(ch > "ऀ" for ch in s) for s in r["steps"])
    assert playbooks.search_playbook("how do I file taxes", "en")["covered"] is False
