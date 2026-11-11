"""Watch: reads alerts and rainfall, keeps area memory, proposes pre-positioning."""
from .. import db, events
from ..tools import alerts, approvals, geo, registry, teams, weather  # noqa: F401  (registers get_rainfall)
from .base import Agent

# Low-lying lanes along River Road flood first.
WATCH_ZONES = [
    {"name": "River Road, Lanes 1 to 5", "polygon": [[19.0742, 72.8728], [19.0752, 72.8728], [19.0752, 72.8772], [19.0742, 72.8772]]},
    {"name": "River Road, Lanes 6 to 9", "polygon": [[19.0742, 72.8772], [19.0752, 72.8772], [19.0752, 72.8815], [19.0742, 72.8815]]},
]
PREPOSITION_PLAN = [
    ("boat2", "L7_mid", "East side, Market Road at Lane 7: cut off from Station Road if Lane 6 floods"),
    ("boat3", "L4_bot", "River Road at Lane 4: closest to the low-lying lanes by the temple"),
]


@registry.tool("propose_preposition",
               "Propose moving a free boat to a staging point near a watch zone before the peak. Needs officer approval.",
               {"type": "object", "properties": {"team_id": {"type": "string"}, "to_node": {"type": "string"},
                                                 "why": {"type": "string"}}, "required": ["team_id", "to_node"]},
               model_safe=False)
def propose_preposition(team_id, to_node, why=""):
    team = teams.get(team_id)
    if not team or team["status"] != "free":
        return None
    route = geo.compute_route(team["node"], to_node, kind=team["kind"])
    if not route["found"]:
        return None
    return approvals.create_approval(
        "preposition", f"Pre-position {team['name']} at {why.split(':')[0]}?", team_id=team_id,
        payload={"to_node": to_node, "route": route, "why": why},
        reasons=["Red alert for the Mithi river", why, f"{route['length_m'] / 1000:.1f} km, about {route['eta_min']} min"],
        agent="Watch")


class Watch(Agent):
    name = "Watch"
    tools = ["read_alerts", "get_rainfall", "mark_road_blocked", "propose_preposition"]

    def run(self, event):
        if event["type"] == "tick":
            return self.check_alerts()
        if event["type"] == "road_blocked":
            return self.road_blocked(event["road"], event.get("source", "volunteer"), event.get("depth"))
        return None

    def check_alerts(self):
        new = alerts.read_alerts()
        actions = []
        for alert in new:
            alerts.mark_seen(alert["id"])
            self.call("read_alerts", summary=f"Watch read a {alert['level']} alert: {alert['headline']}")
            incident = db.one("SELECT * FROM incidents ORDER BY id LIMIT 1")
            level = alerts.higher_level(alert["level"], incident["level"])
            db.update("incidents", "id", incident["id"], level=level,
                      status="active" if level in ("Orange", "Red") else "monitoring", note=alert["headline"])
            if incident["level"] == "none":
                rain = self.call("get_rainfall", summary="Watch checked live rainfall from Open-Meteo")
                self.log(f"Watch: rainfall now {rain['now_mm']} mm, next 6 h {rain['next_6h_mm']} mm ({rain['source']})")
            if alert["level"] in ("Orange", "Red"):
                db.set_setting("watch_zones", _zones_json())
                self.log(f"Watch marked {len(WATCH_ZONES)} low-lying watch zones along River Road")
            if alert["level"] == "Red":
                actions.append({"type": "red_alert", "alert": alert})
                for team_id, node, why in PREPOSITION_PLAN:
                    proposal = self.call("propose_preposition", summary=f"Watch proposed pre-positioning {team_id}",
                                         team_id=team_id, to_node=node, why=why)
                    if proposal:
                        self.log(f"Watch proposed moving {teams.get(team_id)['name']} before the peak: {why}")
            events.publish("changed", {"what": "incident"})
        return actions

    def road_blocked(self, road, source, depth=None):
        result = self.call("mark_road_blocked", summary=f"Watch marked {road} blocked ({source})",
                           road=road, source=source, depth=depth)
        self.log(f"Watch updated area memory: {result['road']} {result['status']} "
                 f"(confirmations: {result['confirmations']}, fades unless confirmed)")
        events.publish("changed", {"what": "area"})
        return result


def _zones_json():
    import json
    return json.dumps(WATCH_ZONES)
