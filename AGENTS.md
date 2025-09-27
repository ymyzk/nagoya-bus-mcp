# AGENTS.md
This repository provides an MCP (Model Context Protocol) server named "Nagoya Bus MCP" that exposes tools and a prompt to retrieve public bus timetable information for Nagoya City.

## Development Tips
- **Run MCP server**: `uv run nagoya-bus-mcp`
- **Run MCP server with inspector**: `npx @modelcontextprotocol/inspector uv run nagoya-bus-mcp`
- **Run linter and formatter (pre-commit)**: `uv run pre-commit run --all-files`
- **Run type checker**: `uv run mypy`
- **Run all tests**: `uv run pytest`
