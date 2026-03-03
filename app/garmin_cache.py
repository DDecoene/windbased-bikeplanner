"""In-memory TTL cache for Garmin OAuth PKCE state parameters."""

import time
from typing import Any

_CACHE_TTL = 300  # 5 minutes — enough for OAuth redirect
_cache: dict[str, dict[str, Any]] = {}


def store(state: str, code_verifier: str, user_id: str, return_path: str = "/") -> None:
    _cleanup()
    _cache[state] = {
        "code_verifier": code_verifier,
        "user_id": user_id,
        "return_path": return_path,
        "expires": time.time() + _CACHE_TTL,
    }


def get(state: str) -> dict[str, Any] | None:
    _cleanup()
    entry = _cache.get(state)
    if entry is None or entry["expires"] < time.time():
        _cache.pop(state, None)
        return None
    _cache.pop(state)  # one-time use
    return entry


def _cleanup() -> None:
    now = time.time()
    expired = [k for k, v in _cache.items() if v["expires"] < now]
    for k in expired:
        del _cache[k]
