"""Demo script to run the MCP server with OpenAI Agents SDK."""

import asyncio
from pathlib import Path

from agents import Agent
from agents.mcp import MCPServerStdio
from agents.repl import run_demo_loop


async def main() -> None:
    """Run an interactive demo of the Nagoya Bus MCP server with OpenAI Agents SDK.

    Initializes the MCP server via stdio, creates a Nagoya Bus Assistant agent,
    and launches an interactive REPL loop for testing server capabilities.
    """
    async with MCPServerStdio(
        name="Nagoya Bus MCP server",
        params={
            "command": "uv",
            "args": [
                "--directory",
                str(Path(__file__).parent.parent),
                "run",
                "nagoya-bus-mcp",
            ],
        },
    ) as server:
        agent = Agent(
            name="Nagoya Bus Assistant",
            model="gpt-5-mini",
            instructions=(
                "You are a Nagoya City bus assistant. Help with station lookups, "
                "timetables, route guidance, and real-time approach information. "
                "Prefer using MCP tools for authoritative answers. Ask clarifying "
                "questions when a station name or route is ambiguous. The output "
                "should be in Markdown format."
            ),
            mcp_servers=[server],
        )
        await run_demo_loop(agent)


if __name__ == "__main__":
    asyncio.run(main())
