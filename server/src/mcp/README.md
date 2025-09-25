# Weather MCP Service

A WebSocket-based Model Context Protocol (MCP) service for weather information retrieval.

## Overview

This MCP service provides weather data through a WebSocket connection using the JSON-RPC 2.0 protocol. It simulates weather information for various cities and supports real-time data queries.

## Features

- **Current Weather**: Get real-time weather data for any city
- **Weather Forecast**: Get multi-day weather forecasts
- **City List**: Get list of available cities
- **WebSocket Protocol**: Real-time communication using WebSocket
- **JSON-RPC 2.0**: Standardized request/response format
- **Mock Data**: Simulated weather data for testing

## Architecture

```
┌─────────────────┐    WebSocket     ┌─────────────────┐
│   MCP Client    │◄────────────────►│  Weather MCP    │
│                 │   JSON-RPC 2.0   │    Service      │
└─────────────────┘                  └─────────────────┘
```

## Installation

The service requires the following Python packages:

```bash
pip install websockets
```

## Usage

### Starting the Service

```python
from server.src.mcp.weather_service import run_weather_service

# Run the service
asyncio.run(run_weather_service(host="localhost", port=8765))
```

Or run directly:

```bash
python -m server.src.mcp.weather_service
```

### Using the Client

```python
from server.src.mcp.client import WeatherMCPClient

async def example():
    client = WeatherMCPClient("localhost", 8765)
    
    # Connect to service
    await client.connect()
    
    # Get current weather
    weather = await client.get_current_weather("Beijing")
    print(weather)
    
    # Get forecast
    forecast = await client.get_weather_forecast("Shanghai", days=5)
    print(forecast)
    
    # Disconnect
    await client.disconnect()
```

### Quick Functions

```python
from server.src.mcp.client import get_weather, get_forecast

# Quick weather query
weather = await get_weather("Beijing")
forecast = await get_forecast("Shanghai", days=3)
```

## API Reference

### Methods

#### `weather/get_current`
Get current weather for a city.

**Parameters:**
- `city` (string): City name (default: "Beijing")

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "weather": {
      "city": "Beijing",
      "temperature": 25.5,
      "humidity": 65,
      "condition": "sunny",
      "wind_speed": 12.3,
      "pressure": 1013.2,
      "timestamp": "2024-01-15T10:30:00",
      "description": "Clear skies with bright sunshine"
    },
    "status": "success"
  }
}
```

#### `weather/get_forecast`
Get weather forecast for a city.

**Parameters:**
- `city` (string): City name (default: "Beijing")
- `days` (integer): Number of forecast days (default: 3)

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "forecast": [
      {
        "city": "Beijing",
        "temperature": 25.5,
        "humidity": 65,
        "condition": "sunny",
        "wind_speed": 12.3,
        "pressure": 1013.2,
        "timestamp": "2024-01-15T10:30:00",
        "description": "Clear skies with bright sunshine"
      }
    ],
    "status": "success"
  }
}
```

#### `weather/get_cities`
Get list of available cities.

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "cities": ["beijing", "shanghai", "guangzhou", "shenzhen"],
    "status": "success"
  }
}
```

### Error Handling

The service returns standard JSON-RPC 2.0 error responses:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32601,
    "message": "Method not found"
  }
}
```

**Error Codes:**
- `-32700`: Parse error
- `-32600`: Invalid Request
- `-32601`: Method not found
- `-32602`: Invalid params
- `-32603`: Internal error

## Configuration

### Service Configuration

```python
service = WeatherMCPService(
    host="localhost",    # Server host
    port=8765           # Server port
)
```

### Client Configuration

```python
client = WeatherMCPClient(
    host="localhost",    # Server host
    port=8765           # Server port
)
```

## Mock Data

The service generates realistic mock weather data for the following cities:

- **Beijing**: Cold winters, hot summers, various conditions
- **Shanghai**: Humid subtropical climate
- **Guangzhou**: Tropical climate with high humidity
- **Shenzhen**: Similar to Guangzhou, coastal city

For unknown cities, default weather patterns are used.

## Integration with Main Application

To integrate the Weather MCP Service with the main application:

1. **Add to main.py**:
```python
from server.src.mcp.weather_service import WeatherMCPService

# Start weather service in background
weather_service = WeatherMCPService()
asyncio.create_task(weather_service.start_server())
```

2. **Use in agents**:
```python
from server.src.mcp.client import get_weather

# In your agent code
weather_data = await get_weather("Beijing")
```

## Testing

Run the service:
```bash
python -m server.src.mcp.weather_service
```

Test with client:
```bash
python -m server.src.mcp.client
```

## WebSocket Connection

The service uses WebSocket for real-time communication:

- **URL**: `ws://localhost:8765`
- **Protocol**: JSON-RPC 2.0 over WebSocket
- **Ping Interval**: 20 seconds
- **Ping Timeout**: 10 seconds

## Logging

The service uses Python's standard logging module. Configure logging level:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

## Future Enhancements

- Real weather API integration
- Historical weather data
- Weather alerts and notifications
- Multiple language support
- Caching and persistence
- Authentication and authorization
