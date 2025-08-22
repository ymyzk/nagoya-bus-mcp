# nagoya-bus-mcp

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

## Manual
```shell
$ uvx nagoya_bus_mcp
```
