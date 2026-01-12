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
        assert result.structured_content == {
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
        assert result.structured_content == {
            "station_name": "名古屋駅",
            "station_number": NAGOYA_STATION_NUMBER,
        }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_station_names_runs_not_found() -> None:
    async with Client(mcp_server) as client:
        with pytest.raises(ToolError, match="Station not found: 存在しないバス停"):
            await client.call_tool(
                "get_station_number", {"station_name": "存在しないバス停"}
            )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_timetable_succeeds_and_has_expected_structure() -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "get_timetable", {"station_number": NAGOYA_STATION_NUMBER}
        )
        data = result.structured_content

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
            "stop_station_names",
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
        assert isinstance(tt["stop_station_names"], list)
        assert len(tt["stop_station_names"]) > 0
        assert all(isinstance(s, str) and s for s in tt["stop_station_names"])
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
        data = result.structured_content

        assert data is not None
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
        with pytest.raises(ToolError, match="Station number not found: 123456789"):
            await client.call_tool("get_timetable", {"station_number": 123456789})


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_approach_for_route_succeeds_and_has_expected_structure() -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "get_approach_for_route", {"route_code": ROUTE_CODE}
        )
        data = result.structured_content

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
            assert "pole" in bus_stop
            assert isinstance(bus_stop["station_number"], int)
            assert isinstance(bus_stop["station_name"], str)
            assert isinstance(bus_stop["pole"], str)

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
                assert "pole" in stop
                assert isinstance(stop["station_number"], int)
                assert isinstance(stop["station_name"], str)
                assert isinstance(stop["pole"], str)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_approach_for_route_not_found() -> None:
    async with Client(mcp_server) as client:
        with pytest.raises(ToolError, match="404 Not Found"):
            await client.call_tool("get_approach_for_route", {"route_code": "9999999"})


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_approach_for_station_succeeds_and_has_expected_structure() -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "get_approach_for_station", {"station_number": NAGOYA_STATION_NUMBER}
        )
        data = result.structured_content

        # Basic structure checks
        assert isinstance(data, dict)
        assert "routes" in data
        assert "url" in data
        assert isinstance(data["routes"], list)
        assert isinstance(data["url"], str)
        assert "名古屋駅" in data["url"]

        # If there are any routes, validate their structure
        if len(data["routes"]) > 0:
            approach = data["routes"][0]
            assert "route_code" in approach
            assert "route" in approach
            assert "direction" in approach
            assert "pole" in approach
            assert "last_pass_time" in approach
            assert "approaching_buses" in approach

            assert isinstance(approach["route_code"], str)
            assert isinstance(approach["route"], str)
            assert isinstance(approach["direction"], str)
            assert isinstance(approach["pole"], str)
            assert approach["last_pass_time"] is None or isinstance(
                approach["last_pass_time"], str
            )
            assert isinstance(approach["approaching_buses"], list)

            # Validate last_pass_time format if present
            if approach["last_pass_time"] is not None:
                assert re.match(r"^\d{2}:\d{2}:\d{2}$", approach["last_pass_time"])

            # Validate approaching buses structure if present
            for bus in approach["approaching_buses"]:
                assert "location" in bus
                assert "previous_station_name" in bus
                assert "pass_time" in bus
                assert isinstance(bus["location"], str)
                assert isinstance(bus["previous_station_name"], str)
                assert isinstance(bus["pass_time"], str)
                assert re.match(r"^\d{2}:\d{2}:\d{2}$", bus["pass_time"])


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_approach_for_station_filters_routes_without_activity() -> None:
    """Test that routes with no last pass time and no approaching buses are removed."""
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "get_approach_for_station", {"station_number": NAGOYA_STATION_NUMBER}
        )
        data = result.structured_content

        # All returned routes should have either a last pass time
        # or approaching buses
        assert data is not None
        for approach in data["routes"]:
            has_last_pass = approach["last_pass_time"] is not None
            has_approaching_buses = len(approach["approaching_buses"]) > 0
            assert has_last_pass or has_approaching_buses, (
                "Each approach should have either last_pass_time or approaching_buses"
            )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_approach_for_station_not_found() -> None:
    async with Client(mcp_server) as client:
        with pytest.raises(ToolError, match="404 Not Found"):
            await client.call_tool(
                "get_approach_for_station", {"station_number": 99999}
            )
