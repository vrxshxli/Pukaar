"""One interface for the two LLM modes.

rules:  deterministic extraction and matching from nlp.py. Always available.
ollama: a local model through Ollama's chat API with tool calling. Every call
        has a short timeout, and any error or timeout falls back to rules for
        that call, so the app keeps working if Ollama stops.

The model only reads and proposes. Tools that change the world (sending
messages, approvals, team status) are never offered to it.
"""
import ctypes
import json
import math
import os
import sys
import threading
import time

from . import db, nlp
from .tools import registry

HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "6"))
EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
HEALTH_EVERY = 20

_state = {"checked_at": 0.0, "available": False, "models": [], "fallbacks": 0, "calls": 0,
          "last_error": None, "last_source": "rules"}
_lock = threading.Lock()


def total_ram_gb():
    try:
        if sys.platform == "win32":
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(MemoryStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return status.ullTotalPhys / 1024 ** 3
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3
    except (OSError, ValueError, AttributeError):
        return 8.0


def chat_model():
    """qwen2.5:7b with 16 GB of RAM or more, otherwise qwen2.5:3b."""
    if os.environ.get("OLLAMA_MODEL"):
        return os.environ["OLLAMA_MODEL"]
    return "qwen2.5:7b" if total_ram_gb() >= 16 else "qwen2.5:3b"


def mode():
    return db.get_setting("llm_mode", "rules")


def _client(timeout=TIMEOUT):
    import ollama
    return ollama.Client(host=HOST, timeout=timeout)


def _has_model(name):
    base = name.split(":")[0]
    return any(m == name or m.split(":")[0] == base and (":" not in name or m == name) for m in _state["models"])


def check_health(force=False):
    """Is Ollama up, and is the chat model pulled? Cached for a few seconds."""
    with _lock:
        if not force and time.time() - _state["checked_at"] < HEALTH_EVERY:
            return _state["available"]
        _state["checked_at"] = time.time()
    try:
        listing = _client(timeout=1.5).list()
        models = [m.model for m in listing.models]
        _state["models"] = models
        _state["available"] = _has_model(chat_model())
        if not _state["available"]:
            _state["last_error"] = f"model {chat_model()} is not pulled (run: ollama pull {chat_model()})"
    except Exception as e:
        _state.update(available=False, models=[], last_error=f"Ollama unreachable: {type(e).__name__}")
    return _state["available"]


def status():
    use_ollama = mode() == "ollama"
    available = check_health() if use_ollama else _state["available"]
    effective = "ollama" if use_ollama and available else "rules"
    return {
        "mode": mode(),
        "effective": effective,
        "fallback": use_ollama and not available,
        "model": chat_model() if use_ollama else None,
        "embeddings": EMBED_MODEL if use_ollama and _has_model(EMBED_MODEL) else None,
        "available": available,
        "calls": _state["calls"],
        "fallbacks": _state["fallbacks"],
        "last_error": _state["last_error"] if use_ollama else None,
        "timeout_s": TIMEOUT,
    }


def _fallback(error):
    _state["fallbacks"] += 1
    _state["last_error"] = error
    _state["last_source"] = "rules (fallback)"


def _use_ollama():
    return mode() == "ollama" and check_health()


REPORT_TOOL = {
    "type": "function",
    "function": {
        "name": "record_report",
        "description": "Record the structured details of one citizen message from a flood.",
        "parameters": {
            "type": "object",
            "properties": {
                "language": {"type": "string", "enum": ["hi", "mr", "hinglish", "en"],
                             "description": "hi = Hindi in Devanagari, mr = Marathi, hinglish = Hindi in Latin letters"},
                "intent": {"type": "string", "enum": ["rescue", "welfare", "supplies", "rumour", "road_report",
                                                      "power_report", "question", "faq", "status_query", "safe_report", "other"]},
                "people": {"type": "integer", "description": "Number of people who need help, if stated"},
                "vulnerable": {"type": "array", "items": {"type": "string", "enum": ["elderly", "child", "pregnant", "disabled"]}},
                "medical": {"type": "array", "items": {"type": "string", "enum": ["unconscious", "breathing", "injured", "fever", "dialysis", "chronic"]}},
                "danger": {"type": "array", "items": {"type": "string", "enum": ["gas", "fire", "electrical"]}},
                "water_level": {"type": "string", "enum": ["ankle", "knee", "entering", "waist", "chest", "neck", "roof"]},
                "rising": {"type": "boolean"},
                "battery": {"type": "integer", "description": "Phone battery percent, if stated"},
                "location_text": {"type": "string", "description": "The exact location words: lane, gali, landmark"},
                "name": {"type": "string", "description": "Family or person name, if stated"},
            },
            "required": ["language", "intent"],
        },
    },
}

LISTEN_PROMPT = """You are Listen, an agent in a flood control room in Mumbai.
Read one citizen message (Hindi, Marathi, Hinglish or English) and call record_report exactly once.
Only record what the message says. Do not guess numbers that are not stated.
Copy the location words exactly into location_text; the control room geocodes them."""


def extract(text):
    """Structured report from a message: model first, rules always as the base."""
    rules = nlp.extract(text)
    if not _use_ollama():
        if mode() == "ollama":
            _fallback(_state["last_error"] or "Ollama unavailable")
        return rules, "rules"
    try:
        args, trace = run_tools(LISTEN_PROMPT, text, [], final_tool=REPORT_TOOL)
        if args is None:
            _fallback("model did not call record_report")
            return rules, "rules (fallback)"
        _state["last_source"] = "ollama"
        return merge_fields(rules, args), "ollama"
    except Exception as e:
        _fallback(f"{type(e).__name__}: {str(e)[:120]}")
        return rules, "rules (fallback)"


VALID = {p: set(s.get("enum") or s.get("items", {}).get("enum") or []) for p, s in
         REPORT_TOOL["function"]["parameters"]["properties"].items()}


def merge_fields(rules, model):
    """Combine the model's reading with the rules. Geocoding always comes from our gazetteer."""
    out = dict(rules)
    for key in ("vulnerable", "medical", "danger"):
        vals = model.get(key) or []
        if isinstance(vals, str):
            vals = [vals]
        out[key] = sorted(set(rules.get(key, [])) | {v for v in vals if v in VALID[key]})
    # The script decides Devanagari versus Latin; the model may only refine within a script.
    # Within Devanagari the Hindi and Marathi word markers are more reliable than a small model.
    same_script = {"hi": {"hi"}, "mr": {"mr"}, "en": {"en", "hinglish"}, "hinglish": {"en", "hinglish"}}
    if model.get("language") in same_script[rules["language"]]:
        out["language"] = model["language"]
    if model.get("intent") in VALID["intent"]:
        # Rules are exact for rumours, reposts and safe reports, so they win there.
        if rules["intent"] not in ("rumour", "safe_report", "faq"):
            out["intent"] = model["intent"]
    if model.get("water_level") in VALID["water_level"] and not rules.get("water_level"):
        out["water_level"] = model["water_level"]
    for key in ("people", "battery"):
        v = model.get(key)
        if isinstance(v, str) and v.isdigit():
            v = int(v)
        implied_floor = rules.get("people") if key == "people" and rules.get("people_implied") else 0
        if isinstance(v, int) and max(0, implied_floor or 0) <= v < 200 and v > 0 and                 (rules.get(key) is None or rules.get("people_implied")):
            out[key] = v
            if key == "people":
                out["people_implied"] = False
    if model.get("rising") is True:
        out["rising"] = True
    if model.get("location_text") and not rules.get("location_found"):
        from .tools import geo
        g = geo.geocode_landmark(model["location_text"])
        if g["found"]:
            out.update(location_found=True, lane=g["lane"], landmark=g["landmark"], lat=g["lat"], lng=g["lng"],
                       node=g["node"], geo_confidence=g["confidence"], location_text=g["why"])
    name = str(model.get("name") or "").strip()
    if name and not rules.get("name") and looks_like_name(name):
        out["name"] = name[:60]
    return out


GENERIC_WORDS = {"amma", "budhi", "budha", "bachcha", "people", "family", "members", "mother", "father", "grandmother",
                 "child", "old", "lady", "uncle", "aunty", "dadi", "nani", "aaji", "neighbour"}


def looks_like_name(name):
    words = name.split()
    if not 1 <= len(words) <= 3 or any(ch.isdigit() for ch in name) or any(p in name for p in ",.!?…।"):
        return False
    return not any(w.lower() in GENERIC_WORDS for w in words)


def run_tools(system, user, tool_names, final_tool=None, max_steps=3):
    """A small tool-calling loop. Returns the final tool's arguments (or the text) and a trace."""
    client = _client()
    tools = registry.ollama_schemas(tool_names) + ([final_tool] if final_tool else [])
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    trace = []
    started = time.time()
    for _ in range(max_steps):
        if time.time() - started > TIMEOUT:
            raise TimeoutError("tool loop took too long")
        _state["calls"] += 1
        response = client.chat(model=chat_model(), messages=messages, tools=tools, options={"temperature": 0})
        msg = response.message
        calls = msg.tool_calls or []
        if not calls:
            return (None if final_tool else msg.content), trace
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
            {"function": {"name": c.function.name, "arguments": c.function.arguments}} for c in calls]})
        for c in calls:
            name, args = c.function.name, dict(c.function.arguments or {})
            trace.append({"tool": name, "args": args})
            if final_tool and name == final_tool["function"]["name"]:
                return args, trace
            if name not in tool_names or not registry.TOOLS[name].model_safe:
                result = {"error": "tool not allowed"}
            else:
                try:
                    result = registry.TOOLS[name].fn(**args)
                except TypeError as e:
                    result = {"error": str(e)}
            messages.append({"role": "tool", "content": json.dumps(result, ensure_ascii=False, default=str)})
    return None, trace


