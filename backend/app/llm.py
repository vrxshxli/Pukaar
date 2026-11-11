"""One interface for the two LLM modes.

rules:  deterministic extraction and matching from nlp.py. Always available.
ollama: a local model through Ollama (added in llm_ollama.py). Any error or
        timeout falls back to rules for that call.
"""
from . import db, nlp


def mode():
    return db.get_setting("llm_mode", "rules")


def status():
    return {"mode": mode(), "effective": "rules", "model": None, "fallbacks": 0}


def extract(text):
    """Structured report from a message."""
    return nlp.extract(text), "rules"


def similarity(a, b):
    """Meaning similarity between two messages, or None when unavailable."""
    return None
