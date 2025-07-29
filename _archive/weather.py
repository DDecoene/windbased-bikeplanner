import requests
import numpy as np

def get_coords_from_address(address: str) -> tuple[float, float] | None:
    """
    Geocodes an address in Belgium to latitude and longitude using the Nominatim API.

    Args:
        address: The address string to geocode.

    Returns:
        A tuple of (latitude, longitude) or None if not found.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "countrycodes": "be",  # Restrict to Belgium
        "limit": 1
    }
    headers = {
        "User-Agent": "Windbased-Bikeplanner/1.0 (https://github.com/DDecoene/windbased-bikeplanner)"
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

    Args:
        lat: Latitude for the location.
        lon: Longitude for the location.

    Returns:
        A dictionary containing wind speed and direction, or None on error.
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

def format_wind_data_for_ui(wind_data: dict) -> tuple[str, str]:
    """
    Formats wind data for display in the Streamlit UI.

    Args:
        wind_data: A dictionary with 'speed' (m/s) and 'direction' (degrees).

    Returns:
        A tuple of formatted strings (wind_speed_kmh, wind_direction_cardinal).
    """
    if not wind_data:
        return "N/A", "N/A"

    speed_kmh = wind_data["speed"] * 3.6
    direction_deg = wind_data["direction"]
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    ix = round(direction_deg / (360. / len(dirs)))
    direction_cardinal = dirs[ix % len(dirs)]

    return f"{speed_kmh:.1f} km/h", direction_cardinal

def get_wind_arrow_html(direction_degrees: float) -> str:
    """
    Generates an HTML string for an SVG arrow rotated to show the direction of wind flow.

    Args:
        direction_degrees: The meteorological wind direction (where the wind comes FROM).

    Returns:
        An HTML string containing the correctly rotated SVG arrow.
    """
    # --- FIX IS HERE ---
    # To point where the wind is going TO, we add 180 degrees to the meteorological direction.
    visual_rotation = (direction_degrees + 180) % 360

    arrow_svg = """
    <svg width="24" height="24" viewBox="-12 -12 24 24">
        <g transform="rotate({rotation})">
            <path d="M 0 -10 L 8 0 L 2 0 L 2 8 L -2 8 L -2 0 L -8 0 Z" fill="#333333" />
        </g>
    </svg>
    """
    # Use the corrected visual_rotation in the format string.
    return arrow_svg.format(rotation=visual_rotation)