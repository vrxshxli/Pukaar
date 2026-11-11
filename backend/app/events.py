"""A tiny publish and subscribe bus that feeds the server-sent events stream.

Agents run in worker threads, while the SSE endpoint lives on the asyncio
loop, so publishing hands each event to the loop in a thread-safe way.
"""
import asyncio
import json
import threading

_subscribers = set()
_lock = threading.Lock()
_loop = None


def bind_loop(loop):
    global _loop
    _loop = loop


def subscribe():
    queue = asyncio.Queue(maxsize=500)
    with _lock:
        _subscribers.add(queue)
    return queue


def unsubscribe(queue):
    with _lock:
        _subscribers.discard(queue)


def publish(kind, data=None):
    if _loop is None:
        return
    payload = json.dumps({"kind": kind, "data": data or {}}, ensure_ascii=False, default=str)
    with _lock:
        queues = list(_subscribers)
    for queue in queues:
        _loop.call_soon_threadsafe(_offer, queue, payload)


def _offer(queue, payload):
    # A slow browser tab should never block the agents, so drop if full.
    if not queue.full():
        queue.put_nowait(payload)
