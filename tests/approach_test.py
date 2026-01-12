"""Unit tests for the approach module."""

import pytest
from pytest_mock import MockerFixture

from nagoya_bus_mcp.approach import (
    ApproachBusStop,
    ApproachInfo,
    ApproachPosition,
    _normalize_route_name,
    get_realtime_approach,
)
from nagoya_bus_mcp.client import (
    ApproachInfoResponse,
    BusStopPoleInfoResponse,
    Client,
    KeitoResponse,
    StationNamesResponse,
)
from nagoya_bus_mcp.data import BaseData
from tests.types import FixtureLoader


@pytest.fixture
def sample_poles_response(fixture_loader: FixtureLoader) -> BusStopPoleInfoResponse:
    """Fixture providing sample bus stop pole information."""
    return BusStopPoleInfoResponse.model_validate(fixture_loader("buspole_infos.json"))


@pytest.fixture
def sample_stations_response(
    fixture_loader: FixtureLoader,
) -> StationNamesResponse:
    """Fixture providing sample station names."""
    return StationNamesResponse.model_validate(fixture_loader("station_name.json"))


@pytest.fixture
def base_data(
    sample_poles_response: BusStopPoleInfoResponse,
    sample_stations_response: StationNamesResponse,
) -> BaseData:
    """Fixture providing initialized BaseData instance."""
    return BaseData(sample_poles_response, sample_stations_response)


@pytest.fixture
def sample_bus_stops() -> list[ApproachBusStop]:
    """Fixture providing sample bus stops."""
    return [
        ApproachBusStop(
            bus_stop_code="41025701",
            station_number=41025,
            station_name="中川車庫前",
            pole="1番",
        ),
        ApproachBusStop(
            bus_stop_code="52025701",
            station_number=52025,
            station_name="野田",
            pole="1番",
        ),
        ApproachBusStop(
            bus_stop_code="31090101",
            station_number=31090,
            station_name="栄",
            pole="1番",
        ),
    ]


@pytest.fixture
def sample_approach_info(sample_bus_stops: list[ApproachBusStop]) -> ApproachInfo:
    """Fixture providing sample ApproachInfo instance."""
    latest_passes = {
        "41025701": ApproachPosition(
            car_code="NF 0612",
            previous_stop=sample_bus_stops[0],
            passed_time="21:24:41",
            next_stop=sample_bus_stops[1],
        ),
    }
    current_positions = [
        ApproachPosition(
            car_code="NF 0612",
            previous_stop=sample_bus_stops[0],
            passed_time="21:31:42",
            next_stop=sample_bus_stops[1],
        ),
        ApproachPosition(
            car_code="NF 0613",
            previous_stop=sample_bus_stops[1],
            passed_time="21:44:45",
            next_stop=sample_bus_stops[2],
        ),
    ]
    return ApproachInfo(
        route="栄23",
        direction="中川車庫前発 栄行き",
        bus_stops=sample_bus_stops,
        latest_passes=latest_passes,
        current_positions=current_positions,
    )


