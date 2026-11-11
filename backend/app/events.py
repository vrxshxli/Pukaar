"""A tiny publish and subscribe bus that feeds the server-sent events stream.

Agents run in worker threads, while the SSE endpoint lives on the asyncio
loop, so publishing hands each event to the loop in a thread-safe way.
Each subscriber can pass a filter, so a citizen's phone only receives its
own chat messages and a volunteer only their team's tasks.
"""
import asyncio
import json
import threading

_subscribers = {}
_lock = threading.Lock()
_loop = None


def bind_loop(loop):
    global _loop
    _loop = loop


def subscribe(accept=None):
    queue = asyncio.Queue(maxsize=500)
    with _lock:
        _subscribers[queue] = accept or (lambda kind, data: True)
    return queue


def unsubscribe(queue):
    with _lock:
        _subscribers.pop(queue, None)


def publish(kind, data=None):
    if _loop is None:
        return
    data = data or {}
    payload = json.dumps({"kind": kind, "data": data}, ensure_ascii=False, default=str)
    with _lock:
        targets = [q for q, accept in _subscribers.items() if _safe_accept(accept, kind, data)]
    for queue in targets:
        _loop.call_soon_threadsafe(_offer, queue, payload)


def _safe_accept(accept, kind, data):
    try:
        return accept(kind, data)
    except Exception:
        return False


def _offer(queue, payload):
    # A slow browser tab should never block the agents, so drop if full.
    if not queue.full():
        queue.put_nowait(payload)
