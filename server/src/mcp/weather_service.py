"""
Weather MCP Service (FastMCP streamable-http)

Run with:
  python -m src.mcp.weather_service

It serves on http://127.0.0.1:8000/mcp by default (FastMCP default).
Compatible with MultiServerMCPClient(transport="streamable_http").
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("Weather")

_CITY_CONFIG: Dict[str, Dict[str, Any]] = {
    "beijing": {
        "temperature_range": (-5, 35),
        "humidity_range": (30, 80),
        "conditions": ["sunny", "cloudy", "rainy", "snowy"],
        "wind_speed_range": (5, 25),
        "pressure_range": (1000, 1030),
    },
    "shanghai": {
        "temperature_range": (0, 38),
        "humidity_range": (40, 90),
        "conditions": ["sunny", "cloudy", "rainy", "foggy"],
        "wind_speed_range": (3, 20),
        "pressure_range": (1005, 1025),
    },
    "guangzhou": {
        "temperature_range": (10, 40),
        "humidity_range": (50, 95),
        "conditions": ["sunny", "cloudy", "rainy", "thunderstorm"],
        "wind_speed_range": (5, 30),
        "pressure_range": (1000, 1020),
    },
    "shenzhen": {
        "temperature_range": (12, 38),
        "humidity_range": (45, 90),
        "conditions": ["sunny", "cloudy", "rainy", "thunderstorm"],
        "wind_speed_range": (5, 25),
        "pressure_range": (1000, 1020),
    },
}

def _generate_mock_weather(city: str) -> Dict[str, Any]:
    city_lower = city.lower()
    cfg = _CITY_CONFIG.get(city_lower, {
        "temperature_range": (0, 30),
        "humidity_range": (40, 80),
        "conditions": ["sunny", "cloudy", "rainy"],
        "wind_speed_range": (5, 20),
        "pressure_range": (1000, 1025),
    })

    temp = round(random.uniform(*cfg["temperature_range"]), 1)
    hum = random.randint(*cfg["humidity_range"])
    cond = random.choice(cfg["conditions"])
    wind = round(random.uniform(*cfg["wind_speed_range"]), 1)
    press = round(random.uniform(*cfg["pressure_range"]), 1)

    descriptions = {
        "sunny": "Clear skies with bright sunshine",
        "cloudy": "Overcast with scattered clouds",
        "rainy": "Light to moderate rainfall expected",
        "snowy": "Snowfall with cold temperatures",
        "foggy": "Dense fog reducing visibility",
        "thunderstorm": "Thunderstorms with heavy rain",
    }

    return {
        "city": city,
        "temperature": temp,
        "humidity": hum,
        "condition": cond,
        "wind_speed": wind,
        "pressure": press,
        "timestamp": datetime.now().isoformat(),
        "description": descriptions.get(cond, "Variable weather conditions"),
    }


@mcp.tool()
async def get_weather(location: str = "Beijing") -> Dict[str, Any]:
    return {"weather": _generate_mock_weather(location), "status": "success"}


@mcp.tool()
async def get_forecast(location: str = "Beijing", days: int = 3) -> Dict[str, Any]:
    days = max(1, min(7, int(days)))
    forecast: List[Dict[str, Any]] = []
    for i in range(days):
        item = _generate_mock_weather(location)
        item["temperature"] = round(item["temperature"] + random.uniform(-3, 3), 1)
        item["humidity"] = max(0, min(100, int(item["humidity"]) + random.randint(-10, 10)))
        item["timestamp"] = (datetime.now() + timedelta(days=i)).isoformat()
        forecast.append(item)
    return {"forecast": forecast, "status": "success"}


@mcp.tool()
async def list_cities() -> Dict[str, Any]:
    return {"cities": list(_CITY_CONFIG.keys()), "status": "success"}


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    # FastMCP.run manages its own event loop; do not call inside asyncio.run
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
