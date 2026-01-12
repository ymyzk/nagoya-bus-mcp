"""MCP server for Nagoya Bus information."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from logging import getLogger

from fastmcp import FastMCP

from nagoya_bus_mcp.client import Client
from nagoya_bus_mcp.data import BaseData, init_base_data
from nagoya_bus_mcp.mcp.prompts import ask_bus_approach, ask_timetable
from nagoya_bus_mcp.mcp.tools import (
    get_approach_for_route,
    get_approach_for_station,
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
class Settings:
    """Settings for the MCP server."""

    cache_database_path: str | None = None


@dataclass
class LifespanContext:
    """Lifespan context holding shared resources for the MCP server.

    This context is created at server startup and provides access to the
    shared HTTP client for Nagoya Bus API requests and preloaded base data.
    """

    bus_client: Client
    base_data: BaseData


def build_mcp_server(settings: Settings) -> FastMCP:
    """Build and return the MCP server instance.

    Args:
        settings: Settings for the MCP server.
    """

    @asynccontextmanager
    async def lifespan(_mcp: FastMCP) -> AsyncIterator[LifespanContext]:
        """Manage the lifespan of the MCP server.

        Creates and maintains a single HTTP client for the Nagoya Bus API
        that is shared across all tool invocations during the server's lifetime.
        Also initializes base data (stations and poles) at startup.

        Args:
            _mcp: The FastMCP server instance (unused).

        Yields:
            LifespanContext containing the shared bus client and base data.
        """
        log.info("Starting lifespan and initializing context")
        async with Client(
            cache_database_path=settings.cache_database_path
        ) as bus_client:
            log.info("Initializing base data")
            base_data = await init_base_data(bus_client)
            context = LifespanContext(bus_client=bus_client, base_data=base_data)
            log.info("Lifespan context initialized")
            yield context
        log.info("Lifespan context closed")

    mcp_server: FastMCP = FastMCP("Nagoya Bus MCP", version=version, lifespan=lifespan)
    mcp_server.tool(get_station_number)
    mcp_server.tool(get_timetable)
    mcp_server.tool(get_approach_for_route)
    mcp_server.tool(get_approach_for_station)
    mcp_server.prompt(ask_timetable)
    mcp_server.prompt(ask_bus_approach)

    return mcp_server
