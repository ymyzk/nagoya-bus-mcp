"""Unit tests for the HTTP client."""

from collections.abc import AsyncGenerator, Callable
import json
from pathlib import Path
import re
from typing import Any

import httpx
import pytest
import pytest_asyncio

from nagoya_bus_mcp.client import Client

FIXTURE_DIR = Path(__file__).parent / "fixtures"

# Test constants
NAGOYA_STATION_ID = 41200
SAKAE_STATION_ID = 21010
ROUTE_CODE = "1123002"


def create_mock_transport(
    *, path: str, response: httpx.Response
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == path:
            return response
        return httpx.Response(404, text="Not found")

    return httpx.MockTransport(handler)


FixtureLoader = Callable[[str], Any]


@pytest.fixture
def fixture_loader() -> FixtureLoader:
    def _fixture_loader(name: str) -> Any:  # noqa: ANN401
        fixture_path = FIXTURE_DIR / name
        with fixture_path.open("rb") as f:
            return json.load(f)

    return _fixture_loader


ClientFactory = Callable[[httpx.MockTransport], Client]


@pytest_asyncio.fixture
async def client_factory() -> AsyncGenerator[ClientFactory]:
    client: Client | None = None

    def _factory(transport: httpx.MockTransport) -> Client:
        nonlocal client
        client = Client(transport=transport)
        return client

    yield _factory
    if client:
        await client.close()


@pytest.mark.asyncio
async def test_get_station_names_success(
    client_factory: ClientFactory,
    fixture_loader: FixtureLoader,
) -> None:
    """Test successful retrieval of station names."""
    client = client_factory(
        create_mock_transport(
            path="/STATION_DATA/station_infos/station_name.json",
            response=httpx.Response(
                status_code=200,
                json=fixture_loader("station_name.json"),
            ),
        )
    )

    result = await client.get_station_names()

    assert result.root["名古屋駅"] == NAGOYA_STATION_ID
    assert result.root["栄"] == SAKAE_STATION_ID


@pytest.mark.asyncio
async def test_get_station_names_http_error(client_factory: ClientFactory) -> None:
    """Test HTTP error handling for get_station_names."""
    client = client_factory(
        create_mock_transport(
            path="/STATION_DATA/station_infos/station_name.json",
            response=httpx.Response(status_code=404),
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_station_names()


@pytest.mark.asyncio
async def test_get_station_diagram_success(
    client_factory: ClientFactory,
    fixture_loader: FixtureLoader,
) -> None:
    """Test successful retrieval of station diagram."""
    client = client_factory(
        create_mock_transport(
            path="/STATION_DATA/station_infos/diagrams/41200.json",
            response=httpx.Response(
                status_code=200,
                json=fixture_loader("diagrams_41200.json"),
            ),
        )
    )

    result = await client.get_station_diagram(NAGOYA_STATION_ID)

    # Assertions for the structure and content of the diagram
    assert "名駅20" in result.root
    route = result.root["名駅20"][0]
    assert route.polename == "21番"
    assert route.stations[0][:3] == [
        "名古屋駅",
        "笹島町",
        "ささしまライブ",
    ]
    assert route.diagram.root == {
        "土曜": {
            6: [33, 49],
            7: [10, 28, 51],
        },
        "平日": {
            6: [33, 51],
            7: [7, 19, 33, 53],
        },
        "日曜・休日": {
            6: [
                33,
                49,
            ],
            7: [
                10,
                28,
                51,
            ],
        },
    }


@pytest.mark.asyncio
async def test_get_station_diagram_http_error(client_factory: ClientFactory) -> None:
    """Test HTTP error handling for get_station_diagram."""
    client = client_factory(
        create_mock_transport(
            path="/STATION_DATA/station_infos/diagrams/41200.json",
            response=httpx.Response(status_code=404),
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_station_diagram(NAGOYA_STATION_ID)


@pytest.mark.asyncio
async def test_client_cannot_use_after_close(client_factory: ClientFactory) -> None:
    """Test using client as context manager."""
    client = client_factory(
        httpx.MockTransport(lambda _: httpx.Response(status_code=200, json={}))
    )

    try:
        # Test that we can use the client and then close it
        result = await client.get_station_names()
        assert result.root == {}
        await client.close()

        # After closing, the client should not be usable
        with pytest.raises(
            RuntimeError,
            match=re.escape("Cannot send a request, as the client has been closed."),
        ):
            await client.get_station_names()
    finally:
        # Ensure cleanup in case test fails
        if not client.client.is_closed:
            await client.close()


@pytest.mark.asyncio
async def test_get_busstops_success(
    client_factory: ClientFactory,
    fixture_loader: FixtureLoader,
) -> None:
    """Test successful retrieval of bus stops."""
    client = client_factory(
        create_mock_transport(
            path="/BUS_SEKKIN/master_json/busstops/41200.json",
            response=httpx.Response(
                status_code=200,
                json=fixture_loader("busstops_41200.json"),
            ),
        )
    )

    result = await client.get_busstops(NAGOYA_STATION_ID)

    assert result.root.name == "名古屋駅"
    assert result.root.kana == "なごやえき"
    assert result.root.poles[0].noriba == "11番"
    assert result.root.poles[0].route_codes == ["7871001", "7871011"]


@pytest.mark.asyncio
async def test_get_busstops_http_error(client_factory: ClientFactory) -> None:
    """Test HTTP error handling for get_busstops."""
    client = client_factory(
        create_mock_transport(
            path="/BUS_SEKKIN/master_json/busstops/41200.json",
            response=httpx.Response(status_code=404),
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_busstops(NAGOYA_STATION_ID)


@pytest.mark.asyncio
async def test_get_routes_success(
    client_factory: ClientFactory,
    fixture_loader: FixtureLoader,
) -> None:
    """Test successful retrieval of routes."""
    client = client_factory(
        create_mock_transport(
            path="/BUS_SEKKIN/master_json/keitos/1123002.json",
            response=httpx.Response(
                status_code=200,
                json=fixture_loader("routes_1123002.json"),
            ),
        )
    )

    result = await client.get_routes(ROUTE_CODE)

    assert result.root.to == "栄"
    assert result.root.from_ == "中川車庫前"
    assert result.root.keito == "1123"
    assert result.root.busstops == ["41025701", "52025701", "31090101"]


@pytest.mark.asyncio
async def test_get_routes_http_error(client_factory: ClientFactory) -> None:
    """Test HTTP error handling for get_routes."""
    client = client_factory(
        create_mock_transport(
            path="/BUS_SEKKIN/master_json/keitos/1123002.json",
            response=httpx.Response(status_code=404),
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_routes(ROUTE_CODE)


@pytest.mark.asyncio
async def test_get_realtime_approach_success(
    client_factory: ClientFactory,
    fixture_loader: FixtureLoader,
) -> None:
    """Test successful retrieval of real-time approach information."""
    client = client_factory(
        create_mock_transport(
            path="/BUS_SEKKIN/realtime_json/1123002.json",
            response=httpx.Response(
                status_code=200,
                json=fixture_loader("realtime_approach_1123002.json"),
            ),
        )
    )

    result = await client.get_realtime_approach(ROUTE_CODE)

    assert result.root.latest_bus_pass == {
        "11015/301": {"NF 0612": "21:31:42"},
        "45055/301": {"NF 0612": "21:24:41"},
        "21010/1E1": {"NF 0612": "21:44:45"},
    }


@pytest.mark.asyncio
async def test_get_realtime_approach_http_error(client_factory: ClientFactory) -> None:
    """Test HTTP error handling for get_realtime_approach."""
    client = client_factory(
        create_mock_transport(
            path="/BUS_SEKKIN/realtime_json/1123002.json",
            response=httpx.Response(status_code=404),
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_realtime_approach(ROUTE_CODE)
