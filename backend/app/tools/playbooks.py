"""Looks up safety steps in the approved playbooks. Saathi answers only from these."""
import json
from functools import lru_cache

from ..scenario import DATA_DIR
from .registry import tool


@lru_cache
def playbooks():
    out = {}
    for path in sorted((DATA_DIR / "playbooks").glob("*.json")):
        pb = json.loads(path.read_text(encoding="utf-8"))
        out[pb["id"]] = pb
    return out


def match_hazards(text):
    """Return playbook ids whose keywords appear in the text, most hits first."""
    t = (text or "").lower()
    scored = []
    for pb in playbooks().values():
        hits = sum(1 for k in pb["keywords"] if k.lower() in t)
        if hits:
            # Danger playbooks win ties, because they need the emergency number first.
            scored.append((hits + (0.5 if pb["danger"] else 0), pb["id"]))
    return [pid for _, pid in sorted(scored, reverse=True)]


@tool("search_playbook",
      "Find the approved safety playbook that answers a 'what do I do now' question. Returns the steps in the requested language, or covered=false.",
      {"type": "object", "properties": {
          "question": {"type": "string"},
          "language": {"type": "string", "enum": ["en", "hi", "mr"]},
          "hazard": {"type": "string", "enum": ["flood", "fire", "gas_leak", "heat", "electrical"]}},
       "required": ["question"]})
def search_playbook(question, language="en", hazard=None):
    ids = [hazard] if hazard else match_hazards(question)
    if not ids:
        return {"covered": False}
    pb = playbooks()[ids[0]]
    lang = language if language in pb["steps"] else "en"
    return {
        "covered": True,
        "playbook": pb["id"],
        "danger": pb["danger"],
        "title": pb["title"][lang],
        "steps": pb["steps"][lang],
        "emergency": pb["emergency"]["number"],
        "emergency_also": pb["emergency"].get("also"),
        "emergency_label": pb["emergency"]["label"][lang],
        "language": lang,
    }
