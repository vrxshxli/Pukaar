"""Landmark geocoding, the ward road graph, routing, and area memory."""
import heapq
import math
import re
from datetime import timedelta

from rapidfuzz import fuzz

from .. import db, scenario
from .registry import tool

# Boats move slowly through flooded lanes, roughly 6 km/h.
BOAT_METRES_PER_MIN = 100
VAN_METRES_PER_MIN = 250
LAUNCH_MIN = 3
BLOCK_FADES_AFTER_MIN = 90

NUMBER_WORDS = {
    "ek": 1, "one": 1, "एक": 1,
    "do": 2, "two": 2, "दो": 2, "दोन": 2,
    "teen": 3, "tin": 3, "three": 3, "तीन": 3,
    "char": 4, "chaar": 4, "four": 4, "चार": 4,
    "paanch": 5, "panch": 5, "five": 5, "पाँच": 5, "पांच": 5, "पाच": 5,
    "chhe": 6, "che": 6, "six": 6, "छह": 6, "छः": 6, "सहा": 6,
    "saat": 7, "sat": 7, "seven": 7, "सात": 7,
    "aath": 8, "aat": 8, "eight": 8, "आठ": 8,
    "nau": 9, "nine": 9, "नौ": 9, "नऊ": 9,
}
DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
LANE_WORDS = r"(?:lane|gali|galli|gully|street|गली|गल्ली|लेन)"


def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nodes():
    return scenario.roads()["nodes"]


def edges():
    return scenario.roads()["edges"]


def edge_length(edge):
    a, b = nodes()[edge["from"]], nodes()[edge["to"]]
    return haversine_m(a["lat"], a["lng"], b["lat"], b["lng"])


def nearest_node(lat, lng):
    return min(nodes(), key=lambda n: haversine_m(lat, lng, nodes()[n]["lat"], nodes()[n]["lng"]))


def parse_lane(text):
    """Find a lane number in text like 'gali 4', 'Lane 9', 'गली चार' or 'gali no. 7'."""
    t = text.lower().translate(DEVANAGARI_DIGITS)
    m = re.search(LANE_WORDS + r"\s*(?:no\.?|number|नंबर|क्र\.?)?\s*(\d{1,2})\b", t)
    if m:
        return int(m.group(1))
    m = re.search(LANE_WORDS + r"\s*(?:no\.?|number|नंबर)?\s*([^\s,.!?।]+)", t)
    if m and m.group(1) in NUMBER_WORDS:
        return NUMBER_WORDS[m.group(1)]
    m = re.search(r"(\d{1,2})\s*(?:no\.?)?\s*" + LANE_WORDS, t)
    if m:
        return int(m.group(1))
    return None


def find_landmark(text):
    """Return the best landmark alias found in the text, with a match score."""
    t = text.lower()
    best, best_score = None, 0
    for lm in scenario.landmarks():
        for alias in lm["aliases"]:
            alias_l = alias.lower()
            if alias_l in t:
                # Longer aliases are more specific than 'mandir' or 'hall'.
                score = 100 + min(len(alias_l), 30)
            elif len(alias_l) >= 6:
                score = fuzz.partial_ratio(alias_l, t)
                if score < 88:
                    continue
            else:
                continue
            if score > best_score:
                best, best_score = lm, score
    return best, best_score


@tool("geocode_landmark",
      "Turn a location description such as 'gali 4 mandir ke peeche' into coordinates using the ward's landmark list. Returns a confidence between 0 and 1.",
      {"type": "object", "properties": {"text": {"type": "string", "description": "Location words from the message"}}, "required": ["text"]})
def geocode_landmark(text):
    lane = parse_lane(text or "")
    landmark, _ = find_landmark(text or "")
    lane_node = f"L{lane}_mid" if lane and f"L{lane}_mid" in nodes() else None

    if landmark and lane_node and landmark["lane"] == f"Lane {lane}":
        return _geo(landmark["lat"], landmark["lng"], landmark["node"], 0.95, landmark, lane,
                    f"Lane {lane} and {landmark['name']} agree")
    if landmark and not lane_node:
        return _geo(landmark["lat"], landmark["lng"], landmark["node"], 0.75, landmark, None,
                    f"matched landmark {landmark['name']}")
    if lane_node:
        n = nodes()[lane_node]
        conf = 0.5 if landmark else 0.65
        why = f"Lane {lane}" + (f", but {landmark['name']} is on {landmark['lane']}" if landmark else "")
        return _geo(n["lat"], n["lng"], lane_node, conf, landmark, lane, why)
    return {"found": False, "confidence": 0.0, "why": "no lane or known landmark in the text"}


def _geo(lat, lng, node, confidence, landmark, lane, why):
    return {
        "found": True, "lat": lat, "lng": lng, "node": node, "confidence": confidence,
        "landmark": landmark["id"] if landmark else None,
        "landmark_name": landmark["name"] if landmark else None,
        "lane": f"Lane {lane}" if lane else (landmark["lane"] if landmark else None),
        "why": why,
    }


# Area memory: blocked roads and water depth reported from the field.

