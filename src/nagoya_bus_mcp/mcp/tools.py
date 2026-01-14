"""MCP tool implementations for Nagoya Bus information queries."""

import asyncio
from functools import reduce
from logging import getLogger
from operator import iadd, itemgetter
from typing import TYPE_CHECKING, Annotated, cast

from fastmcp import Context
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

from nagoya_bus_mcp.approach import (
    ApproachBusStop,
    ApproachPosition,
    get_realtime_approach,
)
from nagoya_bus_mcp.client import Client
from nagoya_bus_mcp.data import BaseData

if TYPE_CHECKING:
    from nagoya_bus_mcp.mcp.server import LifespanContext

log = getLogger(__name__)


class StationNumberResponse(BaseModel):
    """Response model for station number lookup by name.

    Used by the get_station_number tool to return station lookup results,
    including fuzzy matching outcomes.
    """

    station_name: Annotated[str, Field(description="バス停名")]
    station_number: Annotated[int, Field(description="バス停番号")]


class TimeTable(BaseModel):
    """Timetable information for a single route at a station.

    Contains route details, direction, boarding location, and departure times
    organized by day of week.
    """

    route: Annotated[str, Field(description="系統")]
    route_codes: Annotated[list[int], Field(description="系統コードのリスト")]
    direction: Annotated[str, Field(description="行き先")]
    pole: Annotated[str, Field(description="のりば")]
    stop_station_names: Annotated[list[str], Field(description="停車バス停名のリスト")]
    timetable: Annotated[dict[str, list[str]], Field(description="曜日別の時刻表")]
    url: Annotated[str, Field(description="系統の時刻表のURL")]


class TimeTableResponse(BaseModel):
    """Response model for station timetable queries.

    Contains all timetables for different routes operating at a given station,
    along with the station identifier and reference URL.
    """

    station_number: Annotated[int, Field(description="バス停番号")]
    timetables: list[TimeTable]
    url: Annotated[str, Field(description="系統別の時刻表一覧のURL")]


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
        Field(description="通過時間を含む、系統のバス停のリスト"),
    ]
    bus_positions: Annotated[
        list[ApproachPosition], Field(description="現在走行中のバスの位置のリスト")
    ]


class ApproachingBusForStationRoute(BaseModel):
    """Real-time information about a bus approaching a station on a specific route."""

    location: Annotated[str, Field(description="接近中のバスの現在位置の説明")]
    previous_station_name: Annotated[str, Field(description="直前に通過したバス停名")]
    pass_time: Annotated[str, Field(description="直前のバス停の通過時刻(HH:MM:SS形式)")]


class ApproachForStationRoute(BaseModel):
    """Real-time approach information for a specific route at a station."""

    route: Annotated[str, Field(description="系統")]
    route_code: Annotated[str, Field(description="系統コード")]
    direction: Annotated[str, Field(description="行き先")]
    pole: Annotated[str, Field(description="のりば")]
    last_pass_time: Annotated[
        str | None, Field(description="前回のバスがのりばを通過した時刻 (HH:MM:SS形式)")
    ] = None
    approaching_buses: Annotated[
        list[ApproachingBusForStationRoute], Field(description="接近中のバスの情報")
    ]


class ApproachForStationResponse(BaseModel):
    """Real-time approach information for a specific station.

    Contains the latest bus passage information and current bus positions
    for the specified station.
    """

    routes: Annotated[
        list[ApproachForStationRoute], Field(description="接近情報のある系統のリスト")
    ]
    url: Annotated[str, Field(description="バス停の接近情報のURL")]


