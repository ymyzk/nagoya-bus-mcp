"""MCP server for Nagoya Bus information."""

from logging import getLogger

from fastmcp import FastMCP

from nagoya_bus_mcp.mcp.prompts import ask_timetable
from nagoya_bus_mcp.mcp.tools import get_station_number, get_timetable

log = getLogger(__name__)

mcp_server: FastMCP = FastMCP("Nagoya Bus MCP", version="0.1.0")
mcp_server.tool(get_station_number)
mcp_server.tool(get_timetable)
mcp_server.prompt(ask_timetable)
