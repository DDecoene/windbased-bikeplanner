"""Fetch weather data for today's rotating Flemish province.

Outputs JSON to /tmp/weather.json with current conditions,
7-day forecast, and best cycling day calculation.

Usage: python fetch_weather.py
"""
import json
import urllib.request
from datetime import datetime, date

PROVINCES = [
    {"name": "West-Vlaanderen", "city": "Brugge", "lat": 51.21, "lon": 3.22},
    {"name": "Oost-Vlaanderen", "city": "Gent", "lat": 51.05, "lon": 3.72},
    {"name": "Antwerpen", "city": "Antwerpen", "lat": 51.22, "lon": 4.40},
    {"name": "Vlaams-Brabant", "city": "Leuven", "lat": 50.88, "lon": 4.70},
    {"name": "Limburg", "city": "Hasselt", "lat": 50.93, "lon": 5.34},
]

# Wind direction labels in Dutch
WIND_DIRECTIONS = [
    "noorden", "noordoosten", "oosten", "zuidoosten",
    "zuiden", "zuidwesten", "westen", "noordwesten"
]


def get_today_province():
    """Deterministic daily rotation through provinces."""
    day_number = (date.today() - date(2026, 1, 1)).days
    return PROVINCES[day_number % len(PROVINCES)]


def degrees_to_direction(degrees):
    """Convert wind degrees to Dutch direction label."""
    index = round(degrees / 45) % 8
    return WIND_DIRECTIONS[index]


def calculate_cycling_score(temp_max, wind_speed, rain_prob):
    """Score a day for cycling: higher = better. Max ~100."""
    temp_score = max(0, min(30, temp_max - 5)) / 30 * 40  # 5-35°C range, max 40 pts
    wind_score = max(0, 40 - wind_speed)  # lower wind = higher score, max 40 pts
    rain_score = (100 - rain_prob) / 100 * 20  # no rain = 20 pts
    return round(temp_score + wind_score + rain_score, 1)


def fetch_weather(province):
    """Fetch current + 7-day forecast from Open-Meteo."""
    lat, lon = province["lat"], province["lon"]

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,wind_speed_10m,wind_direction_10m,"
        f"rain,weather_code"
        f"&daily=temperature_2m_max,temperature_2m_min,"
        f"wind_speed_10m_max,wind_direction_10m_dominant,"
        f"precipitation_probability_max,weather_code"
        f"&timezone=Europe/Brussels"
        f"&forecast_days=7"
    )

    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def main():
    province = get_today_province()
    print(f"Today's province: {province['name']} ({province['city']})")

    raw = fetch_weather(province)

    current = raw["current"]
    daily = raw["daily"]

    # Find best cycling day this week
    days = []
    for i in range(len(daily["time"])):
        score = calculate_cycling_score(
            daily["temperature_2m_max"][i],
            daily["wind_speed_10m_max"][i],
            daily["precipitation_probability_max"][i],
        )
        day_name_nl = _dutch_day_name(daily["time"][i])
        days.append({
            "date": daily["time"][i],
            "day_name_nl": day_name_nl,
            "temp_max": daily["temperature_2m_max"][i],
            "temp_min": daily["temperature_2m_min"][i],
            "wind_speed_max": daily["wind_speed_10m_max"][i],
            "wind_direction": degrees_to_direction(daily["wind_direction_10m_dominant"][i]),
            "rain_probability": daily["precipitation_probability_max"][i],
            "weather_code": daily["weather_code"][i],
            "cycling_score": score,
        })

    best_day = max(days, key=lambda d: d["cycling_score"])

    output = {
        "province": province["name"],
        "city": province["city"],
        "current": {
            "temperature": current["temperature_2m"],
            "wind_speed": current["wind_speed_10m"],
            "wind_direction": degrees_to_direction(current["wind_direction_10m"]),
            "rain": current["rain"],
            "weather_code": current["weather_code"],
        },
        "forecast_7_days": days,
        "best_cycling_day": best_day,
    }

    out_path = "/tmp/weather.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Weather data written to {out_path}")
    print(f"Current: {current['temperature_2m']}°C, wind {current['wind_speed_10m']} km/u uit het {output['current']['wind_direction']}")
    print(f"Best cycling day: {best_day['day_name_nl']} ({best_day['date']}) — score {best_day['cycling_score']}")


def _dutch_day_name(date_str):
    """Convert YYYY-MM-DD to Dutch day name."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    names = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
    return names[dt.weekday()]


if __name__ == "__main__":
    main()