def blocked_roads():
    now = db.now_iso()
    rows = db.query(
        "SELECT ref FROM area_events WHERE kind = 'road_blocked' AND expires_at > ?", (now,))
    return sorted({r["ref"] for r in rows})


@tool("mark_road_blocked",
      "Record in area memory that a named road is blocked or flooded. The report fades after a while unless someone confirms it again.",
      {"type": "object", "properties": {
          "road": {"type": "string", "description": "Road name, for example 'Lane 6'"},
          "source": {"type": "string"},
          "depth": {"type": "string", "description": "Optional water depth, for example 'waist'"}},
       "required": ["road"]})
def mark_road_blocked(road, source="field report", depth=None):
    road = normalise_road_name(road)
    now = db.now_game()
    expires = (now + timedelta(minutes=BLOCK_FADES_AFTER_MIN)).replace(microsecond=0).isoformat()
    existing = db.one(
        "SELECT * FROM area_events WHERE kind = 'road_blocked' AND ref = ? AND expires_at > ?",
        (road, now.isoformat()))
    if existing:
        db.update("area_events", "id", existing["id"], expires_at=expires,
                  confirmations=existing["confirmations"] + 1)
        return {"road": road, "status": "confirmed again", "confirmations": existing["confirmations"] + 1}
    db.insert("area_events", kind="road_blocked", ref=road, value=depth or "blocked", source=source,
              confirmations=1, created_at=now.replace(microsecond=0).isoformat(), expires_at=expires)
    return {"road": road, "status": "blocked", "confirmations": 1, "fades_at": expires}


def clear_road(road):
    db.execute("UPDATE area_events SET expires_at = ? WHERE kind = 'road_blocked' AND ref = ?",
               (db.now_iso(), normalise_road_name(road)))


def normalise_road_name(road):
    lane = parse_lane(road)
    if lane:
        return f"Lane {lane}"
    for e in edges():
        if e["name"].lower() == road.strip().lower():
            return e["name"]
    return road.strip().title()


def road_geometry(road):
    """Coordinates of every segment of a named road, for drawing on the map."""
    out = []
    for e in edges():
        if e["name"] == road:
            a, b = nodes()[e["from"]], nodes()[e["to"]]
            out.append([[a["lat"], a["lng"]], [b["lat"], b["lng"]]])
    return out


# Routing over the ward graph with Dijkstra, skipping blocked roads.

def _adjacency(blocked):
    adj = {n: [] for n in nodes()}
    for e in edges():
        if e["name"] in blocked:
            continue
        length = edge_length(e)
        cost = length * e.get("slow", 1.0)
        adj[e["from"]].append((e["to"], length, cost, e["name"]))
        adj[e["to"]].append((e["from"], length, cost, e["name"]))
    return adj


def shortest_path(start, goal, blocked=()):
    # Dijkstra on travel cost (slow water counts extra), while also adding up
    # the real distance so we can show it.
    adj = _adjacency(set(blocked))
    dist, prev, metres = {start: 0.0}, {}, {start: 0.0}
    heap = [(0.0, start)]
    while heap:
        d, n = heapq.heappop(heap)
        if n == goal:
            break
        if d > dist.get(n, math.inf):
            continue
        for nxt, length, cost, road in adj[n]:
            nd = d + cost
            if nd < dist.get(nxt, math.inf):
                dist[nxt], prev[nxt] = nd, (n, road)
                metres[nxt] = metres[n] + length
                heapq.heappush(heap, (nd, nxt))
    if goal not in dist:
        return None
    path, roads, n = [goal], [], goal
    while n != start:
        n, road = prev[n]
        path.append(n)
        roads.append(road)
    path.reverse()
    roads.reverse()
    return {"nodes": path, "roads": roads, "length_m": metres[goal], "cost_m": dist[goal]}


@tool("compute_route",
      "Compute the shortest route between two places on the ward road graph, avoiding roads that are currently blocked.",
      {"type": "object", "properties": {
          "from_node": {"type": "string"}, "to_node": {"type": "string"},
          "kind": {"type": "string", "enum": ["boat", "van"]}},
       "required": ["from_node", "to_node"]})
def compute_route(from_node, to_node, kind="boat", blocked=None):
    blocked = blocked_roads() if blocked is None else blocked
    path = shortest_path(from_node, to_node, blocked)
    if not path:
        return {"found": False, "why": "no open route", "blocked": blocked}
    speed = VAN_METRES_PER_MIN if kind == "van" else BOAT_METRES_PER_MIN
    road_names = list(dict.fromkeys(path["roads"]))
    return {
        "found": True,
        "nodes": path["nodes"],
        "coords": [[nodes()[n]["lat"], nodes()[n]["lng"]] for n in path["nodes"]],
        "roads": road_names,
        "length_m": round(path["length_m"]),
        "eta_min": round(LAUNCH_MIN + path["cost_m"] / speed),
        "avoids": [b for b in blocked],
        "summary": describe_route(road_names, path["length_m"], blocked),
    }


def describe_route(road_names, length_m, blocked):
    text = f"{length_m / 1000:.1f} km via " + ", ".join(road_names)
    if blocked:
        text += "; avoids flooded " + ", ".join(blocked)
    return text
