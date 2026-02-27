"""GPX file generation from route data."""

from datetime import datetime, timezone
from xml.sax.saxutils import escape

from .wind_utils import degrees_to_cardinal


def generate_gpx(route_data: dict, wind_data: dict) -> str:
    """Generate GPX XML string from route data.

    Args:
        route_data: Dict with keys: start_address, actual_distance_km,
            junctions, junction_coords, route_geometry, planned_datetime.
        wind_data: Dict with keys: speed, direction.

    Returns:
        GPX XML string.
    """
    now = datetime.now(timezone.utc).isoformat()
    wind_kmh = f"{wind_data['speed'] * 3.6:.1f}"
    wind_dir = degrees_to_cardinal(wind_data["direction"])
    wind_label = "Voorspelde wind" if route_data.get("planned_datetime") else "Wind"

    planned_note = ""
    if route_data.get("planned_datetime"):
        planned_note = f" Gepland: {route_data['planned_datetime']}."

    addr = escape(route_data["start_address"])
    dist = route_data["actual_distance_km"]
    junctions_str = " → ".join(route_data["junctions"])

    gpx = f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="RGWND" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>{addr} — {dist} km</name>
    <desc>{wind_label}: {wind_kmh} km/h {wind_dir}. Knooppunten: {junctions_str}{planned_note}</desc>
    <time>{now}</time>
  </metadata>
"""

    for jc in route_data["junction_coords"]:
        ref = escape(str(jc["ref"]))
        gpx += f'  <wpt lat="{jc["lat"]}" lon="{jc["lon"]}"><name>Knooppunt {ref}</name></wpt>\n'

    gpx += f"  <trk>\n    <name>{addr}</name>\n    <trkseg>\n"
    for segment in route_data["route_geometry"]:
        for lat, lon in segment:
            gpx += f'      <trkpt lat="{lat}" lon="{lon}"></trkpt>\n'
    gpx += "    </trkseg>\n  </trk>\n</gpx>"

    return gpx
