"""MCP tool implementations for Nagoya Bus information queries."""

import difflib
from functools import reduce
from logging import getLogger
from operator import iadd
from typing import TYPE_CHECKING, Annotated, cast

from fastmcp import Context
from pydantic import BaseModel, Field

from nagoya_bus_mcp.client import Client

if TYPE_CHECKING:
    from nagoya_bus_mcp.mcp.server import LifespanContext

log = getLogger(__name__)


class StationNumberResponse(BaseModel):
    """Response model for station number lookup by name.

    Used by the get_station_number tool to return station lookup results,
    including fuzzy matching outcomes.
    """

    success: bool
    station_name: str | None = None
    station_number: int | None = None


class TimeTable(BaseModel):
    """Timetable information for a single route at a station.

    Contains route details, direction, boarding location, and departure times
    organized by day of week.
    """

    route: Annotated[str, Field(description="路線")]
    direction: Annotated[str, Field(description="方面")]
    pole: Annotated[str, Field(description="乗り場")]
    stop_stations: Annotated[list[str], Field(description="停車バス停のリスト")]
    timetable: Annotated[dict[str, list[str]], Field(description="曜日別の時刻表")]
    url: str


class TimeTableResponse(BaseModel):
    """Response model for station timetable queries.

    Contains all timetables for different routes operating at a given station,
    along with the station identifier and reference URL.
    """

    station_number: int
    timetables: list[TimeTable]
    url: str


class PoleInfoResponse(BaseModel):
    """Information about a specific pole (boarding location) at a bus stop.

    Each pole serves one or more routes and has associated codes for
    identification and real-time tracking.
    """

    keitos: Annotated[list[str], Field(description="路線コードのリスト")]
    code: Annotated[str, Field(description="ポールコード")]
    bcode: Annotated[str, Field(description="バスコード")]
    noriba: Annotated[str, Field(description="乗り場名")]


class RouteInfoResponse(BaseModel):
    """Master information for a specific bus route.

    Contains metadata about the route including origin, destination,
    route number, and the complete list of stops along the route.
    """

    to: Annotated[str, Field(description="行き先")]
    from_: Annotated[str, Field(description="出発地")]
    direction: Annotated[str, Field(description="方向")]
    no: Annotated[str, Field(description="路線番号")]
    article: Annotated[str, Field(description="記事")]
    keito: Annotated[str, Field(description="系統コード")]
    rosen: Annotated[str, Field(description="路線名")]
    busstops: Annotated[list[str], Field(description="バス停のリスト")]


class BusstopInfoResponse(BaseModel):
    """Complete information about a bus stop.

    Contains the stop name, phonetic reading, and details about all
    boarding locations (poles) at the stop.
    """

    poles: Annotated[list[PoleInfoResponse], Field(description="乗り場のリスト")]
    name: Annotated[str, Field(description="バス停名")]
    kana: Annotated[str, Field(description="バス停名(カナ)")]


class StopApproachInfo(BaseModel):
    """Real-time information about a bus passing or approaching a stop.

    Contains the stop identifier, timestamp of the bus passing, and the
    unique vehicle code for tracking.
    """

    stop_id: Annotated[str, Field(description="停留所ID")]
    passed_time: Annotated[str, Field(description="通過時刻(HH:MM形式)")]
    car_code: Annotated[str, Field(description="車両コード")]


class ApproachResponse(BaseModel):
    """Real-time approach information for buses on a route.

    Provides both historical data (latest bus passages) and current
    position data for buses actively running on the route.
    """

    latest_bus_pass: Annotated[
        list[StopApproachInfo], Field(description="最新のバス通過情報")
    ]
    current_bus_positions: Annotated[
        list[StopApproachInfo], Field(description="現在のバス位置情報")
    ]


_cached_station_names: dict[str, int] | None = None
_cached_station_numbers: dict[int, str] | None = None
_cached_route_masters: dict[str, dict[str, dict[str, dict[str, str]]] | None] | None = (
    None
)
_cached_busstops: dict[int, dict[str, dict[str, str]] | None] | None = None


