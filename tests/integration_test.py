"""Integration tests for Nagoya Bus MCP server tools.

These tests make real API calls to the Nagoya City bus API and are marked
with @pytest.mark.integration. They verify the end-to-end functionality
of MCP tools against live data.
"""

import re

from fastmcp import Client
from fastmcp.exceptions import ToolError
import pytest

from nagoya_bus_mcp.mcp.server import Settings, build_mcp_server

NAGOYA_STATION_NUMBER = 41200
ROUTE_CODE = "1123002"


mcp_server = build_mcp_server(Settings())


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_station_names_succeeds() -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "get_station_number", {"station_name": "名古屋駅"}
        )
        assert result.data == {
            "success": True,
            "station_name": "名古屋駅",
            "station_number": NAGOYA_STATION_NUMBER,
        }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_station_names_runs_fuzzy_matching() -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "get_station_number", {"station_name": "名古駅"}
        )
        assert result.data == {
            "success": True,
            "station_name": "名古屋駅",
            "station_number": NAGOYA_STATION_NUMBER,
        }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_station_names_runs_not_found() -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "get_station_number", {"station_name": "存在しないバス停"}
        )
        assert result.data == {
            "success": False,
            "station_name": None,
            "station_number": None,
        }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_timetable_succeeds_and_has_expected_structure() -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "get_timetable", {"station_number": NAGOYA_STATION_NUMBER}
        )
        data = result.data

        # Basic structure checks
        assert isinstance(data, dict)
        assert data["station_number"] == NAGOYA_STATION_NUMBER
        assert isinstance(data["timetables"], list)
        assert len(data["timetables"]) > 0
        assert (
            data["url"]
            == "https://www.kotsu.city.nagoya.jp/jp/pc/bus/timetable_list.html?name=名古屋駅&toname="
        )

        # Validate one timetable entry
        tt = data["timetables"][0]
        assert {
            "route",
            "route_codes",
            "direction",
            "pole",
            "stop_stations",
            "timetable",
            "url",
        }.issubset(tt.keys())
        assert isinstance(tt["route"], str)
        assert len(tt["route"]) > 0
        assert isinstance(tt["route_codes"], list)
        assert len(tt["route_codes"]) > 0
        assert all(isinstance(rc, int) and rc for rc in tt["route_codes"])
        assert isinstance(tt["direction"], str)
        assert isinstance(tt["pole"], str)
        assert isinstance(tt["stop_stations"], list)
        assert len(tt["stop_stations"]) > 0
        assert all(isinstance(s, str) and s for s in tt["stop_stations"])
        assert isinstance(tt["timetable"], dict)
        assert isinstance(tt["url"], str)
        assert "timetable_dtl.html" in tt["url"]

        # Validate time string format (HH:MM) across days
        for day, times in tt["timetable"].items():
            assert isinstance(day, str)
            assert isinstance(times, list)
            for t in times:
                assert isinstance(t, str)
                assert re.match(r"^\d{1,2}:\d{2}$", t)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_timetable_all_entries_have_valid_time_format() -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "get_timetable", {"station_number": NAGOYA_STATION_NUMBER}
        )
        data = result.data

        for tt in data["timetables"]:
            assert isinstance(tt["timetable"], dict)
            for day, times in tt["timetable"].items():
                assert isinstance(day, str)
                assert isinstance(times, list)
                for t in times:
                    assert isinstance(t, str)
                    assert re.match(r"^\d{1,2}:\d{2}$", t)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_timetable_not_found() -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_timetable", {"station_number": 123456789})
        assert result.data is None, "Expected None for non-existent station number"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_approach_succeeds_and_has_expected_structure() -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_approach", {"route_code": ROUTE_CODE})
        data = result.data

        # Basic structure checks
        assert isinstance(data, dict)
        assert "bus_stops" in data
        assert "bus_positions" in data
        assert isinstance(data["bus_stops"], list)
        assert isinstance(data["bus_positions"], list)

        # Validate bus_stops structure
        for bus_stop in data["bus_stops"]:
            assert "station_number" in bus_stop
            assert "station_name" in bus_stop
            assert "pole_name" in bus_stop
            assert isinstance(bus_stop["station_number"], int)
            assert isinstance(bus_stop["station_name"], str)
            assert isinstance(bus_stop["pole_name"], str)

        # Validate bus_positions structure
        for bus_position in data["bus_positions"]:
            assert "car_code" in bus_position
            assert "previous_stop" in bus_position
            assert "passed_time" in bus_position
            assert "next_stop" in bus_position
            assert isinstance(bus_position["car_code"], str)
            assert isinstance(bus_position["passed_time"], str)
            assert re.match(r"^\d{2}:\d{2}:\d{2}$", bus_position["passed_time"])
            # Validate nested RouteBusStopInfo objects
            assert isinstance(bus_position["previous_stop"], dict)
            assert isinstance(bus_position["next_stop"], dict)
            for stop in [bus_position["previous_stop"], bus_position["next_stop"]]:
                assert "station_number" in stop
                assert "station_name" in stop
                assert "pole_name" in stop
                assert isinstance(stop["station_number"], int)
                assert isinstance(stop["station_name"], str)
                assert isinstance(stop["pole_name"], str)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_approach_not_found() -> None:
    async with Client(mcp_server) as client:
        with pytest.raises(ToolError, match="404 Not Found"):
            await client.call_tool("get_approach", {"route_code": "9999999"})
