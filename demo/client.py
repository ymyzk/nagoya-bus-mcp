"""Demo client for testing the Nagoya Bus MCP server."""

import asyncio

from fastmcp import Client

from nagoya_bus_mcp.mcp.server import Settings, build_mcp_server


async def main() -> None:
    """Run demo client to test MCP server tools."""
    mcp_server = build_mcp_server(Settings())
    async with Client(mcp_server) as client:
        print(await client.list_tools())
        print(
            (await client.call_tool("get_station_number", {"station_name": "新栄町"}))
            .content[0]
            .text
        )


if __name__ == "__main__":
    asyncio.run(main())
