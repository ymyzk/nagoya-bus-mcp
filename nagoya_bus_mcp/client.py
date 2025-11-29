"""HTTP client for Nagoya Bus API."""

from types import TracebackType
from typing import Self

import httpx
from pydantic import BaseModel, ConfigDict, Field, RootModel
from datetime import datetime

StationNamesResponse = RootModel[dict[str, int]]
Diagram = RootModel[dict[str, dict[int, list[int]]]]


class DiagramRoute(BaseModel):
    model_config = ConfigDict(alias_generator=str.upper)
    polename: str
    railway: list[str]
    stations: list[list[str]]
    diagram: Diagram


DiagramResponse = RootModel[dict[str, list[DiagramRoute]]]


class Pole(BaseModel):
    """Pole information model."""
    model_config = ConfigDict(alias_generator=str.upper)

    route_codes: list[str] = Field(alias="KEITOS")
    code: str = Field(alias="CODE")
    bcode: str = Field(alias="BCODE")
    noriba: str = Field(alias="NORIBA")


class Busstop(BaseModel):
    """Bus stop information model."""
    model_config = ConfigDict(alias_generator=str.upper)

    poles: list[Pole] = Field(alias="POLES")
    name: str = Field(alias="NAME")
    kana: str = Field(alias="KANA")


BusstopResponse = RootModel[Busstop]


class Route(BaseModel):
    """Route master information model."""
    model_config = ConfigDict(alias_generator=str.upper)

    to: str
    from_: str = Field(alias="FROM")
    direction: str
    no: str
    article: str
    keito: str
    rosen: str
    busstops: list[str]


RouteResponse = RootModel[Route]


class Approach(BaseModel):
    """Real-time approach information model."""
    model_config = ConfigDict(alias_generator=str.upper)

    latest_bus_pass: dict[str, dict]

ApproachInfoResponse = RootModel[Approach]


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
            station_number: The station number to get the diagram for

        Returns:
            DiagramResponse: Response containing the station's timetable data
        """
        url = f"/STATION_DATA/station_infos/diagrams/{station_number}.json"
        response = await self.client.get(url)
        response.raise_for_status()
        return DiagramResponse.model_validate(response.json())

    async def get_busstops(self, station_number: int) -> BusstopResponse:
        """Get bus stop information for a specific station.

        Args:
            station_number: The station number to get bus stop information for
        Returns:
            list[RouteInfo]: List of route information for the station
        """
        parsed_station_number = str(station_number).zfill(5)
        url = f"/BUS_SEKKIN/master_json/busstops/{parsed_station_number}.json"
        response = await self.client.get(url)
        response.raise_for_status()
        return BusstopResponse.model_validate(response.json())


    async def get_routes(self, route_code: str) -> RouteResponse:
        """Get route master information for a specific route.

        Args:
            route_code: The route code to get the master information for
        Returns:
            dict: The route master information data
        """
        url = f"/BUS_SEKKIN/master_json/keitos/{route_code}.json"
        response = await self.client.get(url)
        response.raise_for_status()
        return RouteResponse.model_validate(response.json())


    async def get_realtime_approach(self, route_code: str) -> ApproachInfoResponse:
        """Get real-time approach information for a specific bus.

        Args:
            route_code: The route code to get the real-time approach information for
        Returns:
            dict: The real-time approach information data
        """
        timestamp = datetime.now().timestamp()
        url = f"/BUS_SEKKIN/realtime_json/{route_code}.json?_={int(timestamp)}"
        response = await self.client.get(url)
        response.raise_for_status()
        return ApproachInfoResponse.model_validate(response.json())


if __name__ == "__main__":
    import asyncio

    async def main() -> None:
        async with Client() as client:
            print(await client.get_station_names())
            print(await client.get_station_diagram(22460))

    asyncio.run(main())
