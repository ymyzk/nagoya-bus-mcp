"""MCP tool implementations for Nagoya Bus information queries."""

import asyncio
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
    route_codes: Annotated[list[int], Field(description="路線コードのリスト")]
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


class BusstopInfoResponse(BaseModel):
    """Complete information about a bus stop.

    Contains the stop name, phonetic reading, and details about all
    boarding locations (poles) at the stop.
    """

    poles: Annotated[list[PoleInfoResponse], Field(description="乗り場のリスト")]
    name: Annotated[str, Field(description="バス停名")]
    kana: Annotated[str, Field(description="バス停名(カナ)")]


class ApproachBusStop(BaseModel):
    """Information about a bus stop on a specific route.

    Contains the code, station name, station number, and pole name.
    """

    code: Annotated[str, Field(description="コード (例: 02200702)")]
    station_number: Annotated[int, Field(description="バス停番号 (例: 02200)")]
    station_name: Annotated[str, Field(description="バス停名")]
    pole_name: Annotated[str, Field(description="乗り場名")]


class ApproachPosition(BaseModel):
    """Information about a bus position on a specific route.

    Contains the car code, previous stop, next stop, and passed time.
    """

    car_code: str
    previous_stop: ApproachBusStop
    passed_time: Annotated[str, Field(description="通過時刻(HH:MM:SS形式)")]
    next_stop: ApproachBusStop


class ApproachInfo(BaseModel):
    """Real-time approach information for a specific route."""

    bus_stops: list[ApproachBusStop]
    latest_passes: dict[str, ApproachPosition]
    current_positions: list[ApproachPosition]


class ApproachForRouteBusStop(ApproachBusStop):
    """Information about a bus stop on a specific route.

    Contains the code, station name, station number, and pole name.
    Additionally includes the last pass time of the most recent bus.
    """

    last_pass_time: Annotated[str | None, Field(description="最終通過時刻")] = None


class ApproachForRouteResponse(BaseModel):
    """Real-time approach information for a specific route.

    Contains the latest bus passage information and current bus positions
    for the specified route.
    """

    bus_stops: Annotated[
        list[ApproachForRouteBusStop],
        Field(description="通過時間を含む、路線のバス停のリスト"),
    ]
    bus_positions: Annotated[
        list[ApproachPosition], Field(description="現在走行中のバスの位置のリスト")
    ]


_cached_pole_names: dict[str, str] | None = None
_cached_station_names: dict[str, int] | None = None
_cached_station_numbers: dict[int, str] | None = None


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


async def _get_pole_names(client: Client) -> dict[str, str]:
    global _cached_pole_names  # noqa: PLW0603
    if _cached_pole_names is None:
        poles = (await client.get_bus_stop_pole_info()).root
        _cached_pole_names = {code: pole.n for code, pole in poles.items()}
    return _cached_pole_names


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
                    route_codes=(
                        railway.railway_ids  # pyrefly: ignore[bad-argument-type]
                    ),
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
    busstop = await client.get_bus_stop(station_number)

    return BusstopInfoResponse(
        name=busstop.name,
        kana=busstop.kana,
        poles=[
            PoleInfoResponse(
                keitos=pole.keitos,
                code=pole.code,
                bcode=pole.bcode,
                noriba=pole.noriba,
            )
            for pole in busstop.poles
        ],
    )


async def _resolve_bus_stop(client: Client, bus_stop_code: str) -> ApproachBusStop:
    """Resolve bus stop code to station information."""
    if len(bus_stop_code) < 5 or not bus_stop_code[:5].isdigit():  # noqa: PLR2004
        msg = f"bus_stop_code must be at least 5 digits, got: {bus_stop_code!r}"
        raise ValueError(msg)
    station_number = int(bus_stop_code[:5].lstrip("0"))
    station_name = (await _get_station_numbers(client)).get(station_number)
    pole_name = (await _get_pole_names(client)).get(bus_stop_code)
    return ApproachBusStop(
        code=bus_stop_code,
        station_number=station_number,
        station_name=station_name or "不明なバス停",
        pole_name=pole_name or "不明なのりば",
    )


