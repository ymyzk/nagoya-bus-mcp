"""Unit tests for the data module."""

import pytest

from nagoya_bus_mcp.client import (
    BusStopPoleInfoResponse,
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


def test_get_pole_name_found(base_data: BaseData) -> None:
    """Test retrieving a pole name that exists."""
    # Using data from buspole_infos.json fixture
    pole_name = base_data.get_pole_name("01110301")
    assert pole_name == "1番"

    pole_name = base_data.get_pole_name("75030701")
    assert pole_name == "2番"

    pole_name = base_data.get_pole_name("711455W1")
    assert pole_name == "5番"


def test_get_pole_name_not_found(base_data: BaseData) -> None:
    """Test retrieving a pole name that doesn't exist."""
    pole_name = base_data.get_pole_name("nonexistent")
    assert pole_name is None

    pole_name = base_data.get_pole_name("99999999")
    assert pole_name is None


def test_get_station_number_found(base_data: BaseData) -> None:
    """Test retrieving a station number that exists."""
    # Using data from station_name.json fixture
    station_number = base_data.get_station_number("名古屋駅")
    assert station_number == 41200

    station_number = base_data.get_station_number("栄")
    assert station_number == 21010


def test_get_station_number_not_found(base_data: BaseData) -> None:
    """Test retrieving a station number that doesn't exist."""
    station_number = base_data.get_station_number("nonexistent")
    assert station_number is None

    station_number = base_data.get_station_number("不明な駅")
    assert station_number is None


def test_get_station_name_found(base_data: BaseData) -> None:
    """Test retrieving a station name that exists."""
    # Using data from station_name.json fixture
    station_name = base_data.get_station_name(41200)
    assert station_name == "名古屋駅"

    station_name = base_data.get_station_name(21010)
    assert station_name == "栄"


def test_get_station_name_not_found(base_data: BaseData) -> None:
    """Test retrieving a station name that doesn't exist."""
    station_name = base_data.get_station_name(99999)
    assert station_name is None

    station_name = base_data.get_station_name(12345)
    assert station_name is None


def test_station_lookups_are_bidirectional(base_data: BaseData) -> None:
    """Test that station name and number lookups work bidirectionally."""
    # Test name -> number -> name roundtrip
    original_name = "名古屋駅"
    station_number = base_data.get_station_number(original_name)
    assert station_number is not None
    retrieved_name = base_data.get_station_name(station_number)
    assert retrieved_name == original_name

    # Test number -> name -> number roundtrip
    original_number = 21010
    station_name = base_data.get_station_name(original_number)
    assert station_name is not None
    retrieved_number = base_data.get_station_number(station_name)
    assert retrieved_number == original_number


def test_find_station_number_exact_match(base_data: BaseData) -> None:
    """Test fuzzy matching with exact match (should return immediately)."""
    station_number = base_data.find_station_number("名古屋駅")
    assert station_number == 41200

    station_number = base_data.find_station_number("栄")
    assert station_number == 21010


def test_find_station_number_fuzzy_match(base_data: BaseData) -> None:
    """Test fuzzy matching with similar but not exact match."""
    # This test assumes that slight misspellings will be caught by fuzzy matching
    # The exact behavior depends on the data in the fixtures
    # If "名古屋" is similar enough to "名古屋駅", it should match
    station_number = base_data.find_station_number("名古屋", cutoff=0.6)
    assert station_number == 41200


def test_find_station_number_no_match(base_data: BaseData) -> None:
    """Test fuzzy matching with no match."""
    station_number = base_data.find_station_number("completely_nonexistent_station")
    assert station_number is None


def test_find_station_number_with_custom_cutoff(base_data: BaseData) -> None:
    """Test fuzzy matching with custom cutoff threshold."""
    # With a very high cutoff (0.99), fewer fuzzy matches should succeed
    station_number = base_data.find_station_number("名古屋", cutoff=0.99)
    assert station_number is None

    # With a very low cutoff (0.1), more fuzzy matches should succeed
    station_number = base_data.find_station_number("名古屋", cutoff=0.1)
    assert station_number == 41200


def test_base_data_with_empty_poles() -> None:
    """Test BaseData initialization with empty pole information."""
    empty_poles = BusStopPoleInfoResponse.model_validate({})
    sample_stations = StationNamesResponse.model_validate({"Test Station": 12345})

    base_data = BaseData(empty_poles, sample_stations)

    # Should handle empty poles gracefully
    pole_name = base_data.get_pole_name("any_code")
    assert pole_name is None


def test_base_data_with_empty_stations() -> None:
    """Test BaseData initialization with empty station information."""
    sample_poles = BusStopPoleInfoResponse.model_validate(
        {"01110301": {"BC": "301", "C": "301", "N": "1番"}}
    )
    empty_stations = StationNamesResponse.model_validate({})

    base_data = BaseData(sample_poles, empty_stations)

    # Should handle empty stations gracefully
    # Test individual lookups
    assert base_data.get_station_number("any_name") is None
    assert base_data.get_station_name(12345) is None
    assert base_data.find_station_number("any_name") is None


def test_base_data_pole_names_mapping() -> None:
    """Test that pole names are correctly extracted from BusStopPoleInfo."""
    poles_data = {
        "code1": {"BC": "bc1", "C": "c1", "N": "Pole 1"},
        "code2": {"BC": "bc2", "C": "c2", "N": "Pole 2"},
        "code3": {"BC": "bc3", "C": "c3", "N": "Pole 3"},
    }
    poles = BusStopPoleInfoResponse.model_validate(poles_data)
    stations = StationNamesResponse.model_validate({})

    base_data = BaseData(poles, stations)

    # Verify all poles are mapped correctly
    assert base_data.get_pole_name("code1") == "Pole 1"
    assert base_data.get_pole_name("code2") == "Pole 2"
    assert base_data.get_pole_name("code3") == "Pole 3"