def _get_client_from_context(ctx: Context) -> Client:
    """Extract the bus client from the context.

    Args:
        ctx: The FastMCP context object.

    Returns:
        The bus client instance.

    Raises:
        RuntimeError: If request_context is None.
    """
    # See the following documentation on when request_context is available:
    # https://gofastmcp.com/servers/context#request-context-availability
    if ctx.request_context is None:
        msg = (
            "ctx.request_context is None"
            " because the MCP session has not been established yet."
        )
        raise RuntimeError(msg)
    lifespan_context = cast("LifespanContext", ctx.request_context.lifespan_context)
    return lifespan_context.bus_client


async def _get_station_names(client: Client) -> dict[str, int]:
    global _cached_station_names  # noqa: PLW0603
    if _cached_station_names is None:
        _cached_station_names = (await client.get_station_names()).root
    return _cached_station_names


async def _get_station_numbers(client: Client) -> dict[int, str]:
    global _cached_station_numbers  # noqa: PLW0603
    if _cached_station_numbers is None:
        _cached_station_numbers = {
            num: name for name, num in (await _get_station_names(client)).items()
        }
    return _cached_station_numbers


async def _get_route_master(
    client: Client, route_code: str
) -> dict[str, dict[str, dict[str, str]]] | None:
    """Get route master information from the API."""
    global _cached_route_masters  # noqa: PLW0603
    if _cached_route_masters is None:
        _cached_route_masters = {}
    if route_code not in _cached_route_masters:
        route_response = await client.get_keitos(route_code)
        if route_response is None:
            _cached_route_masters[route_code] = None
            return None
        _cached_route_masters[route_code] = route_response.model_dump()
    return _cached_route_masters[route_code]


async def _get_realtime_approach(
    client: Client, route_code: str
) -> dict[str, list[dict[str, str]]] | None:
    """Get real-time approach information from the API."""
    response = await client.get_realtime_approach(route_code)
    approach_response = {}
    if response is None or not response:
        return None

    for k, v in response.model_dump().items():
        stop_pass_info = []
        for stop_id, info in v.items():
            stop_approach = {}
            stop_approach["stop_id"] = stop_id.replace("/", "")
            cache_approach = [
                {"car_code": ck, "passed_time": cv} for ck, cv in info.items()
            ]
            stop_approach["passed_time"] = cache_approach[0]["passed_time"]
            stop_approach["car_code"] = cache_approach[0]["car_code"]
            stop_pass_info.append(stop_approach)
        approach_response[k] = stop_pass_info

    return approach_response


async def _get_busstops(
    client: Client, station_number: int
) -> dict[str, dict[str, str]] | None:
    """Get bus stop information from the API."""
    global _cached_busstops  # noqa: PLW0603
    if _cached_busstops is None:
        _cached_busstops = {}
    if station_number not in _cached_busstops:
        busstop_response = await client.get_bus_stops(station_number)
        if busstop_response is None:
            _cached_busstops[station_number] = None
            return None
        _cached_busstops[station_number] = busstop_response.model_dump()
    return _cached_busstops[station_number]


async def get_station_number(
    ctx: Context, station_name: str
) -> StationNumberResponse | None:
    """Get station number for a given station name using fuzzy matching.

    Attempts exact match first, then falls back to fuzzy matching with 60%
    similarity threshold if no exact match is found.

    Args:
        ctx: FastMCP context containing the bus client.
        station_name: The station name to look up (e.g., "名古屋駅").

    Returns:
        StationNumberResponse with success flag and matched station details,
        or None if the context is unavailable.
    """
    client = _get_client_from_context(ctx)

    log.info("Getting station number for %s", station_name)
    station_names = await _get_station_names(client)

    # First try exact match
    station_number = station_names.get(station_name)
    if station_number is not None:
        return StationNumberResponse(
            success=True, station_name=station_name, station_number=station_number
        )

    # If no exact match, try fuzzy matching
    log.info("No exact match found for %s, trying fuzzy matching", station_name)
    closest_matches = difflib.get_close_matches(
        station_name, station_names.keys(), n=1, cutoff=0.6
    )

    if closest_matches:
        closest_station = closest_matches[0]
        closest_station_number = station_names[closest_station]
        log.info(
            "Found closest match: %s (station number: %s)",
            closest_station,
            closest_station_number,
        )
        return StationNumberResponse(
            success=True,
            station_name=closest_station,
            station_number=closest_station_number,
        )

    log.info("No fuzzy match found for %s", station_name)
    return StationNumberResponse(success=False)


