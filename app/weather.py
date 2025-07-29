import requests

def get_coords_from_address(address: str) -> tuple[float, float] | None:
    """
    Geocodes an address in Belgium to latitude and longitude using the Nominatim API.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "countrycodes": "be",  # Restrict to Belgium
        "limit": 1
    }
    headers = {
        "User-Agent": "Windbased-Bikeplanner/2.0"
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
        return None
    except (requests.RequestException, IndexError, KeyError):
        return None

def get_wind_data(lat: float, lon: float) -> dict | None:
    """
    Fetches current wind data from the Open-Meteo API.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "wind_speed_10m,wind_direction_10m",
        "wind_speed_unit": "ms", # Use meters/second for calculations
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {
            "speed": data["current"]["wind_speed_10m"], # m/s
            "direction": data["current"]["wind_direction_10m"] # degrees
        }
    except (requests.RequestException, KeyError):
        return None
