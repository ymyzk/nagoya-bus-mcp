"""HTTP client for Nagoya Bus API."""

from datetime import UTC, datetime
from types import TracebackType
from typing import Self

import httpx
from pydantic import BaseModel, ConfigDict, Field, RootModel

# Shared config for models with uppercase field aliases
_UPPER_ALIAS_CONFIG = ConfigDict(alias_generator=str.upper)

# e.g., {"白川通大津": 22460, "栄": 22010}
StationNamesResponse = RootModel[dict[str, int]]
# e.g., {"土曜": {"栄17": {"6": [13, 43], "7": [30, 59]}}}
Diagram = RootModel[dict[str, dict[int, list[int]]]]


class DiagramRoute(BaseModel):
    """Timetable diagram for a specific route and pole at a station.

    Contains the pole name, railway direction, station stops, and time diagram
    organized by day of week and hour.
    """

    model_config = _UPPER_ALIAS_CONFIG
    polename: str  # e.g., "1番"
    railway: list[str]  # e.g., ["名古屋大学(吹上経由)"]
    stations: list[list[str]]  # e.g., [["矢場町", "名古屋大学"]]
    diagram: Diagram


# Key: Route code like 栄17
# e.g., {"栄17": [DiagramRoute(...)], "栄21": [DiagramRoute(...)]}
DiagramResponse = RootModel[dict[str, list[DiagramRoute]]]


class BusStopPole(BaseModel):
    """Pole information model."""

    model_config = _UPPER_ALIAS_CONFIG

    keitos: list[str]  # e.g., ["1117001", "1120011"]
    code: str  # e.g., "5E1"
    bcode: str  # e.g., "5E1"
    noriba: str  # e.g., "1番"


class BusStopResponse(BaseModel):
    """Bus stop information model."""

    model_config = _UPPER_ALIAS_CONFIG

    poles: list[BusStopPole]
    name: str  # e.g., "白川通大津"
    kana: str  # e.g., "しらかわどおりおおつ"


class KeitoResponse(BaseModel):
    """Route master information model."""

    model_config = _UPPER_ALIAS_CONFIG

    to: str
    from_: str = Field(alias="FROM")
    direction: str
    no: str
    article: str
    keito: str
    rosen: str
    busstops: list[str]


class ApproachInfoResponse(BaseModel):
    """Real-time approach information model."""

    model_config = _UPPER_ALIAS_CONFIG

    # e.g., {"71145/1E1": {"NS 0341": "14:24:32"}}
    latest_bus_pass: dict[str, dict[str, str]]
    current_bus_positions: dict[str, dict[str, str]]


class Client:
    """HTTP client for Nagoya Bus API."""

    def __init__(
        self,
        base_url: str = "https://www.kotsu.city.nagoya.jp",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Initialize the client with an httpx session."""
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, transport=transport)

    async def __aenter__(self) -> Self:
        """Enter the async context manager by returning the client instance."""
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        """Ensure the underlying httpx client is closed on exit."""
        await self.close()

    async def close(self) -> None:
        """Close the client session."""
        await self.client.aclose()

    async def get_station_names(self) -> StationNamesResponse:
        """Get station names and their corresponding numbers.

        Returns:
            StationNamesResponse: Mapping of station names to their numbers
        """
        url = "/STATION_DATA/station_infos/station_name.json"
        response = await self.client.get(url)
        response.raise_for_status()
        return StationNamesResponse.model_validate(response.json())

    async def get_station_diagram(self, station_number: int) -> DiagramResponse:
        """Get timetable diagram for a specific station.

        Args:
            station_number: The station number (e.g., 22460 for 白川通大津).

        Returns:
            DiagramResponse: Mapping of route codes to diagram information.

        Raises:
            httpx.HTTPStatusError: If the station is not found (API returns 404).
        """
        url = f"/STATION_DATA/station_infos/diagrams/{station_number}.json"
        response = await self.client.get(url)
        response.raise_for_status()
        self._check_404(response)
        return DiagramResponse.model_validate(response.json())

    async def get_bus_stops(self, station_number: int) -> BusStopResponse:
        """Get bus stop information for a specific station.

        Args:
            station_number: The station number (e.g., 22460).

        Returns:
            BusStopResponse: Bus stop details including poles and route codes.

        Raises:
            httpx.HTTPStatusError: If the station is not found (API returns 404).
        """
        url = f"/BUS_SEKKIN/master_json/busstops/{station_number:05}.json"
        response = await self.client.get(url)
        response.raise_for_status()
        self._check_404(response)
        return BusStopResponse.model_validate(response.json())

    async def get_keitos(self, keito_code: str) -> KeitoResponse:
        """Get route master information for a specific route.

        Args:
            keito_code: The route code (keito) to fetch information for
                (e.g., "1117001").

        Returns:
            KeitoResponse: Route metadata including origin, destination, and stops.

        Raises:
            httpx.HTTPStatusError: If the route is not found (API returns 404).
        """
        url = f"/BUS_SEKKIN/master_json/keitos/{keito_code}.json"
        response = await self.client.get(url)
        response.raise_for_status()
        self._check_404(response)
        return KeitoResponse.model_validate(response.json())

    async def get_realtime_approach(
        self, route_code: str, current_time: datetime | None = None
    ) -> ApproachInfoResponse:
        """Get real-time approach information for buses on a route.

        Args:
            route_code: The route code to query (e.g., "1123002").
            current_time: Optional timestamp for the query. Defaults to current
                UTC time if not provided.

        Returns:
            ApproachInfoResponse: Latest bus passages and current positions.

        Raises:
            httpx.HTTPStatusError: If the route is not found (API returns 404).
        """
        if current_time is None:
            current_time = datetime.now(tz=UTC)
        url = f"/BUS_SEKKIN/realtime_json/{route_code}.json"
        response = await self.client.get(
            url, params={"_": int(current_time.timestamp())}
        )
        response.raise_for_status()
        self._check_404(response)

        approach_info: dict[str, dict[str, str]] = {}
        approach_info["CURRENT_BUS_POSITIONS"] = {}
        for k, v in response.json().items():
            if k == "LATEST_BUS_PASS":
                approach_info[k] = v
            else:
                approach_info["CURRENT_BUS_POSITIONS"][k] = v

        return ApproachInfoResponse.model_validate(approach_info)

    @staticmethod
    def _check_404(response: httpx.Response) -> None:
        """Check if the response indicates a 404 Not Found error.

        The Nagoya Bus API returns an HTML 404 page with HTTP status code 200
        for non-existent resources. This function checks for that case and raises
        an HTTPStatusError if detected.
        """
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type and b"404 NotFound" in response.content:
            msg = "404 Not Found"
            raise httpx.HTTPStatusError(
                msg,
                request=response.request,
                response=response,
            )


if __name__ == "__main__":
    import asyncio

    async def main() -> None:
        """Test the client by fetching various data."""
        async with Client() as client:
            print(await client.get_station_names())
            # 白川通大津
            print(await client.get_station_diagram(22460))
            print(await client.get_bus_stops(22460))
            print(await client.get_keitos("1123002"))
            print(await client.get_realtime_approach("1123002"))

    asyncio.run(main())