def _get_context_from_context(ctx: Context) -> tuple[Client, BaseData]:
    """Extract the bus client and base data from the context.

    Args:
        ctx: The FastMCP context object.

    Returns:
        A tuple of (Client, BaseData).

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
    return lifespan_context.bus_client, lifespan_context.base_data


async def get_station_number(ctx: Context, station_name: str) -> StationNumberResponse:
    """Get station number for a given station name using fuzzy matching.

    Attempts exact match first, then falls back to fuzzy matching with 60%
    similarity threshold if no exact match is found.

    Args:
        ctx: FastMCP context containing the bus client.
        station_name: The station name to look up (e.g., "名古屋駅").

    Returns:
        StationNumberResponse with matched station details.

    Raises:
        ToolError: If no station matches the given name.
    """
    _, base_data = _get_context_from_context(ctx)

    log.info("Getting station number for %s", station_name)

    # First try exact match
    if station_number := base_data.get_station_number(station_name):
        return StationNumberResponse(
            station_name=station_name, station_number=station_number
        )

    # If no exact match, try fuzzy matching
    log.info("No exact match found for %s, trying fuzzy matching", station_name)

    if closest_station_number := base_data.find_station_number(
        station_name, cutoff=0.6
    ):
        closest_station = base_data.get_station_name(closest_station_number)
        if closest_station is None:
            msg = "Inconsistent base data: station number has no name"
            raise ToolError(msg)
        log.info(
            "Found closest match: %s (station number: %s)",
            closest_station,
            closest_station_number,
        )
        return StationNumberResponse(
            station_name=closest_station,
            station_number=closest_station_number,
        )

    log.info("No fuzzy match found for %s", station_name)
    msg = f"Station not found: {station_name}"
    raise ToolError(msg)


async def get_timetable(ctx: Context, station_number: int) -> TimeTableResponse:
    """Get formatted timetable information for all routes at a station.

    Retrieves and formats timetable data including routes, directions, boarding
    locations, and departure times organized by day of week.

    Args:
        ctx: FastMCP context containing the bus client.
        station_number: The station number to query (e.g., 22460).

    Returns:
        TimeTableResponse with all timetables for the station.

    Raises:
        ToolError: If the station number is not found in base data.
    """
    client, base_data = _get_context_from_context(ctx)

    station_name = base_data.get_station_name(station_number)
    if station_name is None:
        log.warning("Station number %s not found", station_number)
        msg = f"Station number not found: {station_number}"
        raise ToolError(msg)

    log.info("Getting timetable for station number %s", station_number)
    diagram_response = await client.get_station_diagram(station_number)

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
                    stop_station_names=reduce(iadd, railway.stations, []),
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


async def get_approach_for_route(
    ctx: Context, route_code: str
) -> ApproachForRouteResponse:
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
    client, base_data = _get_context_from_context(ctx)

    log.info("Getting real-time approach information for route code %s", route_code)

    approach_info = await get_realtime_approach(client, base_data, route_code)
    bus_stops = [
        ApproachForRouteBusStop(
            bus_stop_code=bus_stop.bus_stop_code,
            station_number=bus_stop.station_number,
            station_name=bus_stop.station_name,
            pole=bus_stop.pole,
            last_pass_time=approach_info.latest_passes[
                bus_stop.bus_stop_code
            ].passed_time
            if bus_stop.bus_stop_code in approach_info.latest_passes
            else None,
        )
        for bus_stop in approach_info.bus_stops
    ]

    return ApproachForRouteResponse(
        bus_stops=bus_stops,
        bus_positions=approach_info.current_positions,
    )


_MAX_SORT_KEY = 2**32 - 1


async def get_approach_for_station(
    ctx: Context, station_number: int
) -> ApproachForStationResponse:
    """Get real-time bus approach information for all routes at a station.

    Provides a list of routes that currently have activity at the specified
    station (either a recent passage time or at least one approaching bus),
    along with a URL for more details.

    Routes that have neither a latest pass time nor any approaching buses are
    filtered out and are not included in the result. The remaining routes are
    sorted by the proximity of their approaching buses so that routes with the
    nearest approaching vehicles appear first.

    Args:
        ctx: FastMCP context containing the bus client.
        station_number: The station number to query (e.g., 22460).
    """
    client, base_data = _get_context_from_context(ctx)

    log.info(
        "Getting real-time approach information for station number %s", station_number
    )

    bus_stop = await client.get_bus_stop(station_number)
    station_name = bus_stop.name
    route_codes = [
        (keito, pole.code) for pole in bus_stop.poles for keito in pole.keitos
    ]

    approaches: list[tuple[int, ApproachForStationRoute]] = []

    approach_infos = await asyncio.gather(
        *(
            get_realtime_approach(client, base_data, route_code)
            for route_code, _ in route_codes
        )
    )

    for (route_code, pole_code), approach_info in zip(
        route_codes, approach_infos, strict=True
    ):
        sort_key = _MAX_SORT_KEY
        bus_stop_code = f"{station_number:05}{pole_code}"
        approach_bus_stop = approach_info.get_bus_stop_for_code(bus_stop_code)

        approaching_buses: list[ApproachingBusForStationRoute] = []
        positions_before = approach_info.get_current_positions_before_code(
            bus_stop_code
        )
        for n, position in positions_before:
            sort_key = min(sort_key, n)
            approaching_buses.append(
                ApproachingBusForStationRoute(
                    location=f"{n}停前を通過",
                    previous_station_name=position.previous_stop.station_name,
                    pass_time=position.passed_time,
                )
            )

        last_pass_time = approach_info.get_last_pass_time_for_code(bus_stop_code)

        if last_pass_time is None and len(approaching_buses) == 0:
            continue

        approaches.append(
            (
                sort_key,
                ApproachForStationRoute(
                    route_code=route_code,
                    route=approach_info.route,
                    direction=approach_info.direction,
                    last_pass_time=last_pass_time,
                    pole=approach_bus_stop.pole
                    if approach_bus_stop
                    else "不明なのりば",
                    approaching_buses=approaching_buses,
                ),
            )
        )
    return ApproachForStationResponse(
        routes=[approach for _, approach in sorted(approaches, key=itemgetter(0))],
        url=f"https://www.kotsu.city.nagoya.jp/jp/pc/BUS/stand_access.html?name={station_name}",
    )
