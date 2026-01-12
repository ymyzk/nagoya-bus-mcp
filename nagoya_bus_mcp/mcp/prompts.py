"""MCP prompt templates for Nagoya Bus queries."""


def ask_timetable(station_name: str, date: str) -> str:
    """Ask for the timetable of a bus station on a specific date."""
    return f"{station_name}の{date}のバスの時刻表を教えて"


def ask_bus_approach(station_name: str) -> str:
    """Ask for the bus approach information at a bus station."""
    return f"{station_name}のバスの接近情報を教えて"