SAATHI_PROMPT = """You are Saathi, a safety helper. Decide which safety playbook answers the user's question.
Call search_playbook with the question and the hazard id: flood, fire, gas_leak, heat or electrical.
If none fits, do not call any tool."""


def pick_playbook(text):
    """Ask the model which playbook fits. Returns a playbook id, or None to use the keyword match."""
    if not _use_ollama():
        return None
    try:
        _, trace = run_tools(SAATHI_PROMPT, text, ["search_playbook"], max_steps=1)
        for step in trace:
            hazard = step["args"].get("hazard")
            if hazard in ("flood", "fire", "gas_leak", "heat", "electrical"):
                return hazard
    except Exception as e:
        _fallback(f"{type(e).__name__}: {str(e)[:120]}")
    return None


def warm_up():
    """Load the model in the background so the first real call does not time out."""
    def run():
        if check_health(force=True):
            try:
                _client(timeout=120).chat(model=chat_model(), messages=[{"role": "user", "content": "ok"}],
                                          options={"num_predict": 1})
            except Exception as e:
                _state["last_error"] = f"warm-up failed: {type(e).__name__}"
    threading.Thread(target=run, daemon=True, name="ollama-warm-up").start()


_embed_cache = {}


def embed(text):
    if text in _embed_cache:
        return _embed_cache[text]
    if not _has_model(EMBED_MODEL):
        return None
    try:
        vec = _client(timeout=TIMEOUT).embed(model=EMBED_MODEL, input=text).embeddings[0]
    except Exception as e:
        _fallback(f"embedding failed: {type(e).__name__}")
        return None
    _embed_cache[text] = vec
    return vec


def similarity(a, b):
    """Cosine similarity of two messages using embeddings, or None if unavailable."""
    if not _use_ollama():
        return None
    va, vb = embed(a), embed(b)
    if not va or not vb:
        return None
    dot = sum(x * y for x, y in zip(va, vb))
    norm = math.sqrt(sum(x * x for x in va)) * math.sqrt(sum(y * y for y in vb))
    return dot / norm if norm else None
