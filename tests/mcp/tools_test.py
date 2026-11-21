"""Unit tests for the MCP server and tools, run through an in-memory FastMCP client.

The Nagoya Bus API is replaced with an httpx mock transport serving fixtures, so
these tests exercise the FastMCP integration (lifespan context, tool schemas,
structured output and error mapping) without network access.
"""

from collections.abc import AsyncGenerator
from typing import Any

from fastmcp import Client
from fastmcp.exceptions import ToolError
import httpx
import pytest
import pytest_asyncio

from nagoya_bus_mcp import client as bus_client_module
from nagoya_bus_mcp.mcp import server as server_module
from nagoya_bus_mcp.mcp.server import Settings, build_mcp_server
from tests.types import FixtureLoader

NAGOYA_STATION_NUMBER = 41200
ROUTE_CODE = "1123002"

NOT_FOUND_HTML = """<html>
<head><title>404 NotFound｜名古屋市交通局</title></head>
<body>404 Not Found</body>
</html>""".encode()  # noqa: RUF001


def _mock_transport(fixture_loader: FixtureLoader) -> httpx.MockTransport:
    keito = fixture_loader("routes_1123002.json")
    # Align the route's bus stops with the realtime approach fixture
    keito["BUSSTOPS"] = ["11015301", "45055301", "210101E1"]
    routes: dict[str, Any] = {
        "/STATION_DATA/station_infos/station_name.json": fixture_loader(
            "station_name.json"
        ),
        "/BUS_SEKKIN/master_json/buspole_infos.json": fixture_loader(
            "buspole_infos.json"
        ),
        "/STATION_DATA/station_infos/diagrams/41200.json": fixture_loader(
            "diagrams_41200.json"
        ),
        f"/BUS_SEKKIN/master_json/keitos/{ROUTE_CODE}.json": keito,
        f"/BUS_SEKKIN/realtime_json/{ROUTE_CODE}.json": fixture_loader(
            "realtime_approach_1123002.json"
        ),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if (data := routes.get(request.url.path)) is not None:
            return httpx.Response(status_code=200, json=data)
        # The real API returns an HTML 404 page with HTTP status code 200.
        return httpx.Response(
            status_code=200,
            content=NOT_FOUND_HTML,
            headers={"content-type": "text/html"},
        )

    return httpx.MockTransport(handler)


@pytest_asyncio.fixture
async def mcp_client(
    monkeypatch: pytest.MonkeyPatch, fixture_loader: FixtureLoader
) -> AsyncGenerator[Client[Any]]:
    transport = _mock_transport(fixture_loader)
    real_client = bus_client_module.Client

    def client_with_mock_transport(
        **kwargs: Any,  # noqa: ANN401
    ) -> bus_client_module.Client:
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(server_module, "Client", client_with_mock_transport)
    async with Client(build_mcp_server(Settings())) as client:
        yield client


@pytest.mark.asyncio
async def test_list_tools(mcp_client: Client[Any]) -> None:
    tools = await mcp_client.list_tools()

    assert {tool.name for tool in tools} == {
        "get_station_number",
        "get_timetable",
        "get_approach_for_route",
        "get_approach_for_station",
    }
    for tool in tools:
        # ctx must not leak into the input schema
        assert "ctx" not in tool.input_schema.get("properties", {})
        assert tool.output_schema is not None


@pytest.mark.asyncio
async def test_list_prompts(mcp_client: Client[Any]) -> None:
    prompts = await mcp_client.list_prompts()

    assert {prompt.name for prompt in prompts} == {
        "ask_timetable",
        "ask_bus_approach",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("station_name", ["名古屋駅", "名古駅"])
async def test_get_station_number(mcp_client: Client[Any], station_name: str) -> None:
    result = await mcp_client.call_tool(
        "get_station_number", {"station_name": station_name}
    )

    assert result.structured_content == {
        "station_name": "名古屋駅",
        "station_number": NAGOYA_STATION_NUMBER,
    }


@pytest.mark.asyncio
async def test_get_station_number_not_found(mcp_client: Client[Any]) -> None:
    with pytest.raises(ToolError, match="Station not found: 存在しないバス停"):
        await mcp_client.call_tool(
            "get_station_number", {"station_name": "存在しないバス停"}
        )


@pytest.mark.asyncio
async def test_get_timetable(mcp_client: Client[Any]) -> None:
    result = await mcp_client.call_tool(
        "get_timetable", {"station_number": NAGOYA_STATION_NUMBER}
    )
    data = result.structured_content

    assert data is not None
    assert data["station_number"] == NAGOYA_STATION_NUMBER
    assert data["url"] == (
        "https://www.kotsu.city.nagoya.jp/jp/pc/bus/timetable_list.html"
        "?name=名古屋駅&toname="
    )
    assert len(data["timetables"]) > 0
    timetable = data["timetables"][0]
    assert timetable["route"] == "名駅20"
    assert all(isinstance(code, int) for code in timetable["route_codes"])
    assert len(timetable["stop_station_names"]) > 0


@pytest.mark.asyncio
async def test_get_timetable_not_found(mcp_client: Client[Any]) -> None:
    with pytest.raises(ToolError, match="Station number not found: 123456789"):
        await mcp_client.call_tool("get_timetable", {"station_number": 123456789})


@pytest.mark.asyncio
async def test_get_approach_for_route(mcp_client: Client[Any]) -> None:
    result = await mcp_client.call_tool(
        "get_approach_for_route", {"route_code": ROUTE_CODE}
    )
    data = result.structured_content

    assert data is not None
    assert [stop["bus_stop_code"] for stop in data["bus_stops"]] == [
        "11015301",
        "45055301",
        "210101E1",
    ]
    for bus_stop in data["bus_stops"]:
        assert isinstance(bus_stop["station_number"], int)
        assert isinstance(bus_stop["station_name"], str)
    assert isinstance(data["bus_positions"], list)


@pytest.mark.asyncio
async def test_get_approach_for_route_not_found(mcp_client: Client[Any]) -> None:
    with pytest.raises(ToolError, match="404 Not Found"):
        await mcp_client.call_tool("get_approach_for_route", {"route_code": "9999999"})
