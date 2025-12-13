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
INVALID_STATION_ID = 99999
ROUTE_CODE = "1123002"
INVALID_ROUTE_CODE = "9999999"


def create_mock_transport(
    *, path: str, response: httpx.Response
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == path:
            return response
        # Simulate the server behavior that returns an HTML 404 page with HTTP status
        # code 200 for non-existent resources.
        return httpx.Response(
            status_code=200,
            content="""<html>
<head><title>404 NotFound｜名古屋市交通局</title></head>
<body>404 Not Found</body>
</html>""".encode(),  # noqa: RUF001
            headers={"content-type": "text/html"},
        )

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
async def test_get_station_names_on_server_error(client_factory: ClientFactory) -> None:
    """Test HTTP error handling for get_station_names."""
    client = client_factory(
        create_mock_transport(
            path="/STATION_DATA/station_infos/station_name.json",
            response=httpx.Response(status_code=500),
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
async def test_get_station_diagram_on_not_found(client_factory: ClientFactory) -> None:
    """Test HTTP error handling for get_station_diagram."""
    client = client_factory(
        create_mock_transport(
            path="/",
            response=httpx.Response(status_code=200),
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_station_diagram(INVALID_STATION_ID)


@pytest.mark.asyncio
async def test_get_station_diagram_on_server_error(
    client_factory: ClientFactory,
) -> None:
    """Test HTTP error handling for get_station_diagram."""
    client = client_factory(
        create_mock_transport(
            path="/STATION_DATA/station_infos/diagrams/41200.json",
            response=httpx.Response(status_code=500),
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_station_diagram(NAGOYA_STATION_ID)


@pytest.mark.asyncio
async def test_get_bus_stops_success(
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

    result = await client.get_bus_stops(NAGOYA_STATION_ID)

    assert result is not None
    assert result.name == "名古屋駅"
    assert result.kana == "なごやえき"
    assert result.poles[0].noriba == "11番"
    assert result.poles[0].keitos == ["7871001", "7871011"]


@pytest.mark.asyncio
async def test_get_bus_stops_on_not_found(client_factory: ClientFactory) -> None:
    """Test HTTP error handling for get_bus_stops."""
    client = client_factory(
        create_mock_transport(
            path="/",
            response=httpx.Response(status_code=200),
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_bus_stops(INVALID_STATION_ID)


@pytest.mark.asyncio
async def test_get_bus_stops_on_server_error(client_factory: ClientFactory) -> None:
    """Test HTTP error handling for get_bus_stops."""
    client = client_factory(
        create_mock_transport(
            path="/BUS_SEKKIN/master_json/busstops/41200.json",
            response=httpx.Response(status_code=500),
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_bus_stops(NAGOYA_STATION_ID)


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

    result = await client.get_keitos(ROUTE_CODE)

    assert result is not None
    assert result.to == "栄"
    assert result.from_ == "中川車庫前"
    assert result.keito == "1123"
    assert result.busstops == ["41025701", "52025701", "31090101"]


@pytest.mark.asyncio
async def test_get_routes_on_not_found(client_factory: ClientFactory) -> None:
    """Test HTTP error handling for get_routes."""
    client = client_factory(
        create_mock_transport(
            path="/",
            response=httpx.Response(status_code=200),
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_keitos(INVALID_ROUTE_CODE)


@pytest.mark.asyncio
async def test_get_routes_on_server_error(client_factory: ClientFactory) -> None:
    """Test HTTP error handling for get_routes."""
    client = client_factory(
        create_mock_transport(
            path="/BUS_SEKKIN/master_json/keitos/1123002.json",
            response=httpx.Response(status_code=500),
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_keitos(ROUTE_CODE)


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

    assert result is not None
    assert result.latest_bus_pass == {
        "11015/301": {"NF 0612": "21:31:42"},
        "45055/301": {"NF 0612": "21:24:41"},
        "21010/1E1": {"NF 0612": "21:44:45"},
    }
    assert result.current_bus_positions == {"21010/1E1": {"NF 0612": "21:44:45"}}


@pytest.mark.asyncio
async def test_get_realtime_approach_multiple_positions(
    client_factory: ClientFactory,
    fixture_loader: FixtureLoader,
) -> None:
    """Test retrieval of approach information with multiple current bus positions."""
    client = client_factory(
        create_mock_transport(
            path="/BUS_SEKKIN/realtime_json/1123002.json",
            response=httpx.Response(
                status_code=200,
                json=fixture_loader("realtime_approach_multiple_positions.json"),
            ),
        )
    )

    result = await client.get_realtime_approach(ROUTE_CODE)

    assert result is not None
    assert result.latest_bus_pass == {
        "11015/301": {"NF 0612": "21:31:42"},
        "45055/301": {"NF 0612": "21:24:41"},
        "21010/1E1": {"NF 0612": "21:44:45"},
    }
    # Verify that all three current bus positions are accumulated
    assert result.current_bus_positions == {
        "21010/1E1": {"NF 0612": "21:44:45"},
        "11015/301": {"NF 0612": "21:31:42"},
        "45055/301": {"NF 0612": "21:24:41"},
    }
    assert len(result.current_bus_positions) == 3


@pytest.mark.asyncio
async def test_get_realtime_approach_on_not_found(
    client_factory: ClientFactory,
) -> None:
    """Test HTTP error handling for get_realtime_approach."""
    client = client_factory(
        create_mock_transport(
            path="/",
            response=httpx.Response(status_code=200),
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_realtime_approach(INVALID_ROUTE_CODE)


@pytest.mark.asyncio
async def test_get_realtime_approach_on_server_error(
    client_factory: ClientFactory,
) -> None:
    """Test HTTP error handling for get_realtime_approach."""
    client = client_factory(
        create_mock_transport(
            path="/BUS_SEKKIN/realtime_json/1123002.json",
            response=httpx.Response(status_code=500),
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_realtime_approach(ROUTE_CODE)


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
