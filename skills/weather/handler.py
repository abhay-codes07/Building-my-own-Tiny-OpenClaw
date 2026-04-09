"""
weather skill — current conditions and 3-day forecast via Open-Meteo.

Two-step process:
  1. Geocode the city name → lat/lon using Open-Meteo's free geocoding API
  2. Fetch weather data for those coordinates

No API key required for either endpoint.
"""

import httpx

GEO_URL     = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT     = 10

# WMO weather interpretation codes → human-readable description
WMO_CODES: dict[int, str] = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}

tools = [
    {
        "name": "get_weather",
        "description": (
            "Return current temperature, weather condition, wind speed, and a "
            "3-day max/min temperature forecast for a given city."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name (e.g. 'London', 'New York', 'Tokyo')",
                },
            },
            "required": ["city"],
        },
    },
]


async def _geocode(city: str, client: httpx.AsyncClient) -> dict:
    resp = await client.get(GEO_URL, params={"name": city, "count": 1, "language": "en", "format": "json"})
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results")
    if not results:
        raise ValueError(f"Could not find location: {city!r}")
    return results[0]  # {latitude, longitude, name, country, ...}


async def execute(tool_name: str, tool_input: dict, context: dict):
    if tool_name != "get_weather":
        return {"error": f"Unknown tool: {tool_name}"}

    city = tool_input.get("city", "").strip()
    if not city:
        return {"error": "city must not be empty"}

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Step 1 — geocode
            location = await _geocode(city, client)
            lat  = location["latitude"]
            lon  = location["longitude"]
            name = f"{location['name']}, {location.get('country', '')}"

            # Step 2 — fetch weather
            params = {
                "latitude":   lat,
                "longitude":  lon,
                "current":    "temperature_2m,weathercode,windspeed_10m,relative_humidity_2m",
                "daily":      "temperature_2m_max,temperature_2m_min,weathercode",
                "forecast_days": 3,
                "timezone":   "auto",
                "wind_speed_unit": "kmh",
            }
            resp = await client.get(WEATHER_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        current = data["current"]
        daily   = data["daily"]

        condition = WMO_CODES.get(current.get("weathercode", 0), "Unknown")
        forecast  = []
        for i in range(len(daily["time"])):
            forecast.append({
                "date":        daily["time"][i],
                "condition":   WMO_CODES.get(daily["weathercode"][i], "Unknown"),
                "temp_max_c":  daily["temperature_2m_max"][i],
                "temp_min_c":  daily["temperature_2m_min"][i],
            })

        return {
            "location":      name,
            "temperature_c": current["temperature_2m"],
            "condition":     condition,
            "humidity_pct":  current.get("relative_humidity_2m"),
            "wind_kmh":      current.get("windspeed_10m"),
            "forecast":      forecast,
        }

    except ValueError as exc:
        return {"error": str(exc)}
    except httpx.HTTPStatusError as exc:
        return {"error": f"Weather API error: {exc.response.status_code}"}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