async def _get_realtime_approach(client: Client, route_code: str) -> ApproachInfo:
    """Get real-time bus approach and position information for a route.

    This is a helper function that retrieves and processes real-time approach
    data for a given route code.
    """
    # e.g., ["62185701", "71060701", "31165701", ...]
    bus_stop_codes: list[str] = (await client.get_keito(route_code)).busstops
    approach = await client.get_realtime_approach(route_code)

    bus_stops: list[ApproachBusStop] = await asyncio.gather(
        *(_resolve_bus_stop(client, code) for code in bus_stop_codes)
    )
    code_to_bus_stop = {bus_stop.code: bus_stop for bus_stop in bus_stops}

    latest_passes: dict[str, ApproachPosition] = {}
    for station_pole_with_slash, passed_cars in approach.latest_bus_pass.items():
        next_stop_id = station_pole_with_slash.replace("/", "")
        next_stop_index = bus_stop_codes.index(next_stop_id)
        if next_stop_index == 0:
            log.warning(
                "Next stop is the first stop, skipping as there is no previous stop"
            )
            continue
        previous_stop_id = bus_stop_codes[next_stop_index - 1]
        for car_code, passed_time in passed_cars.items():
            if (
                previous_stop_id in latest_passes
                and latest_passes[previous_stop_id].passed_time >= passed_time
            ):
                continue
            latest_passes[previous_stop_id] = ApproachPosition(
                car_code=car_code,
                previous_stop=code_to_bus_stop[previous_stop_id],
                passed_time=passed_time,
                next_stop=code_to_bus_stop[next_stop_id],
            )

    current_positions: list[ApproachPosition] = []
    for station_pole_with_slash, passed_cars in approach.current_bus_positions.items():
        next_stop_id = station_pole_with_slash.replace("/", "")
        next_stop_index = bus_stop_codes.index(next_stop_id)
        if next_stop_index == 0:
            log.warning(
                "Next stop is the first stop, skipping as there is no previous stop"
            )
            continue
        previous_stop_id = bus_stop_codes[next_stop_index - 1]
        for car_code, passed_time in passed_cars.items():
            current_positions.append(
                ApproachPosition(
                    car_code=car_code,
                    previous_stop=code_to_bus_stop[previous_stop_id],
                    passed_time=passed_time,
                    next_stop=code_to_bus_stop[next_stop_id],
                )
            )

    return ApproachInfo(
        bus_stops=bus_stops,
        latest_passes=latest_passes,
        current_positions=current_positions,
    )


async def get_approach(
    ctx: Context, route_code: str
) -> ApproachForRouteResponse | None:
    """Get real-time bus approach and position information for a route.

    Provides both historical data (latest bus passages at stops) and current
    position data for buses actively running on the route.

    Args:
        ctx: FastMCP context containing the bus client.
        route_code: The route code (keito) to query (e.g., "1123002").

    Returns:
        RouteApproachResponse with latest passages and current positions, or None
        if no data is available.
    """
    client = _get_client_from_context(ctx)

    log.info("Getting real-time approach information for route code %s", route_code)

    approach_info = await _get_realtime_approach(client, route_code)
    bus_stops = [
        ApproachForRouteBusStop(
            code=bus_stop.code,
            station_number=bus_stop.station_number,
            station_name=bus_stop.station_name,
            pole_name=bus_stop.pole_name,
            last_pass_time=approach_info.latest_passes[bus_stop.code].passed_time
            if bus_stop.code in approach_info.latest_passes
            else None,
        )
        for bus_stop in approach_info.bus_stops
    ]

    return ApproachForRouteResponse(
        bus_stops=bus_stops,
        bus_positions=approach_info.current_positions,
    )
