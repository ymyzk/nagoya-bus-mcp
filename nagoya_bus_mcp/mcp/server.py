"""MCP server for Nagoya Bus information."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from logging import getLogger

from fastmcp import FastMCP

from nagoya_bus_mcp.client import Client
from nagoya_bus_mcp.mcp.prompts import ask_timetable
from nagoya_bus_mcp.mcp.tools import get_station_number, get_timetable

log = getLogger(__name__)


@dataclass
class LifespanContext:
    bus_client: Client


@asynccontextmanager
async def lifespan(_mcp: FastMCP) -> AsyncIterator[LifespanContext]:
    log.info("Starting lifespan and initializing context")
    context = LifespanContext(bus_client=Client())
    yield context
    log.info("Cleaning up lifespan and context")
    await context.bus_client.close()
    log.info("Clean up complete")


mcp_server: FastMCP = FastMCP("Nagoya Bus MCP", version="0.1.0", lifespan=lifespan)
mcp_server.tool(get_station_number)
mcp_server.tool(get_timetable)
mcp_server.prompt(ask_timetable)
