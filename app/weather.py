import logging
import time
from datetime import datetime, timezone
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
FORECAST_WIND_TTL_SECONDS = 3600  # 1 uur voor voorspelde wind

_FORECAST_WIND_CACHE: Dict[tuple, dict] = {}
_FORECAST_WIND_TTL: Dict[tuple, float] = {}

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
    from .notify import send_alert
    max_retries = 2

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code in (429, 503, 504) and attempt < max_retries:
                logger.warning("Nominatim HTTP %d, poging %d/%d", response.status_code, attempt + 1, max_retries + 1)
                time.sleep(2 ** attempt)
                continue
            response.raise_for_status()
            data = response.json()
            if data:
                coords = (float(data[0]["lat"]), float(data[0]["lon"]))
                _GEOCODE_CACHE[key] = coords
                _GEOCODE_TTL[key] = _now() + GEOCODE_TTL_SECONDS
                return coords
            return None
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt < max_retries:
                logger.warning("Nominatim fout (poging %d/%d): %s", attempt + 1, max_retries + 1, e)
                time.sleep(2 ** attempt)
                continue
            logger.error("Nominatim geocoding fout na %d pogingen: %s", max_retries + 1, e)
            send_alert(f"Nominatim geocoding fout na {max_retries + 1} pogingen: {e}")
            return None
        except (requests.RequestException, IndexError, KeyError) as e:
            logger.error("Nominatim geocoding fout: %s", e)
            send_alert(f"Nominatim geocoding fout: {e}")
            return None
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
    from .notify import send_alert
    max_retries = 2

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code in (429, 503, 504) and attempt < max_retries:
                logger.warning("Open-Meteo HTTP %d, poging %d/%d", response.status_code, attempt + 1, max_retries + 1)
                time.sleep(2 ** attempt)
                continue
            response.raise_for_status()
            data = response.json()
            wind = {
                "speed": data["current"]["wind_speed_10m"],  # m/s
                "direction": data["current"]["wind_direction_10m"],  # degrees
            }
            _WIND_CACHE[loc] = wind
            _WIND_TTL[loc] = _now() + WIND_TTL_SECONDS
            return wind
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt < max_retries:
                logger.warning("Open-Meteo fout (poging %d/%d): %s", attempt + 1, max_retries + 1, e)
                time.sleep(2 ** attempt)
                continue
            logger.error("Open-Meteo wind API fout na %d pogingen: %s", max_retries + 1, e)
            send_alert(f"Open-Meteo wind API fout na {max_retries + 1} pogingen: {e}")
            return None
        except (requests.RequestException, KeyError) as e:
            logger.error("Open-Meteo wind API fout: %s", e)
            send_alert(f"Open-Meteo wind API fout: {e}")
            return None
    return None


def get_forecast_wind_data(lat: float, lon: float, target_dt: datetime) -> Optional[dict]:
    """
    Fetches forecasted wind data for a specific future hour from Open-Meteo.
    Uses hourly forecast endpoint. Cached for 1 hour.
    """
    loc = (round(lat, 4), round(lon, 4))
    # Round to nearest hour for cache key
    target_hour = target_dt.replace(minute=0, second=0, microsecond=0)
    cache_key = (loc[0], loc[1], target_hour.isoformat())
    ts = _FORECAST_WIND_TTL.get(cache_key)
    if ts and _now() < ts:
        return _FORECAST_WIND_CACHE.get(cache_key)

    # Calculate forecast_days needed (from today to the target date)
    now_utc = datetime.now(timezone.utc)
    target_utc = target_dt if target_dt.tzinfo else target_dt.replace(tzinfo=timezone.utc)
    days_ahead = (target_utc.date() - now_utc.date()).days
    forecast_days = max(days_ahead + 1, 1)
    forecast_days = min(forecast_days, 16)

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "wind_speed_10m,wind_direction_10m",
        "wind_speed_unit": "ms",
        "forecast_days": forecast_days,
        "timezone": "Europe/Brussels",
    }
    from .notify import send_alert
    max_retries = 2

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code in (429, 503, 504) and attempt < max_retries:
                logger.warning("Open-Meteo forecast HTTP %d, poging %d/%d", response.status_code, attempt + 1, max_retries + 1)
                time.sleep(2 ** attempt)
                continue
            response.raise_for_status()
            data = response.json()

            # Find the closest hour in the forecast
            hourly = data["hourly"]
            times = hourly["time"]  # list of "YYYY-MM-DDTHH:MM" strings
            target_str = target_hour.strftime("%Y-%m-%dT%H:%M")

            # Find matching hour
            idx = None
            for i, t in enumerate(times):
                if t == target_str:
                    idx = i
                    break

            if idx is None:
                # Fall back to closest available hour
                logger.warning("Forecast uur %s niet gevonden, dichtstbijzijnde wordt gebruikt", target_str)
                # Find closest time
                min_diff = float("inf")
                for i, t in enumerate(times):
                    try:
                        forecast_dt = datetime.strptime(t, "%Y-%m-%dT%H:%M")
                        diff = abs((forecast_dt - target_hour.replace(tzinfo=None)).total_seconds())
                        if diff < min_diff:
                            min_diff = diff
                            idx = i
                    except ValueError:
                        continue
                if idx is None:
                    logger.error("Geen bruikbaar forecast-uur gevonden")
                    return None

            wind = {
                "speed": hourly["wind_speed_10m"][idx],
                "direction": hourly["wind_direction_10m"][idx],
            }
            _FORECAST_WIND_CACHE[cache_key] = wind
            _FORECAST_WIND_TTL[cache_key] = _now() + FORECAST_WIND_TTL_SECONDS
            return wind
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt < max_retries:
                logger.warning("Open-Meteo forecast fout (poging %d/%d): %s", attempt + 1, max_retries + 1, e)
                time.sleep(2 ** attempt)
                continue
            logger.error("Open-Meteo forecast API fout na %d pogingen: %s", max_retries + 1, e)
            send_alert(f"Open-Meteo forecast API fout na {max_retries + 1} pogingen: {e}")
            return None
        except (requests.RequestException, KeyError) as e:
            logger.error("Open-Meteo forecast API fout: %s", e)
            send_alert(f"Open-Meteo forecast API fout: {e}")
            return None
    return None