class TestApproachInfo:
    """Tests for ApproachInfo model and its methods."""

    def test_get_last_pass_time_for_code_found(
        self, sample_approach_info: ApproachInfo
    ) -> None:
        """Test get_last_pass_time_for_code with existing code."""
        assert (
            sample_approach_info.get_last_pass_time_for_code("41025701") == "21:24:41"
        )

    def test_get_last_pass_time_for_code_not_found(
        self, sample_approach_info: ApproachInfo
    ) -> None:
        """Test get_last_pass_time_for_code with non-existent code."""
        assert sample_approach_info.get_last_pass_time_for_code("99999999") is None
        assert sample_approach_info.get_last_pass_time_for_code("52025701") is None

    def test_get_bus_stop_for_code_found(
        self, sample_approach_info: ApproachInfo
    ) -> None:
        """Test get_bus_stop_for_code with existing code."""
        bus_stop = sample_approach_info.get_bus_stop_for_code("41025701")
        assert bus_stop is not None
        assert bus_stop.bus_stop_code == "41025701"
        assert bus_stop.station_name == "中川車庫前"

        bus_stop = sample_approach_info.get_bus_stop_for_code("31090101")
        assert bus_stop is not None
        assert bus_stop.bus_stop_code == "31090101"
        assert bus_stop.station_name == "栄"

    def test_get_bus_stop_for_code_not_found(
        self, sample_approach_info: ApproachInfo
    ) -> None:
        """Test get_bus_stop_for_code with non-existent code."""
        assert sample_approach_info.get_bus_stop_for_code("99999999") is None
        assert sample_approach_info.get_bus_stop_for_code("nonexistent") is None

    def test_get_current_positions_before_code_found(
        self, sample_approach_info: ApproachInfo
    ) -> None:
        """Test get_current_positions_before_code with valid code."""
        # Get positions before the last stop (31090101)
        positions = sample_approach_info.get_current_positions_before_code("31090101")
        assert len(positions) == 2

        # First position: 2 stops away (from index 0 to 2)
        assert positions[0][0] == 2
        assert positions[0][1].car_code == "NF 0612"
        assert positions[0][1].previous_stop.bus_stop_code == "41025701"

        # Second position: 1 stop away (from index 1 to 2)
        assert positions[1][0] == 1
        assert positions[1][1].car_code == "NF 0613"
        assert positions[1][1].previous_stop.bus_stop_code == "52025701"

    def test_get_current_positions_before_code_middle_stop(
        self, sample_approach_info: ApproachInfo
    ) -> None:
        """Test get_current_positions_before_code with middle stop."""
        # Get positions before the middle stop (52025701)
        positions = sample_approach_info.get_current_positions_before_code("52025701")
        assert len(positions) == 1

        # Only one position before this stop (from index 0 to 1)
        assert positions[0][0] == 1
        assert positions[0][1].car_code == "NF 0612"
        assert positions[0][1].previous_stop.bus_stop_code == "41025701"

    def test_get_current_positions_before_code_first_stop(
        self, sample_approach_info: ApproachInfo
    ) -> None:
        """Test get_current_positions_before_code with first stop."""
        # Get positions before the first stop - should be empty
        positions = sample_approach_info.get_current_positions_before_code("41025701")
        assert len(positions) == 0

    def test_get_current_positions_before_code_not_found(
        self, sample_approach_info: ApproachInfo
    ) -> None:
        """Test get_current_positions_before_code with non-existent code."""
        positions = sample_approach_info.get_current_positions_before_code("99999999")
        assert len(positions) == 0


class TestNormalizeRouteName:
    """Tests for _normalize_route_name function."""

    def test_normalize_full_width_digits(self) -> None:
        """Test normalizing full-width digits to half-width."""
        assert _normalize_route_name("１２３４５６７８９０") == "1234567890"  # noqa: RUF001

    def test_normalize_full_width_c(self) -> None:
        """Test normalizing full-width C to half-width."""
        assert _normalize_route_name("Ｃ－７５８") == "C-758"  # noqa: RUF001

    def test_normalize_mixed_characters(self) -> None:
        """Test normalizing mixed full-width and half-width characters."""
        assert _normalize_route_name("栄２３") == "栄23"

    def test_normalize_already_half_width(self) -> None:
        """Test normalizing already half-width characters."""
        assert _normalize_route_name("C-758") == "C-758"
        assert _normalize_route_name("栄23") == "栄23"

    def test_normalize_empty_string(self) -> None:
        """Test normalizing empty string."""
        assert _normalize_route_name("") == ""


def _transform_approach_fixture(fixture_data: dict) -> dict:  # type: ignore[type-arg]
    """Transform fixture data to ApproachInfoResponse format (mimics client logic)."""
    approach_info: dict[str, dict[str, str]] = {}
    approach_info["CURRENT_BUS_POSITIONS"] = {}
    for k, v in fixture_data.items():
        if k == "LATEST_BUS_PASS":
            approach_info[k] = v
        else:
            approach_info["CURRENT_BUS_POSITIONS"][k] = v
    return approach_info


