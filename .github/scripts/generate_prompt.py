"""Build the prompt for Claude to generate a social media post.

Reads weather data and post history, outputs the prompt to stdout.

Usage: python generate_prompt.py
"""
import json
from pathlib import Path

WEATHER_FILE = Path("/tmp/weather.json")
HISTORY_FILE = Path(".github/data/post_history.json")

STRATEGIES = [
    {
        "name": "wind-reactive",
        "description": "Gebruik de huidige windcondities om rgwnd te promoten. Verwijs naar windsnelheid, -richting en hoe rgwnd je route optimaliseert voor rugwind.",
        "example": "In Brugge waait het vandaag 20 km/u uit het zuidwesten. Laat rgwnd je een lus plannen richting de kust — de hele weg wind mee op de terugweg."
    },
    {
        "name": "forecast-teaser",
        "description": "Verwijs naar een geweldige fietsdag die eraan komt deze week. Creëer anticipatie.",
        "example": "Woensdag wordt DE dag in Gent: 19°C, amper wind, droog. Plan nu al je route op rgwnd en geniet woensdag van perfecte omstandigheden."
    },
    {
        "name": "best-day-of-week",
        "description": "Kroon de beste fietsdag van de week op basis van de 7-daagse voorspelling. Gebruik specifieke cijfers.",
        "example": "Beste fietsdag deze week in Antwerpen? Donderdag. 17°C, 8 km/u wind, 0% regen. Plan je knooppuntenroute op rgwnd."
    },
    {
        "name": "seasonal-cultural",
        "description": "Koppel aan Belgische wielercultuur, het seizoen, of wielerevenementen. Denk aan voorjaar, knooppunten, koersen.",
        "example": "Het wielerseizoen is geopend in Limburg! De knooppuntenroutes liggen er weer perfect bij. Laat rgwnd je de mooiste lus plannen — met rugwind als bonus."
    },
    {
        "name": "feature-spotlight",
        "description": "Belicht een specifieke rgwnd-functie: GPX-export, 16 dagen vooruit plannen, knooppuntennetwerk, windoptimalisatie, gratis account.",
        "example": "Wist je dat rgwnd tot 16 dagen vooruit kan plannen? Check nu wanneer de wind het beste is voor je volgende rit vanuit Leuven."
    },
    {
        "name": "contrarian-weather",
        "description": "Slecht weer? Perfect moment om vooruit te plannen. Draai negatief weer om naar een reden om rgwnd te gebruiken.",
        "example": "Regen in Hasselt vandaag? Ideaal moment om op rgwnd je weekendroute te plannen. Zaterdag wordt droog met wind uit het zuiden — perfect voor een lus naar het noorden."
    },
    {
        "name": "distance-challenge",
        "description": "Wind mee = verder fietsen. Moedig langere ritten aan dankzij windoptimalisatie.",
        "example": "Met rugwind trap je makkelijk 20 km verder. Plan een ambitieuze 100 km lus vanuit Gent op rgwnd en laat de wind het werk doen."
    },
]


def load_weather():
    return json.loads(WEATHER_FILE.read_text())


def load_post_history():
    try:
        return json.loads(HISTORY_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"posts": []}


def main():
    weather = load_weather()
    history = load_post_history()

    recent_posts = history.get("posts", [])[-30:]
    recent_strategies = [p.get("strategy", "") for p in recent_posts[-3:]]
    recent_texts = [p.get("text", "") for p in recent_posts[-10:]]

    province = weather["province"]
    city = weather["city"]
    current = weather["current"]
    best_day = weather["best_cycling_day"]
    forecast = weather["forecast_7_days"]

    strategies_text = ""
    for s in STRATEGIES:
        marker = " (VERMIJD — recent gebruikt)" if s["name"] in recent_strategies else ""
        strategies_text += f"\n### {s['name']}{marker}\n{s['description']}\nVoorbeeld: \"{s['example']}\"\n"

    forecast_text = ""
    for day in forecast:
        forecast_text += (
            f"- {day['day_name_nl']} {day['date']}: "
            f"{day['temp_max']}°C, wind {day['wind_speed_max']} km/u uit het {day['wind_direction']}, "
            f"{day['rain_probability']}% regen, fietsscore {day['cycling_score']}\n"
        )

    prompt = f"""Je bent een social media expert voor rgwnd — een fietsrouteplanner die lusroutes optimaliseert voor rugwind op het Belgische fietsknooppuntennetwerk. Je schrijft in het Nederlands.

## Huidige weer in {city} ({province})

- Temperatuur: {current['temperature']:.0f}°C
- Wind: {current['wind_speed']:.0f} km/u uit het {current['wind_direction']}
- Regen: {current['rain']} mm
- Weercode: {current['weather_code']}

## 7-daagse voorspelling voor {city}

{forecast_text}

## Beste fietsdag deze week

{best_day['day_name_nl']} ({best_day['date']}): {best_day['temp_max']}°C, wind {best_day['wind_speed_max']} km/u, {best_day['rain_probability']}% regen — fietsscore {best_day['cycling_score']}

## Beschikbare strategieën

Kies de strategie die het beste past bij het huidige weer en de voorspelling. Vermijd strategieën die recent zijn gebruikt (gemarkeerd).

{strategies_text}

## Recente posts (NIET herhalen)

{chr(10).join(f'- "{t}"' for t in recent_texts) if recent_texts else 'Nog geen posts — dit is de eerste!'}

## Opdracht

Schrijf EEN social media post voor rgwnd. Regels:
- Maximum 280 tekens
- In het Nederlands
- Verwijs naar {city} of {province}
- Vermeld rgwnd op een natuurlijke manier (geen link, geen URL)
- Geen hashtags
- Kies een strategie die NIET in de laatste 3 posts is gebruikt
- Gebruik specifieke cijfers uit het weer (temperatuur, windsnelheid, etc.)
- Toon is: enthousiast, praktisch, uitnodigend — niet schreeuwerig of salesy
- De post moet op zichzelf staan en nieuwsgierigheid wekken

Antwoord met ALLEEN de post-tekst op de eerste regel, gevolgd door een lege regel, gevolgd door de naam van de gebruikte strategie op de derde regel. Niets anders. Geen aanhalingstekens, geen uitleg.

Voorbeeld output:
In Brugge waait het vandaag 15 km/u uit het westen — perfect voor een knooppuntenroute richting de kust met rugwind. Plan je rit op rgwnd.

wind-reactive"""

    print(prompt)


if __name__ == "__main__":
    main()
