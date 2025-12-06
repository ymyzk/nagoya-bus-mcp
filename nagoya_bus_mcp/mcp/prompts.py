"""MCP prompt templates for Nagoya Bus queries."""


def ask_timetable(station_name: str, date: str) -> str:
    """Ask for the timetable of a bus station on a specific date."""
    return f"{station_name}の{date}のバスの時刻表を教えて"


def ask_bus_approach(station_name: str, route_code: str) -> str:
    """Ask for the approach of a bus station on a specific date."""
    return f"{station_name}の{route_code}のバスの到着情報を教えて"