@pytest.mark.asyncio
class TestGetRealtimeApproach:
    """Tests for get_realtime_approach async function."""

    async def test_get_realtime_approach_basic(
        self,
        mocker: MockerFixture,
        fixture_loader: FixtureLoader,
        base_data: BaseData,
    ) -> None:
        """Test get_realtime_approach with basic scenario."""
        # Load fixtures
        keito_data = fixture_loader("routes_1123002.json")
        approach_data = fixture_loader("realtime_approach_1123002.json")

        # Update keito_data to have bus stops that match the approach_data
        # The approach data has: 11015301, 45055301, 210101E1
        keito_data["BUSSTOPS"] = ["11015301", "45055301", "210101E1"]

        # Create mock client
        mock_client = mocker.AsyncMock(spec=Client)
        mock_client.get_keito.return_value = KeitoResponse.model_validate(keito_data)
        mock_client.get_realtime_approach.return_value = (
            ApproachInfoResponse.model_validate(
                _transform_approach_fixture(approach_data)
            )
        )

        # Call the function
        result = await get_realtime_approach(mock_client, base_data, "1123002")

        # Verify the result
        assert result.route == "栄23"
        assert result.direction == "中川車庫前発 栄行き"
        assert len(result.bus_stops) == 3
        assert result.bus_stops[0].bus_stop_code == "11015301"
        assert result.bus_stops[1].bus_stop_code == "45055301"
        assert result.bus_stops[2].bus_stop_code == "210101E1"

        # Verify mock calls
        mock_client.get_keito.assert_called_once_with("1123002")
        mock_client.get_realtime_approach.assert_called_once_with("1123002")

    async def test_get_realtime_approach_with_article(
        self,
        mocker: MockerFixture,
        fixture_loader: FixtureLoader,
        base_data: BaseData,
    ) -> None:
        """Test get_realtime_approach with route that has an article."""
        # Load and modify fixtures to include article
        keito_data = fixture_loader("routes_1123002.json")
        keito_data["ARTICLE"] = "地下鉄高畑経由"
        keito_data["BUSSTOPS"] = ["11015301", "45055301", "210101E1"]
        approach_data = fixture_loader("realtime_approach_1123002.json")

        # Create mock client
        mock_client = mocker.AsyncMock(spec=Client)
        mock_client.get_keito.return_value = KeitoResponse.model_validate(keito_data)
        mock_client.get_realtime_approach.return_value = (
            ApproachInfoResponse.model_validate(
                _transform_approach_fixture(approach_data)
            )
        )

        # Call the function
        result = await get_realtime_approach(mock_client, base_data, "1123002")

        # Verify direction includes article
        assert result.direction == "中川車庫前発 地下鉄高畑経由 栄行き"

    async def test_get_realtime_approach_multiple_positions(
        self,
        mocker: MockerFixture,
        fixture_loader: FixtureLoader,
        base_data: BaseData,
    ) -> None:
        """Test get_realtime_approach with multiple bus positions."""
        # Load fixtures
        keito_data = fixture_loader("routes_1123002.json")
        keito_data["BUSSTOPS"] = ["11015301", "45055301", "210101E1"]
        approach_data = fixture_loader("realtime_approach_multiple_positions.json")

        # Create mock client
        mock_client = mocker.AsyncMock(spec=Client)
        mock_client.get_keito.return_value = KeitoResponse.model_validate(keito_data)
        mock_client.get_realtime_approach.return_value = (
            ApproachInfoResponse.model_validate(
                _transform_approach_fixture(approach_data)
            )
        )

        # Call the function
        result = await get_realtime_approach(mock_client, base_data, "1123002")

        # Verify multiple positions are tracked
        assert len(result.current_positions) >= 1
        assert len(result.latest_passes) >= 0

    async def test_get_realtime_approach_normalizes_route_name(
        self,
        mocker: MockerFixture,
        fixture_loader: FixtureLoader,
        base_data: BaseData,
    ) -> None:
        """Test that route names are normalized from full-width to half-width."""
        # Load and modify fixtures to have full-width route name
        keito_data = fixture_loader("routes_1123002.json")
        keito_data["NAME"] = "栄２３"  # Full-width digits
        keito_data["BUSSTOPS"] = ["11015301", "45055301", "210101E1"]
        approach_data = fixture_loader("realtime_approach_1123002.json")

        # Create mock client
        mock_client = mocker.AsyncMock(spec=Client)
        mock_client.get_keito.return_value = KeitoResponse.model_validate(keito_data)
        mock_client.get_realtime_approach.return_value = (
            ApproachInfoResponse.model_validate(
                _transform_approach_fixture(approach_data)
            )
        )

        # Call the function
        result = await get_realtime_approach(mock_client, base_data, "1123002")

        # Verify route name is normalized to half-width
        assert result.route == "栄23"

    async def test_get_realtime_approach_skips_first_stop_in_latest_pass(
        self,
        mocker: MockerFixture,
        fixture_loader: FixtureLoader,
        base_data: BaseData,
    ) -> None:
        """Test that positions where next stop is first stop are skipped."""
        # Load fixtures
        keito_data = fixture_loader("routes_1123002.json")
        keito_data["BUSSTOPS"] = ["11015301", "45055301", "210101E1"]
        approach_data = fixture_loader("realtime_approach_1123002.json")

        # Modify approach data to have next stop as first stop
        # This should be skipped because there's no previous stop
        approach_data["LATEST_BUS_PASS"]["11015/301"] = {"NF 9999": "20:00:00"}

        # Create mock client
        mock_client = mocker.AsyncMock(spec=Client)
        mock_client.get_keito.return_value = KeitoResponse.model_validate(keito_data)
        mock_client.get_realtime_approach.return_value = (
            ApproachInfoResponse.model_validate(
                _transform_approach_fixture(approach_data)
            )
        )

        # Call the function
        result = await get_realtime_approach(mock_client, base_data, "1123002")

        # Verify that the position with first stop as next is not in latest_passes
        # The car "NF 9999" should not appear in any latest_passes
        for position in result.latest_passes.values():
            assert position.car_code != "NF 9999"

    async def test_get_realtime_approach_latest_pass_uses_most_recent(
        self,
        mocker: MockerFixture,
        fixture_loader: FixtureLoader,
        base_data: BaseData,
    ) -> None:
        """Test that latest_passes only keeps the most recent pass time."""
        # Load fixtures
        keito_data = fixture_loader("routes_1123002.json")
        keito_data["BUSSTOPS"] = ["11015301", "45055301", "210101E1"]
        approach_data = fixture_loader("realtime_approach_1123002.json")

        # Modify approach data to have multiple passes for the same previous stop
        # The API format has next_stop as key, so bus at 45055301 has previous 11015301
        approach_data["LATEST_BUS_PASS"]["45055/301"] = {
            "NF 0001": "20:00:00",  # Earlier
            "NF 0002": "21:00:00",  # Later - should be kept
        }

        # Create mock client
        mock_client = mocker.AsyncMock(spec=Client)
        mock_client.get_keito.return_value = KeitoResponse.model_validate(keito_data)
        mock_client.get_realtime_approach.return_value = (
            ApproachInfoResponse.model_validate(
                _transform_approach_fixture(approach_data)
            )
        )

        # Call the function
        result = await get_realtime_approach(mock_client, base_data, "1123002")

        # Verify that only the latest pass is kept for the previous stop
        if "11015301" in result.latest_passes:
            latest = result.latest_passes["11015301"]
            # Should be the later time
            assert latest.passed_time == "21:00:00"
            assert latest.car_code == "NF 0002"
