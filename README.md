# nagoya-bus-mcp
[![PyPI - Version](https://img.shields.io/pypi/v/nagoya-bus-mcp)](https://pypi.org/project/nagoya-bus-mcp/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/nagoya-bus-mcp)](https://pypi.org/project/nagoya-bus-mcp/)
[![CI](https://github.com/ymyzk/nagoya-bus-mcp/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ymyzk/nagoya-bus-mcp/actions/workflows/ci.yml)

## Getting started
The Nagoya Bus MCP server is published to PyPI.

### Claude Desktop
Add the following configuration to `claude_desktop_config.json`.
```json
{
  "mcpServers": {
    "nagoya-bus": {
      "command": "uvx",
      "args": ["nagoya_bus_mcp"]
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
      "args": ["nagoya_bus_mcp"],
      "env": {}
    }
  }
}
```

### Manual
```shell
# Using uvx
$ uvx nagoya_bus_mcp

# Using Docker
$ docker run -i --rm ghcr.io/ymyzk/nagoya-bus-mcp
```
