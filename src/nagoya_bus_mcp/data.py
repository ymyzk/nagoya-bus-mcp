"""Common base data for Nagoya Bus MCP tools.

This module initializes and provides fast access to shared base data such as
a list of bus stations and pole information, which are used by various MCP tools
to answer user queries about Nagoya Bus services.
"""

from __future__ import annotations

import difflib

from nagoya_bus_mcp.client import (  # noqa: TC001
    BusStopPoleInfoResponse,
    Client,
    StationNamesResponse,
)


async def init_base_data(client: Client) -> BaseData:
    """Initialize and return the base data for Nagoya Bus MCP tools."""
    poles = await client.get_bus_stop_pole_info()
    stations = await client.get_station_names()
    return BaseData(poles, stations)


class BaseData:
    """Base data for Nagoya Bus MCP tools."""

    def __init__(
        self, poles: BusStopPoleInfoResponse, stations: StationNamesResponse
    ) -> None:
        """Initialize the base data with pole and station information."""
        self._pole_name_by_code = {code: pole.n for code, pole in poles.root.items()}
        self._station_number_by_name = stations.root
        self._station_name_by_number = {
            num: name for name, num in stations.root.items()
        }

    def get_pole_name(self, code: str) -> str | None:
        """Get the name of a bus stop pole by its code."""
        return self._pole_name_by_code.get(code)

    def get_station_number(self, name: str) -> int | None:
        """Get the station number for a given station name."""
        return self._station_number_by_name.get(name)

    def get_station_name(self, number: int) -> str | None:
        """Get the station name for a given station number."""
        return self._station_name_by_number.get(number)

    def find_station_number(self, name: str, *, cutoff: float = 0.6) -> int | None:
        """Find a station number using fuzzy matching.

        Uses fuzzy matching with the specified cutoff threshold to find the
        closest matching station name.

        Args:
            name: The station name to search for.
            cutoff: Similarity threshold for fuzzy matching (0.0 to 1.0).
                   Defaults to 0.6 (60% similarity).

        Returns:
            The station number if a match is found, None otherwise.
        """
        closest_matches = difflib.get_close_matches(
            name, self._station_number_by_name.keys(), n=1, cutoff=cutoff
        )

        if closest_matches:
            return self._station_number_by_name[closest_matches[0]]

        return None
