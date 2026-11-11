"""Reads the mock CAP alert feed in data/alerts."""
import xml.etree.ElementTree as ET
from datetime import datetime

from .. import db
from ..scenario import DATA_DIR
from .registry import tool

CAP = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}
LEVEL_ORDER = {"none": 0, "Yellow": 1, "Orange": 2, "Red": 3}


def parse_alert(path):
    root = ET.parse(path).getroot()
    info = root.find("cap:info", CAP)

    def text(node, tag):
        el = node.find(f"cap:{tag}", CAP)
        return el.text.strip() if el is not None and el.text else None

    color = None
    for param in info.findall("cap:parameter", CAP):
        if text(param, "valueName") == "ColorCode":
            color = text(param, "value")
    polygon = text(info.find("cap:area", CAP), "polygon") or ""
    effective = datetime.fromisoformat(text(info, "effective")).replace(tzinfo=None)
    return {
        "id": text(root, "identifier"),
        "effective": effective.isoformat(),
        "severity": text(info, "severity"),
        "headline": text(info, "headline"),
        "description": text(info, "description"),
        "level": color,
        "area": text(info.find("cap:area", CAP), "areaDesc"),
        "polygon": [[float(x) for x in pt.split(",")] for pt in polygon.split()],
    }


def all_alerts():
    return sorted((parse_alert(p) for p in (DATA_DIR / "alerts").glob("*.xml")),
                  key=lambda a: a["effective"])


@tool("read_alerts",
      "Read the official CAP alert feed and return alerts that are in effect now and have not been handled yet.",
      {"type": "object", "properties": {}})
def read_alerts(include_seen=False):
    now = db.now_iso()
    seen = set((db.get_setting("alerts_seen") or "").split("|")) - {""}
    out = [a for a in all_alerts() if a["effective"] <= now and (include_seen or a["id"] not in seen)]
    return out


def mark_seen(alert_id):
    seen = set((db.get_setting("alerts_seen") or "").split("|")) - {""}
    seen.add(alert_id)
    db.set_setting("alerts_seen", "|".join(sorted(seen)))


def higher_level(a, b):
    return a if LEVEL_ORDER.get(a, 0) >= LEVEL_ORDER.get(b, 0) else b
