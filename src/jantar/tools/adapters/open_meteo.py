from __future__ import annotations

import logging
from typing import Any

import httpx

from jantar.tools.base import ToolAdapter

logger = logging.getLogger(__name__)

# Major Indian cities → lat/lon (for resolving city names)
INDIAN_CITIES: dict[str, tuple[float, float]] = {
    "delhi": (28.6139, 77.2090), "new delhi": (28.6139, 77.2090),
    "mumbai": (19.0760, 72.8777), "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946), "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639), "hyderabad": (17.3850, 78.4867),
    "pune": (18.5204, 73.8567), "ahmedabad": (23.0225, 72.5714),
    "jaipur": (26.9124, 75.7873), "lucknow": (26.8467, 80.9462),
    "kanpur": (26.4499, 80.3319), "nagpur": (21.1458, 79.0882),
    "patna": (25.6093, 85.1376), "bhopal": (23.2599, 77.4126),
    "indore": (22.7196, 75.8577), "chandigarh": (30.7333, 76.7794),
    "coimbatore": (11.0168, 76.9558), "kochi": (9.9312, 76.2673),
    "thiruvananthapuram": (8.5241, 76.9366), "guwahati": (26.1445, 91.7362),
    "bhubaneswar": (20.2961, 85.8245), "dehradun": (30.3165, 78.0322),
    "ranchi": (23.3441, 85.3096), "raipur": (21.2514, 81.6296),
    "srinagar": (34.0837, 74.7973), "shimla": (31.1048, 77.1734),
    "varanasi": (25.3176, 82.9739), "agra": (27.1767, 78.0081),
    "surat": (21.1702, 72.8311), "visakhapatnam": (17.6868, 83.2185),
    "noida": (28.5355, 77.3910), "gurgaon": (28.4595, 77.0266),
    "gurugram": (28.4595, 77.0266), "faridabad": (28.4089, 77.3178),
    "amritsar": (31.6340, 74.8723), "allahabad": (25.4358, 81.8463),
    "prayagraj": (25.4358, 81.8463), "mysore": (12.2958, 76.6394),
    "madurai": (9.9252, 78.1198), "jodhpur": (26.2389, 73.0243),
    "udaipur": (24.5854, 73.7125), "goa": (15.2993, 74.1240),
    "panaji": (15.4909, 73.8278), "gangtok": (27.3389, 88.6065),
    "imphal": (24.8170, 93.9368), "shillong": (25.5788, 91.8933),
    "aizawl": (23.7271, 92.7176), "itanagar": (27.0844, 93.6053),
    "kohima": (25.6751, 94.1086), "agartala": (23.8315, 91.2868),
}


def _resolve_city(city: str) -> tuple[float, float] | None:
    return INDIAN_CITIES.get(city.lower().strip())


class OpenMeteoAdapter(ToolAdapter):
    """Adapter for Open-Meteo free weather APIs (no auth required)."""

    def handles(self) -> list[str]:
        return [
            "open_meteo_weather",
            "open_meteo_air_quality",
            "open_meteo_historical_weather",
        ]

    async def execute(self, tool_name: str, params: dict[str, Any]) -> Any:
        city = params.get("city", "Delhi")
        coords = _resolve_city(city)
        if not coords:
            # Try geocoding API
            coords = await self._geocode(city)
        if not coords:
            return {"error": f"Could not resolve city '{city}' to coordinates"}

        lat, lon = coords

        if tool_name == "open_meteo_weather":
            return await self._weather(lat, lon)
        elif tool_name == "open_meteo_air_quality":
            return await self._air_quality(lat, lon)
        elif tool_name == "open_meteo_historical_weather":
            return await self._historical(lat, lon, params)
        return {"error": f"Unknown tool: {tool_name}"}

    async def _geocode(self, city: str) -> tuple[float, float] | None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1, "country": "IN"},
            )
            data = resp.json()
            results = data.get("results", [])
            if results:
                return (results[0]["latitude"], results[0]["longitude"])
        return None

    async def _weather(self, lat: float, lon: float) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat, "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code",
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
                    "timezone": "Asia/Kolkata", "forecast_days": 7,
                },
            )
            return resp.json()

    async def _air_quality(self, lat: float, lon: float) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://air-quality-api.open-meteo.com/v1/air-quality",
                params={
                    "latitude": lat, "longitude": lon,
                    "current": "pm2_5,pm10,nitrogen_dioxide,sulphur_dioxide,ozone,us_aqi",
                },
            )
            return resp.json()

    async def _historical(self, lat: float, lon: float, params: dict) -> dict:
        start = params.get("start_date", "2024-01-01")
        end = params.get("end_date", "2024-12-31")
        variable = params.get("variable", "temperature_2m")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://archive-api.open-meteo.com/v1/archive",
                params={
                    "latitude": lat, "longitude": lon,
                    "start_date": start, "end_date": end,
                    "daily": variable, "timezone": "Asia/Kolkata",
                },
            )
            return resp.json()


open_meteo = OpenMeteoAdapter()
