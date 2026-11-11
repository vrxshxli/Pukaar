"""Flood-night replay. Filled in with the generated night in milestone 7."""
_state = {"state": "idle", "speed": 0, "sent": 0, "total": 0}


def status():
    return dict(_state)


def stop():
    _state.update(state="idle", sent=0)
