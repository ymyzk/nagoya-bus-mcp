import re

from fastmcp import Client
import pytest

from nagoya_bus_mcp.mcp.server import mcp_server

NAGOYA_STATION_NUMBER = 41200


# TODO: Remove loop_scope by implementing proper client clean up
@pytest.mark.asyncio(loop_scope="module")
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


@pytest.mark.asyncio(loop_scope="module")
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


@pytest.mark.asyncio(loop_scope="module")
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


@pytest.mark.asyncio(loop_scope="module")
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


@pytest.mark.asyncio(loop_scope="module")
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


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.integration
async def test_get_timetable_not_found() -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_timetable", {"station_number": 123456789})
        assert result.data is None, "Expected None for non-existent station number"
