"""Rainfall from Open-Meteo (free, no key), with a mock fallback when offline."""
import time

import httpx

from .. import scenario
from .registry import tool

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
CACHE_SECONDS = 600
_cache = {"at": 0.0, "value": None}


@tool("get_rainfall",
      "Get current and next-6-hours rainfall in millimetres for the ward from Open-Meteo.",
      {"type": "object", "properties": {}})
def get_rainfall(timeout=4.0):
    if _cache["value"] and time.time() - _cache["at"] < CACHE_SECONDS:
        return _cache["value"]
    center = scenario.ward()["center"]
    try:
        response = httpx.get(OPEN_METEO, timeout=timeout, params={
            "latitude": center["lat"], "longitude": center["lng"],
            "current": "precipitation,rain", "hourly": "precipitation",
            "forecast_hours": 6, "timezone": "Asia/Kolkata",
        })
        response.raise_for_status()
        data = response.json()
        value = {
            "source": "open-meteo",
            "now_mm": data["current"].get("precipitation", 0.0),
            "next_6h_mm": round(sum(x or 0 for x in data["hourly"]["precipitation"][:6]), 1),
            "fetched_for": data["current"].get("time"),
        }
    except (httpx.HTTPError, KeyError, ValueError):
        # Offline or blocked: use the scenario's flood-night figures instead.
        value = {"source": "mock (Open-Meteo unreachable)", "now_mm": 38.0, "next_6h_mm": 160.0}
    _cache.update(at=time.time(), value=value)
    return value
