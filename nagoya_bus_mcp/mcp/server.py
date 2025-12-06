"""MCP server for Nagoya Bus information."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from logging import getLogger

from fastmcp import FastMCP

from nagoya_bus_mcp.client import Client
from nagoya_bus_mcp.mcp.prompts import ask_bus_approach, ask_timetable
from nagoya_bus_mcp.mcp.tools import (
    get_approach,
    get_busstop_info,
    get_route_master,
    get_station_number,
    get_timetable,
)

log = getLogger(__name__)

try:
    from nagoya_bus_mcp.version import version
except ImportError:
    log.warning("nagoya_bus_mcp.version module not found, using default version")
    version = "0.0.0"


@dataclass
class LifespanContext:
    """Lifespan context holding shared resources for the MCP server.

    This context is created at server startup and provides access to the
    shared HTTP client for Nagoya Bus API requests.
    """

    bus_client: Client


@asynccontextmanager
async def lifespan(_mcp: FastMCP) -> AsyncIterator[LifespanContext]:
    """Manage the lifespan of the MCP server.

    Creates and maintains a single HTTP client for the Nagoya Bus API
    that is shared across all tool invocations during the server's lifetime.

    Args:
        _mcp: The FastMCP server instance (unused).

    Yields:
        LifespanContext containing the shared bus client.
    """
    log.info("Starting lifespan and initializing context")
    async with Client() as bus_client:
        context = LifespanContext(bus_client=bus_client)
        log.info("Lifespan context initialized")
        yield context
    log.info("Lifespan context closed")


mcp_server: FastMCP = FastMCP("Nagoya Bus MCP", version=version, lifespan=lifespan)
mcp_server.tool(get_station_number)
mcp_server.tool(get_timetable)
mcp_server.tool(get_busstop_info)
mcp_server.tool(get_route_master)
mcp_server.tool(get_approach)
mcp_server.prompt(ask_timetable)
mcp_server.prompt(ask_bus_approach)
