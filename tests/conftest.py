"""Shared test fixtures."""

import json
from pathlib import Path
from typing import Any

import pytest

from tests.types import FixtureLoader

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def fixture_loader() -> FixtureLoader:
    def _fixture_loader(name: str) -> Any:  # noqa: ANN401
        fixture_path = FIXTURE_DIR / name
        with fixture_path.open("rb") as f:
            return json.load(f)

    return _fixture_loader
