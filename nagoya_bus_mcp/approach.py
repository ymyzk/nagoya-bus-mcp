"""Wrapper and utilities to process real-time approach information."""

from logging import getLogger
from typing import Annotated

from pydantic import BaseModel, Field

from nagoya_bus_mcp.client import Client
from nagoya_bus_mcp.data import BaseData

log = getLogger(__name__)


class ApproachBusStop(BaseModel):
    """Information about a bus stop on a specific route.

    Contains the code, station name, station number, and pole name.
    """

    bus_stop_code: Annotated[str, Field(description="のりばコード (例: 02200702)")]
    station_number: Annotated[int, Field(description="バス停番号 (例: 2200)")]
    station_name: Annotated[str, Field(description="バス停名")]
    pole: Annotated[str, Field(description="のりば")]


class ApproachPosition(BaseModel):
    """Information about a bus position on a specific route.

    Contains the car code, previous stop, next stop, and passed time.
    """

    car_code: Annotated[str, Field(description="車両コード")]
    previous_stop: Annotated[ApproachBusStop, Field(description="直前に通過したのりば")]
    passed_time: Annotated[str, Field(description="通過時刻(HH:MM:SS形式)")]
    next_stop: Annotated[ApproachBusStop, Field(description="次に通過するのりば")]


class ApproachInfo(BaseModel):
    """Real-time approach information for a specific route."""

    route: Annotated[str, Field(description="系統")]
    direction: Annotated[str, Field(description="行き先")]
    bus_stops: list[ApproachBusStop]
    latest_passes: Annotated[
        dict[Annotated[str, Field(description="のりばコード")], ApproachPosition],
        Field(description="各のりばの最新通過情報"),
    ]
    current_positions: list[ApproachPosition]

    def _get_index_for_code(self, code: str) -> int | None:
        """Get the index of a bus stop by its code.

        Args:
            code: The bus stop code to look up.
        """
        for i, bus_stop in enumerate(self.bus_stops):
            if bus_stop.bus_stop_code == code:
                return i
        return None

    def get_last_pass_time_for_code(self, code: str) -> str | None:
        """Get the last pass time for a given bus stop code.

        Args:
            code: The bus stop code to look up.
        """
        if code in self.latest_passes:
            return self.latest_passes[code].passed_time
        return None

    def get_bus_stop_for_code(self, code: str) -> ApproachBusStop | None:
        """Get the bus stop information for a given bus stop code.

        Args:
            code: The bus stop code to look up.
        """
        index = self._get_index_for_code(code)
        return None if index is None else self.bus_stops[index]

    def get_current_positions_before_code(
        self, code: str
    ) -> list[tuple[int, ApproachPosition]]:
        """Get the current bus positions before a given bus stop code.

        Args:
            code: The bus stop code to look up.
        """
        target_stop_index = self._get_index_for_code(code)
        if target_stop_index is None:
            return []
        positions: list[tuple[int, ApproachPosition]] = []
        for position in self.current_positions:
            previous_stop_index = self.bus_stops.index(position.previous_stop)
            if previous_stop_index < target_stop_index:
                positions.append((target_stop_index - previous_stop_index, position))
        return positions


def _resolve_bus_stop(base_data: BaseData, bus_stop_code: str) -> ApproachBusStop:
    """Resolve bus stop code to station information."""
    if len(bus_stop_code) < 5 or not bus_stop_code[:5].isdigit():  # noqa: PLR2004
        msg = f"bus_stop_code must be at least 5 digits, got: {bus_stop_code!r}"
        raise ValueError(msg)
    station_number = int(bus_stop_code[:5].lstrip("0"))
    station_name = base_data.get_station_name(station_number)
    pole_name = base_data.get_pole_name(bus_stop_code)
    return ApproachBusStop(
        bus_stop_code=bus_stop_code,
        station_number=station_number,
        station_name=station_name or "不明なバス停",
        pole=pole_name or "不明なのりば",
    )


_ROUTE_NAME_TRANSLATION_TABLE = str.maketrans(
    "１２３４５６７８９０Ｃ－",  # noqa: RUF001
    "1234567890C-",
)


def _normalize_route_name(name: str) -> str:
    """Normalize route names by converting full-width characters to half-width."""
    return name.translate(_ROUTE_NAME_TRANSLATION_TABLE)


async def get_realtime_approach(
    client: Client, base_data: BaseData, route_code: str
) -> ApproachInfo:
    """Get real-time bus approach and position information for a route.

    This function retrieves and processes real-time approach data for a given
    route code, including bus stop information, latest passage times, and
    current bus positions.

    Args:
        client: The bus API client.
        base_data: The base data containing station and pole information.
        route_code: The route code (keito) to query (e.g., "1123002").

    Returns:
        ApproachInfo containing bus stops, latest passages, and current positions.
    """
    keito = await client.get_keito(route_code)

    # e.g., ["62185701", "71060701", "31165701", ...]
    bus_stop_codes: list[str] = keito.busstops
    approach = await client.get_realtime_approach(route_code)

    bus_stops: list[ApproachBusStop] = [
        _resolve_bus_stop(base_data, code) for code in bus_stop_codes
    ]
    code_to_bus_stop = {bus_stop.bus_stop_code: bus_stop for bus_stop in bus_stops}

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

    direction = (
        f"{keito.from_}発 {keito.article} {keito.to}行き"
        if keito.article
        else f"{keito.from_}発 {keito.to}行き"
    )

    return ApproachInfo(
        route=_normalize_route_name(keito.name),
        direction=direction,
        bus_stops=bus_stops,
        latest_passes=latest_passes,
        current_positions=current_positions,
    )
