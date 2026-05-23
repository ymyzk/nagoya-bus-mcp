# nagoya-bus-mcp
[![PyPI - Version](https://img.shields.io/pypi/v/nagoya-bus-mcp)](https://pypi.org/project/nagoya-bus-mcp/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/nagoya-bus-mcp)](https://pypi.org/project/nagoya-bus-mcp/)
[![CI](https://github.com/ymyzk/nagoya-bus-mcp/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ymyzk/nagoya-bus-mcp/actions/workflows/ci.yml)

**English** | [日本語](README.ja.md)

## Overview
Nagoya Bus MCP is a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that lets LLMs query Nagoya City bus information. Built with [FastMCP](https://gofastmcp.com/), it exposes tools and prompts for looking up bus stops, reading timetables, and checking real-time bus approach and position information. Data is sourced from the public Nagoya City bus website.

Once connected to an MCP client such as Claude Desktop, you can ask questions like "When is the next bus from Nagoya Station?" in natural language and get answers backed by live data.

## Features
The server exposes the following tools:

- **`get_station_number`** — find a bus stop number from a stop name (with fuzzy matching).
- **`get_timetable`** — departure timetables for every route at a bus stop, organized by day of week.
- **`get_approach_for_route`** — real-time bus positions and latest passage times along a route.
- **`get_approach_for_station`** — real-time approaching buses for all routes at a bus stop.

It also provides prompt templates `ask_timetable` and `ask_bus_approach` for common questions.

## Example queries
Bus data is in Japanese, so queries work best in Japanese:

- 「名古屋駅のバスの時刻表を教えて」 (What's the bus timetable at Nagoya Station?)
- 「栄のバスの接近情報を教えて」 (Show real-time bus approach info at Sakae.)
- 「新栄町のバス停番号を教えて」 (What's the bus stop number for Shin-sakaemachi?)

## Getting started
The Nagoya Bus MCP server is published to PyPI.

### Claude Desktop
Add the following configuration to `claude_desktop_config.json`.
```json
{
  "mcpServers": {
    "nagoya-bus": {
      "command": "uvx",
      "args": ["nagoya-bus-mcp"]
    }
  }
}
```

### Visual Studio Code
Add the following configuration to `.vscode/mcp.json`.
```json
{
  "servers": {
    "nagoya-bus": {
      "type": "stdio",
      "command": "uvx",
      "args": ["nagoya-bus-mcp"],
      "env": {}
    }
  }
}
```

### Manual
```shell
# Using uvx
$ uvx nagoya-bus-mcp

# Using Docker
$ docker run -i --rm ghcr.io/ymyzk/nagoya-bus-mcp
```

## For developers
```
# Use MCP Inspector
$ npx @modelcontextprotocol/inspector uv run nagoya-bus-mcp

# Try API client
$ uv run python -m nagoya_bus_mcp.client
```

## Data source
This project queries the public Nagoya City bus website (<https://www.kotsu.city.nagoya.jp>).
It is an unofficial project and is not affiliated with or endorsed by the City of Nagoya.