async def get_timetable(ctx: Context, station_number: int) -> TimeTableResponse | None:
    """Get formatted timetable information for all routes at a station.

    Retrieves and formats timetable data including routes, directions, boarding
    locations, and departure times organized by day of week.

    Args:
        ctx: FastMCP context containing the bus client.
        station_number: The station number to query (e.g., 22460).

    Returns:
        TimeTableResponse with all timetables for the station, or None if the
        station is not found.
    """
    client = _get_client_from_context(ctx)

    station_name = (await _get_station_numbers(client)).get(station_number)
    if station_name is None:
        log.warning("Station number %s not found", station_number)
        return None

    log.info("Getting timetable for station number %s", station_number)
    diagram_response = await client.get_station_diagram(station_number)
    if not diagram_response.root:
        log.error(
            "Failed to get station diagram for %s (%s)", station_name, station_number
        )
        return None

    timetables: list[TimeTable] = []
    for line, railways in diagram_response.root.items():
        for railway_index, railway in enumerate(railways):
            diagram: dict[str, list[str]] = {}
            for day, hour_minutes in railway.diagram.root.items():
                diagram[day] = []
                for hour, minutes in hour_minutes.items():
                    for minute in minutes:
                        diagram[day].append(f"{hour}:{minute:02}")
            timetables.append(
                TimeTable(
                    route=line,
                    direction="・".join(railway.railway),
                    stop_stations=reduce(iadd, railway.stations, []),
                    pole=railway.polename,
                    timetable=diagram,
                    url=f"{client.base_url}/jp/pc/bus/timetable_dtl.html?name={station_name}&keito={line}&lineindex={railway_index}",
                )
            )

    return TimeTableResponse(
        timetables=timetables,
        station_number=station_number,
        url=f"{client.base_url}/jp/pc/bus/timetable_list.html?name={station_name}&toname=",
    )


async def get_busstop_info(
    ctx: Context, station_number: int
) -> BusstopInfoResponse | None:
    """Get detailed bus stop information including all poles and routes.

    Retrieves pole information, route codes, and boarding location details
    for a specific bus stop. Results are cached for performance.

    Args:
        ctx: FastMCP context containing the bus client.
        station_number: The station number to query (e.g., 22460).

    Returns:
        BusstopInfoResponse with stop name and pole details, or None if not found.
    """
    client = _get_client_from_context(ctx)

    log.info("Getting bus stop information for station number %s", station_number)
    busstop_data = await _get_busstops(client, station_number)
    if not busstop_data:
        log.error("No bus stop information found for station number %s", station_number)
        return None

    return BusstopInfoResponse.model_validate(busstop_data)


async def get_route_master(ctx: Context, route_code: str) -> RouteInfoResponse | None:
    """Get master information for a specific bus route.

    Retrieves route metadata including origin, destination, route number,
    and the complete list of stops along the route. Results are cached.

    Args:
        ctx: FastMCP context containing the bus client.
        route_code: The route code (keito) to query (e.g., "1123002").

    Returns:
        RouteInfoResponse with route details and stop list, or None if not found.
    """
    client = _get_client_from_context(ctx)

    log.info("Getting route master information for route code %s", route_code)

    route_master = await _get_route_master(client, route_code)
    if not route_master:
        log.error("No route master information found for route code %s", route_code)
        return None

    return RouteInfoResponse.model_validate(route_master)


async def get_approach(ctx: Context, route_code: str) -> ApproachResponse | None:
    """Get real-time bus approach and position information for a route.

    Provides both historical data (latest bus passages at stops) and current
    position data for buses actively running on the route.

    Args:
        ctx: FastMCP context containing the bus client.
        route_code: The route code (keito) to query (e.g., "1123002").

    Returns:
        ApproachResponse with latest passages and current positions, or None
        if no data is available.
    """
    client = _get_client_from_context(ctx)

    log.info("Getting real-time approach information for route code %s", route_code)

    approach_info = await _get_realtime_approach(client, route_code)
    if not approach_info:
        log.error("No approach information found for route code %s", route_code)
        return None

    return ApproachResponse.model_validate(approach_info)
