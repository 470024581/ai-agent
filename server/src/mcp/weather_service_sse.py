"""
Weather MCP Service over SSE (Server-Sent Events)

Run with:
  python -m src.mcp.weather_service_sse

SSE endpoints (defaults from FastMCP):
  - Connect stream:  GET  http://127.0.0.1:8000/sse
  - Post message:    POST http://127.0.0.1:8000/messages/

Note: MultiServerMCPClient currently uses streamable_http for HTTP transport.
This SSE server is provided as a reference/example for SSE-based MCP transport.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import StreamingResponse, Response
import anyio

logger = logging.getLogger(__name__)

mcp = FastMCP("Weather-SSE", port=8002)

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


@mcp.tool(description="Get current weather information for a given location (SSE server).")
async def get_weather(location: str = "Beijing") -> Dict[str, Any]:
    return {"weather": _generate_mock_weather(location), "status": "success"}


@mcp.tool(description="Get a N-day weather forecast (1-7 days) for a location (SSE server).")
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


@mcp.tool(description="List supported city identifiers (SSE server).")
async def list_cities() -> Dict[str, Any]:
    return {"cities": list(_CITY_CONFIG.keys()), "status": "success"}


@mcp.custom_route("/count", methods=["GET"], name="count_stream")
async def count_stream(request: Request) -> Response:
    """SSE demo: stream numbers starting from 0, increment every second."""
    async def gen():
        i = 0
        while True:
            # SSE event format
            yield f"data: {i}\n\n"
            i += 1
            await anyio.sleep(1)

    return StreamingResponse(gen(), media_type="text/event-stream")


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    # SSE transport will mount at /sse and /messages/ by default
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()


