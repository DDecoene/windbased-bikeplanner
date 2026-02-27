"""In-memory route cache with TTL for export endpoints."""

import time
import uuid
from typing import Any

_CACHE_TTL = 900  # 15 minutes
_MAX_ENTRIES = 500
_cache: dict[str, dict[str, Any]] = {}


def store(route_data: dict, wind_data: dict) -> str:
    """Store route data and return a unique route_id."""
    _cleanup()
    if len(_cache) >= _MAX_ENTRIES:
        oldest_key = min(_cache, key=lambda k: _cache[k]["expires"])
        del _cache[oldest_key]
    route_id = uuid.uuid4().hex
    _cache[route_id] = {
        "route_data": route_data,
        "wind_data": wind_data,
        "expires": time.time() + _CACHE_TTL,
    }
    return route_id


def get(route_id: str) -> dict | None:
    """Retrieve cached route data, or None if expired/missing."""
    _cleanup()
    entry = _cache.get(route_id)
    if entry is None or entry["expires"] < time.time():
        _cache.pop(route_id, None)
        return None
    return entry


def _cleanup() -> None:
    """Remove expired entries (piggyback on access)."""
    now = time.time()
    expired = [k for k, v in _cache.items() if v["expires"] < now]
    for k in expired:
        del _cache[k]
