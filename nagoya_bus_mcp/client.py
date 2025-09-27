"""HTTP client for Nagoya Bus API."""

from types import TracebackType
from typing import Self

import httpx
from pydantic import BaseModel, ConfigDict, RootModel

StationNamesResponse = RootModel[dict[str, int]]
Diagram = RootModel[dict[str, dict[int, list[int]]]]


class DiagramRoute(BaseModel):
    model_config = ConfigDict(alias_generator=str.upper)
    polename: str
    railway: list[str]
    stations: list[list[str]]
    diagram: Diagram


DiagramResponse = RootModel[dict[str, list[DiagramRoute]]]


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


if __name__ == "__main__":
    import asyncio

    async def main() -> None:
        async with Client() as client:
            print(await client.get_station_names())
            print(await client.get_station_diagram(22460))

    asyncio.run(main())
