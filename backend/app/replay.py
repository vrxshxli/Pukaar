"""Flood-night replay: feeds the generated night through the real pipeline.

Messages are released when the game clock reaches their time, so changing the
clock speed changes the replay speed. Volunteer events in the night (such as
Lane 6 flooding) go through the same path as a tap in the volunteer view.
"""
import json
import logging
import threading
from datetime import datetime
from functools import lru_cache

from . import db, events, orchestrator
from .scenario import SCENARIO_DIR

log = logging.getLogger("pukaar.replay")
_state = {"state": "idle", "speed": 0, "sent": 0, "total": 0, "next_at": None}
_stop = threading.Event()
_thread = None


@lru_cache
def night():
    data = json.loads((SCENARIO_DIR / "flood_night.json").read_text(encoding="utf-8"))
    items = [{"kind": "message", **m} for m in data["messages"]] + [{"kind": "event", **e} for e in data["events"]]
    return sorted(items, key=lambda i: i["time"])


def status():
    return dict(_state)


def feed(item):
    """Push one item of the night through the pipeline, exactly as a live input would arrive."""
    if item["kind"] == "message":
        return orchestrator.handle_message(item["phone"], item["text"], channel=item["channel"], name=item.get("sender"))
    if item["type"] == "volunteer":
        return orchestrator.handle_volunteer(item["team"], item["action"], road=item.get("road"))
    return None


def start(speed=10):
    """Reset the ward and play the night from 9:30 PM."""
    stop()
    orchestrator.reset()
    db.set_setting("auto_field", "on")
    items = night()
    db.set_clock(datetime.fromisoformat(items[0]["time"]).replace(hour=21, minute=30), speed=speed)
    _state.update(state="playing", speed=speed, sent=0, total=len(items), next_at=items[0]["time"])
    _stop.clear()
    global _thread
    _thread = threading.Thread(target=_run, args=(items,), daemon=True, name="replay")
    _thread.start()
    events.publish("changed", {"what": "replay"})


def _run(items):
    index = 0
    while not _stop.is_set() and index < len(items):
        now = db.now_iso()
        while index < len(items) and items[index]["time"] <= now and not _stop.is_set():
            try:
                feed(items[index])
            except Exception:
                log.exception("replay item %s failed", items[index].get("id"))
            index += 1
            _state.update(sent=index, next_at=items[index]["time"] if index < len(items) else None)
        _stop.wait(0.2)
    if index >= len(items):
        _state.update(state="finished")
        events.publish("changed", {"what": "replay"})


def pause():
    if _state["state"] == "playing":
        db.set_clock_speed(0)
        _state.update(state="paused")
        events.publish("changed", {"what": "replay"})


def resume(speed=None):
    if _state["state"] == "paused":
        speed = speed or _state["speed"] or 10
        db.set_clock_speed(speed)
        _state.update(state="playing", speed=speed)
        events.publish("changed", {"what": "replay"})


def set_speed(speed):
    _state["speed"] = speed
    if _state["state"] == "playing":
        db.set_clock_speed(speed)
    events.publish("changed", {"what": "replay"})


def stop():
    _stop.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout=5)
    _state.update(state="idle", sent=0, next_at=None)
