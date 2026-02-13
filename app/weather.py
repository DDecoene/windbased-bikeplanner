import logging
import time
import requests
from typing import Optional, Tuple, Dict

logger = logging.getLogger(__name__)

# Simple in-memory TTL caches
_GEOCODE_CACHE: Dict[str, tuple[float, float]] = {}
_GEOCODE_TTL: Dict[str, float] = {}

_WIND_CACHE: Dict[tuple[float, float], dict] = {}
_WIND_TTL: Dict[tuple[float, float], float] = {}

GEOCODE_TTL_SECONDS = 24 * 3600   # 24u is prima voor adres-coördinaten
WIND_TTL_SECONDS = 10 * 60        # 10 minuten voor actuele wind

def _now() -> float:
    return time.time()

def get_coords_from_address(address: str) -> Optional[tuple[float, float]]:
    """
    Geocodes an address in Belgium to latitude and longitude using the Nominatim API.
    Cached for 24h.
    """
    key = address.strip().lower()
    ts = _GEOCODE_TTL.get(key)
    if ts and _now() < ts:
        return _GEOCODE_CACHE.get(key)

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "countrycodes": "be",
        "limit": 1
    }
    headers = {
        "User-Agent": "RGWND/2.0 (+contact: dev)"
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data:
            coords = (float(data[0]["lat"]), float(data[0]["lon"]))
            _GEOCODE_CACHE[key] = coords
            _GEOCODE_TTL[key] = _now() + GEOCODE_TTL_SECONDS
            return coords
        return None
    except (requests.RequestException, IndexError, KeyError) as e:
        logger.error("Nominatim geocoding fout: %s", e)
        from .notify import send_alert
        send_alert(f"Nominatim geocoding fout: {e}")
        return None

def get_wind_data(lat: float, lon: float) -> Optional[dict]:
    """
    Fetches current wind data from the Open-Meteo API.
    Cached for 10 minutes.
    """
    loc = (round(lat, 4), round(lon, 4))  # round to improve cache hit rate
    ts = _WIND_TTL.get(loc)
    if ts and _now() < ts:
        return _WIND_CACHE.get(loc)

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "wind_speed_10m,wind_direction_10m",
        "wind_speed_unit": "ms",
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        wind = {
            "speed": data["current"]["wind_speed_10m"],  # m/s
            "direction": data["current"]["wind_direction_10m"],  # degrees
        }
        _WIND_CACHE[loc] = wind
        _WIND_TTL[loc] = _now() + WIND_TTL_SECONDS
        return wind
    except (requests.RequestException, KeyError) as e:
        logger.error("Open-Meteo wind API fout: %s", e)
        from .notify import send_alert
        send_alert(f"Open-Meteo wind API fout: {e}")
        return None
