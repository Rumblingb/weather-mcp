#!/usr/bin/env python3
"""Weather MCP Server — Get current weather and forecasts for AI agents."""

import os, json
from mcp.server import Server, stdio_server
import httpx

server = Server("weather-mcp")

WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")
BASE_URL = "https://api.openweathermap.org/data/2.5"

def _temp_str(kelvin):
    """Convert Kelvin to Celsius and Fahrenheit."""
    c = kelvin - 273.15
    f = c * 9/5 + 32
    return {"celsius": round(c, 1), "fahrenheit": round(f, 1)}

async def _get(endpoint, params):
    """Make async GET request to OpenWeatherMap."""
    if not WEATHER_API_KEY:
        raise RuntimeError("WEATHER_API_KEY not set. Get a free key at openweathermap.org")
    params["appid"] = WEATHER_API_KEY
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{BASE_URL}/{endpoint}", params=params)
        resp.raise_for_status()
        return resp.json()

@server.tool(
    name="get_weather",
    description="Get current weather for a city",
    input_schema={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name (e.g. London, Tokyo, New York)"},
            "country_code": {"type": "string", "description": "Optional country code (e.g. US, GB, JP)"},
            "units": {"type": "string", "enum": ["metric", "imperial"], "description": "Temperature units", "default": "metric"}
        },
        "required": ["city"]
    }
)
async def get_weather(city: str, country_code: str = None, units: str = "metric") -> str:
    try:
        q = f"{city},{country_code}" if country_code else city
        data = await _get("weather", {"q": q})
        temp = data["main"]
        weather = data["weather"][0]
        return json.dumps({
            "city": data["name"],
            "country": data.get("sys", {}).get("country", ""),
            "temperature": _temp_str(temp["temp"]),
            "feels_like": _temp_str(temp["feels_like"]),
            "humidity": temp["humidity"],
            "pressure": temp["pressure"],
            "conditions": weather["description"],
            "icon": weather["icon"],
            "wind_speed": data["wind"]["speed"],
            "wind_direction": data["wind"].get("deg", 0),
            "visibility": data.get("visibility", 0),
            "cloudiness": data["clouds"]["all"],
            "sunrise": data["sys"]["sunrise"],
            "sunset": data["sys"]["sunset"],
        }, indent=2)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return json.dumps({"error": f"City '{city}' not found"})
        return json.dumps({"error": f"API error: {e.response.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})

@server.tool(
    name="get_forecast",
    description="Get 5-day weather forecast for a city (3-hour intervals)",
    input_schema={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name"},
            "country_code": {"type": "string", "description": "Optional country code"},
            "days": {"type": "integer", "description": "Number of days (1-5)", "default": 3}
        },
        "required": ["city"]
    }
)
async def get_forecast(city: str, country_code: str = None, days: int = 3) -> str:
    try:
        q = f"{city},{country_code}" if country_code else city
        data = await _get("forecast", {"q": q})
        results = []
        for item in data["list"][:days * 8]:  # 8 intervals per day
            results.append({
                "time": item["dt_txt"],
                "temperature": _temp_str(item["main"]["temp"]),
                "conditions": item["weather"][0]["description"],
                "humidity": item["main"]["humidity"],
                "wind_speed": item["wind"]["speed"],
                "pop": item.get("pop", 0)
            })
        return json.dumps({"city": data["city"]["name"], "country": data["city"].get("country", ""), "forecast": results}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@server.tool(
    name="get_weather_by_coords",
    description="Get current weather by GPS coordinates",
    input_schema={
        "type": "object",
        "properties": {
            "lat": {"type": "number", "description": "Latitude"},
            "lon": {"type": "number", "description": "Longitude"}
        },
        "required": ["lat", "lon"]
    }
)
async def get_weather_by_coords(lat: float, lon: float) -> str:
    try:
        data = await _get("weather", {"lat": lat, "lon": lon})
        temp = data["main"]
        weather = data["weather"][0]
        return json.dumps({
            "city": data.get("name", ""),
            "country": data.get("sys", {}).get("country", ""),
            "temperature": _temp_str(temp["temp"]),
            "feels_like": _temp_str(temp["feels_like"]),
            "humidity": temp["humidity"],
            "conditions": weather["description"],
            "wind_speed": data["wind"]["speed"],
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

def main():
    import anyio
    async def run():
        async with stdio_server() as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())
    anyio.run(run)

if __name__ == "__main__":
    main()
