"""
MCP Client (MultiServerMCPClient): Weather (HTTP) + Math (stdio), dynamic tool-calling via system LLM

- Weather: FastMCP streamable_http at http://127.0.0.1:8000/mcp
- Math   : FastMCP stdio spawned from local math_server.py
- LLM    : Retrieved from system factory server.src.models.llm_factory
"""

import asyncio
import json
import logging
import os
import shutil
from typing import Dict, Any, List, Tuple

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from server.src.models.llm_factory import get_llm


_CLIENT: MultiServerMCPClient | None = None
_TOOLS: List[Any] | None = None


def _default_math_path() -> str:
    # Resolve absolute path to math_server.py next to this file
    here = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(here, "math_server.py"))


async def load_tools_combined(
    weather_url: str = "http://127.0.0.1:8001/mcp",
    math_path: str | None = None,
    sse_base: str | None = "http://127.0.0.1:8002/sse",
    git_command: str = "mcp-server-git",
    git_args: List[str] | None = None,
) -> Tuple[MultiServerMCPClient, List[Any]]:
    global _CLIENT, _TOOLS
    if _CLIENT is not None and _TOOLS is not None:
        return _CLIENT, _TOOLS

    math_exe = math_path or _default_math_path()
    # Configure three servers in one MultiServerMCPClient
    servers: Dict[str, Dict[str, Any]] = {
        "math": {
            "command": "python",
            "args": [math_exe],
            "transport": "stdio",
        },
        "weather": {
            "url": weather_url,
            "transport": "streamable_http",
        },
        "weather_sse": {
            "url": sse_base,
            "transport": "sse",
        },
    }
    # Conditionally add git MCP if binary is available
    if git_command and shutil.which(git_command):
        servers["git"] = {
            "command": git_command,
            "args": git_args or [],
            "transport": "stdio",
        }
    client = MultiServerMCPClient(servers)
    tools = await client.get_tools()
    _CLIENT, _TOOLS = client, tools
    return client, tools


def _find_tool(tools: List[Any], candidates: List[str]):
    for tool in tools:
        name = getattr(tool, "name", "")
        if name in candidates:
            return tool
    raise ValueError(f"No matching tool found. Available: {[getattr(t, 'name', '') for t in tools]}")


"""
Note: Removed hard-coded helper functions. Agent will call tools dynamically
via the system LLM based on user intent.
"""


async def main():
    logging.basicConfig(level=logging.INFO)
    print("Connecting MultiServerMCPClient: math(stdio) + weather(http:8001) + weather(sse:8002)...")
    _, tools = await load_tools_combined()

    # Debug: print available tools for visibility
    print("Loaded tools:")
    for t in tools:
        t_name = getattr(t, "name", "<unknown>")
        t_desc = getattr(t, "description", "")
        print(f"- {t_name}: {t_desc}")

    # Build a simple ReAct-style agent using system LLM and loaded tools
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant. Use tools when helpful. If a tool is required, call it."),
        ("human", "{input}")
    ])

    # Many LangChain tool objects conform to BaseTool; ensure they are usable directly
    bound_tools: List[BaseTool] = []
    for t in tools:
        # langchain_mcp_adapters returns tools compatible with LangChain tool interface
        bound_tools.append(t)

    agent = prompt | llm.bind_tools(bound_tools)

    # Demo dynamic invocations based on intent
    queries = [
        "what is the weather in Beijing?",
        "compute (3 + 5) * 12",
        "list available weather cities"
    ]
    for q in queries:
        result = await agent.ainvoke({"input": q})
        print(f"Q: {q}\nA: {getattr(result, 'content', str(result))}\n")

    # Explicit SSE tool demo: directly invoke SSE-backed weather tools
    try:
        sse_get_weather = next(
            t for t in tools
            if getattr(t, "name", "") == "get_weather"
            and "SSE server" in (getattr(t, "description", "") or "")
        )
        sse_res = await sse_get_weather.ainvoke({"location": "Beijing"})
        print("[SSE] get_weather(Beijing):", json.dumps(sse_res, indent=2))
    except StopIteration:
        print("[SSE] get_weather tool not found (ensure SSE server on 8002 is running)")

    try:
        sse_get_forecast = next(
            t for t in tools
            if getattr(t, "name", "") == "get_forecast"
            and "SSE server" in (getattr(t, "description", "") or "")
        )
        sse_res2 = await sse_get_forecast.ainvoke({"location": "Shanghai", "days": 3})
        print("[SSE] get_forecast(Shanghai,3):", json.dumps(sse_res2, indent=2))
    except StopIteration:
        print("[SSE] get_forecast tool not found (ensure SSE server on 8002 is running)")

    # Optional: minimal git MCP example (if mcp-server-git is available and tools loaded)
    git_tools = [
        t for t in tools
        if "git" in (getattr(t, "name", "") or "").lower()
        or "git" in (getattr(t, "description", "") or "").lower()
    ]
    if git_tools:
        print("\n[git] tools detected:")
        for t in git_tools[:3]:
            print(" -", getattr(t, "name", ""), "|", getattr(t, "description", ""))
        try:
            res = await git_tools[0].ainvoke({"repo_path": r"D:\Workspaces\ReactWorkspace\ai-agent"})  # type: ignore[attr-defined]
            print("[git] example call result:", json.dumps(res, indent=2) if not isinstance(res, str) else res)
        except Exception as e:
            print("[git] example call failed:", e)

    # Raw SSE streaming demo: subscribe to continuous counter at /count
    # You should see increasing numbers printed once per second
    import httpx
    print("\n[Raw SSE] connecting to http://127.0.0.1:8002/count ... (Ctrl+C to stop)\n")
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", "http://127.0.0.1:8002/count") as r:
                async for line in r.aiter_lines():
                    if line.startswith("data: "):
                        print(line[6:])
    except (KeyboardInterrupt, asyncio.CancelledError):
        # Graceful shutdown without traceback when user stops the stream
        print("[Raw SSE] stopped by user")


if __name__ == "__main__":
    asyncio.run(main())
