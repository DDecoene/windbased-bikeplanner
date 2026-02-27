"""Shared wind utility functions."""

CARDINAL_DIRS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


def degrees_to_cardinal(deg: float) -> str:
    ix = round(deg / (360 / len(CARDINAL_DIRS)))
    return CARDINAL_DIRS[ix % len(CARDINAL_DIRS)]


def wind_arrow_rotation(direction_deg: float) -> float:
    return (direction_deg + 180) % 360
