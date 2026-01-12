"""Type definitions for tests."""

from collections.abc import Callable
from typing import Any

FixtureLoader = Callable[[str], Any]
