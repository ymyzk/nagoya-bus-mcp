"""Entry point for the Nagoya Bus MCP server."""

import asyncio
import logging
import sys

from nagoya_bus_mcp.mcp.server import mcp_server


async def run_async() -> None:
    """Run the MCP server asynchronously."""
    await mcp_server.run_async()


def main() -> None:
    """Main entry point for the MCP server."""
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    asyncio.run(run_async())


if __name__ == "__main__":
    main()
