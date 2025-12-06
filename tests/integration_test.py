import re

from fastmcp import Client
import pytest

from nagoya_bus_mcp.mcp.server import mcp_server

NAGOYA_STATION_NUMBER = 41200
ROUTE_CODE = "1123002"


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
            "direction",
            "pole",
            "stop_stations",
            "timetable",
            "url",
        }.issubset(tt.keys())
        assert isinstance(tt["route"], str)
        assert len(tt["route"]) > 0
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
async def test_get_route_master_succeeds_and_has_expected_structure() -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_route_master", {"route_code": ROUTE_CODE})
        data = result.data

        # Basic structure checks
        assert isinstance(data, dict)
        assert data["to"] == "栄"
        assert data["from_"] == "中川車庫前"
        assert data["direction"] == "2"
        assert data["no"] == "1400"
        assert data["article"] == ""
        assert data["keito"] == "1123"
        assert isinstance(data["busstops"], list)
        assert len(data["busstops"]) > 0
        assert all(isinstance(s, str) and s for s in data["busstops"])


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_route_master_not_found() -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_route_master", {"route_code": "9999999"})
        assert result.data is None, "Expected None for non-existent route code"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_approach_succeeds_and_has_expected_structure() -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_approach", {"route_code": ROUTE_CODE})
        data = result.data

        # Basic structure checks
        assert isinstance(data, dict)

        latest_pass = data["latest_bus_pass"][0]
        assert {
            "stop_id",
            "passed_time",
            "car_code",
        }.issubset(latest_pass.keys())
        assert isinstance(latest_pass["stop_id"], str)
        assert isinstance(latest_pass["passed_time"], str)
        assert isinstance(latest_pass["car_code"], str)

        current_positions = data["current_bus_positions"][0]
        assert {
            "stop_id",
            "passed_time",
            "car_code",
        }.issubset(current_positions.keys())
        assert isinstance(current_positions["stop_id"], str)
        assert isinstance(current_positions["passed_time"], str)
        assert isinstance(current_positions["car_code"], str)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_approach_not_found() -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_approach", {"route_code": "9999999"})
        assert result.data is None, "Expected empty list for non-existent route code"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_busstop_info_succeeds_and_has_expected_structure() -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "get_busstop_info", {"station_number": NAGOYA_STATION_NUMBER}
        )
        data = result.data

        # Basic structure checks
        assert isinstance(data, dict)
        assert data["name"] == "名古屋駅"
        assert data["kana"] == "なごやえき"
        assert isinstance(data["poles"], list)
        assert len(data["poles"]) > 0

        pole = data["poles"][0]
        assert {
            "code",
            "bcode",
            "noriba",
            "keitos",
        }.issubset(pole.keys())
        assert isinstance(pole["code"], str)
        assert isinstance(pole["bcode"], str)
        assert isinstance(pole["noriba"], str)
        assert isinstance(pole["keitos"], list)
        assert len(pole["keitos"]) > 0
        assert all(isinstance(rc, str) and rc for rc in pole["keitos"])


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_busstop_info_not_found() -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "get_busstop_info", {"station_number": 123456789}
        )
        assert result.data is None, "Expected None for non-existent station number"
