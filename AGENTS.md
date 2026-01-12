# AGENTS.md

This file provides guidance to AI Coding Agent such as Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Model Context Protocol (MCP) server providing tools to query Nagoya City bus timetables. Built using FastMCP, it exposes MCP tools and prompts that allow LLMs to interact with the Nagoya City bus API.

## Development Commands

### Setup
```bash
# Install dependencies
uv sync

# Install pre-commit hooks
uv run pre-commit install
```

### Testing
```bash
# Run all tests (excluding integration tests)
uv run pytest

# Run integration tests
uv run pytest -m integration

# Run specific test file
uv run pytest tests/client_test.py

# Run with coverage
uv run pytest --cov
```

### Linting and Type Checking
```bash
# Run all pre-commit checks
uv run pre-commit run --all-files

# Run type checking
uv run mypy

# Format and lint (via pre-commit hooks: ruff)
uv run pre-commit run ruff-check --all-files
uv run pre-commit run ruff-format --all-files
```

### Running the Server
```bash
# Run with MCP Inspector (recommended for development)
npx @modelcontextprotocol/inspector uv run nagoya-bus-mcp

# Run directly
uv run nagoya-bus-mcp

# Try API client directly
uv run python -m nagoya_bus_mcp.client
```

### Building
```bash
# Build package
uv build
```

## Architecture

### Project Structure

```
nagoya_bus_mcp/
├── __main__.py           # Entry point for the MCP server
├── client.py             # HTTP client for Nagoya Bus API
├── approach.py           # Wrapper and utilities for real-time approach information
├── data.py               # Common base data (stations, poles) with caching
├── mcp/
│   ├── server.py         # FastMCP server initialization and lifespan
│   ├── tools.py          # MCP tool implementations
│   └── prompts.py        # MCP prompt templates
└── version.py            # Auto-generated version file (from setuptools-scm)
```

### Key Components

**API Client (`client.py`)**
- `Client`: Async HTTP client wrapping the Nagoya City bus API
- Uses `httpx.AsyncClient` for all HTTP requests
- Implements context manager protocol for proper resource cleanup
- **Important quirk**: The Nagoya Bus API returns HTML 404 pages with HTTP 200 status. The `_check_404()` method detects this by inspecting content-type and response body.
- All API responses use Pydantic models with `alias_generator=str.upper` for field mapping

**MCP Server (`mcp/server.py`)**
- Uses FastMCP for MCP server implementation
- Lifespan context pattern: Maintains a single `Client` instance and `BaseData` instance shared across all tool calls
- Server is built via `build_mcp_server()` function that accepts a `Settings` object
- Tools and prompts are registered via decorators on the `mcp_server` instance

**MCP Tools (`mcp/tools.py`)**
- Four main tools exposed to MCP clients:
  - `get_station_number`: Fuzzy matching for station names (uses `difflib`)
  - `get_timetable`: Returns formatted timetables by station
  - `get_approach_for_route`: Returns real-time bus approach and position information for a route
  - `get_approach_for_station`: Returns real-time bus approach information for all routes at a station
- Base data caching: Station names and pole information are cached in the `BaseData` instance (initialized at startup) to reduce API calls

**Base Data Management (`data.py`)**
- `BaseData`: Centralized class for managing station and pole information
- Initialized during server startup via `init_base_data()` and stored in lifespan context
- Provides fast lookup methods: `get_station_number()`, `get_station_name()`, `get_pole_name()`, `find_station_number()`
- Uses fuzzy matching with `difflib` for station name searches

**Approach Processing (`approach.py`)**
- `get_realtime_approach()`: Processes real-time bus approach data for a route
- `ApproachInfo`: Model containing route, direction, bus stops, latest passes, and current positions
- Resolves bus stop codes to human-readable station/pole names using `BaseData`
- Used by both `get_approach_for_route` and `get_approach_for_station` tools

**Data Flow**
1. MCP client calls a tool (e.g., `get_timetable`)
2. Tool accesses `Client` instance from `ctx.request_context.lifespan_context.bus_client` and `BaseData` from `ctx.request_context.lifespan_context.base_data`
3. Client makes async HTTP request to Nagoya City bus API
4. Response is validated via Pydantic models
5. Tool transforms and returns data in MCP-friendly format

### Testing Strategy

- Unit tests mock `httpx.AsyncClient` transport to avoid real API calls
- Integration tests (marked with `@pytest.mark.integration`) hit the real API
- Tests use `pytest-asyncio` for async test support
- Type checking enforced via mypy in strict mode

### API Quirks to Know

1. **Fake 404s**: The API returns HTML 404 pages with status 200. Always use `_check_404()` after GET requests for station-specific endpoints.
2. **Field aliases**: All API response models use uppercase field names (e.g., `POLENAME`, `RAILWAY`) but map to lowercase Python attributes.
3. **Route codes vs station numbers**: Station numbers are integers (e.g., `22460`), route codes are strings (e.g., `"1117001"`).

### Code Patterns

- All API client methods are async and should be awaited
- Use the lifespan context to access the shared `Client` and `BaseData` instances in tools via `_get_context_from_context(ctx)`
- Prefer extending existing Pydantic models over manual dict manipulation
- Use `BaseData` methods for station/pole lookups instead of direct API calls when possible
