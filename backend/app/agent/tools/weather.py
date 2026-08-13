import json

import httpx

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain",
    66: "freezing rain", 67: "heavy freezing rain",
    71: "slight snow", 73: "moderate snow", 75: "heavy snow", 77: "snow grains",
    80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
    85: "snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with heavy hail",
}


async def run(location: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            geo = await client.get(
                GEOCODE_URL, params={"name": location, "count": 1, "format": "json"}
            )
            geo.raise_for_status()
            places = geo.json().get("results") or []
            if not places:
                return json.dumps({"error": f"Could not find location: {location}"})
            place = places[0]

            forecast = await client.get(
                FORECAST_URL,
                params={
                    "latitude": place["latitude"],
                    "longitude": place["longitude"],
                    "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                    "weather_code,wind_speed_10m",
                    "daily": "temperature_2m_max,temperature_2m_min,weather_code,"
                    "precipitation_probability_max",
                    "forecast_days": 3,
                    "timezone": "auto",
                },
            )
            forecast.raise_for_status()
            data = forecast.json()
    except httpx.HTTPError as exc:
        return json.dumps({"error": f"Weather service unavailable: {exc}"})

    current = data.get("current", {})
    daily = data.get("daily", {})
    days = []
    for i, date in enumerate(daily.get("time", [])[:3]):
        days.append(
            {
                "date": date,
                "min_c": daily["temperature_2m_min"][i],
                "max_c": daily["temperature_2m_max"][i],
                "conditions": WEATHER_CODES.get(daily["weather_code"][i], "unknown"),
                "precipitation_chance_pct": daily.get(
                    "precipitation_probability_max", [None] * 3
                )[i],
            }
        )
    result = {
        "location": f"{place['name']}, {place.get('country', '')}".strip(", "),
        "current": {
            "temperature_c": current.get("temperature_2m"),
            "feels_like_c": current.get("apparent_temperature"),
            "humidity_pct": current.get("relative_humidity_2m"),
            "wind_kmh": current.get("wind_speed_10m"),
            "conditions": WEATHER_CODES.get(current.get("weather_code"), "unknown"),
        },
        "forecast": days,
    }
    return json.dumps(result, ensure_ascii=False)
