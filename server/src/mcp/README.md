# MCP Services (Math + Weather) with Multi Transports

This folder contains three MCP services and a unified client:

- Math MCP (stdio): `server/src/mcp/math_server.py`
- Weather MCP (streamable-http, port 8001): `server/src/mcp/weather_service.py`
- Weather MCP (SSE, port 8002): `server/src/mcp/weather_service_sse.py`
- Unified Client (dynamic tool calling via system LLM): `server/src/mcp/client.py`

## Key Features

- Multi transport MCP services: stdio, streamable-http, SSE
- Dynamic tool selection via system LLM (OpenRouter/OpenAI/Ollama/Dify)
- Weather tools with clear descriptions for better LLM routing
- SSE continuous streaming demo (`/count`) pushing 0,1,2... every second

## Install

```bash
pip install mcp langchain langchain-mcp-adapters httpx
```

## Start Services

- Weather (HTTP, 8001):
```bash
python -m src.mcp.weather_service
```

- Weather (SSE, 8002):
```bash
python -m src.mcp.weather_service_sse
```

Math (stdio) will be spawned automatically by the client.

## Client (Dynamic Tool Use)

```bash
python -m server.src.mcp.client
```

What it does:
- Loads tools from math(stdio), weather(http:8001), weather(sse:8002)
- Prints all loaded tools (names + descriptions)
- Builds a ReAct-style agent with system LLM and bound tools
- Runs sample queries
- Explicitly calls SSE tools (get_weather/get_forecast) and prints results
- Raw SSE demo: subscribes to `/count` and prints streaming numbers

## Weather Tools

The weather services expose the same tool names; SSE descriptions include "(SSE server)" to distinguish.

- `get_weather(location: str)`
  - Description: Get current weather information for a given location (city name).
- `get_forecast(location: str, days: int)`
  - Description: Get a N-day weather forecast (1-7 days) for a location.
- `list_cities()`
  - Description: List supported city identifiers this server can simulate.

## SSE Continuous Streaming Demo

SSE service also exposes a custom route:

- `GET http://127.0.0.1:8002/count`
  - Streams `data: 0`, `data: 1`, ... once per second

The client subscribes to it and prints numbers until you Ctrl+C.

## MultiServerMCPClient Configuration (internal)

`load_tools_combined()` constructs a single client mapping:

```python
{
  "math": {"command": "python", "args": [math_server.py], "transport": "stdio"},
  "weather": {"url": "http://127.0.0.1:8001/mcp", "transport": "streamable_http"},
  "weather_sse": {"url": "http://127.0.0.1:8002/sse", "transport": "sse"}
}
```

## Notes

- Ensure your `.env` provides valid LLM credentials if using OpenRouter/OpenAI.
- HTTP and SSE run on different ports (8001, 8002) to avoid conflicts with FastAPI.

