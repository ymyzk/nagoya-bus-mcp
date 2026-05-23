# nagoya-bus-mcp
[![PyPI - Version](https://img.shields.io/pypi/v/nagoya-bus-mcp)](https://pypi.org/project/nagoya-bus-mcp/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/nagoya-bus-mcp)](https://pypi.org/project/nagoya-bus-mcp/)
[![CI](https://github.com/ymyzk/nagoya-bus-mcp/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ymyzk/nagoya-bus-mcp/actions/workflows/ci.yml)

[English](README.md) | **日本語**

## 概要
Nagoya Bus MCP は、LLM から名古屋市営バスの情報を問い合わせるための [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) サーバーです。[FastMCP](https://gofastmcp.com/) を利用して構築されており、バス停の検索・時刻表の取得・バスの接近情報や位置情報の確認といったツールやプロンプトを提供します。データは名古屋市営バスの公開ウェブサイトを参照しています。

Claude Desktop などの MCP クライアントに接続すると、「名古屋駅の次のバスは何時？」のように自然言語で質問するだけで、最新のデータに基づいた回答が得られます。

## 機能
このサーバーは次のツールを提供します。

- **`get_station_number`** — バス停名からバス停番号を検索します（あいまい検索に対応）。
- **`get_timetable`** — バス停のすべての系統について、曜日別の発車時刻表を取得します。
- **`get_approach_for_route`** — 系統上のバスのリアルタイムな位置と直近の通過時刻を取得します。
- **`get_approach_for_station`** — バス停のすべての系統について、接近中のバスのリアルタイム情報を取得します。

また、よくある質問のためのプロンプトテンプレート `ask_timetable` と `ask_bus_approach` も提供します。

## 質問の例
バスのデータは日本語のため、日本語での質問が最も適しています。

- 「名古屋駅のバスの時刻表を教えて」
- 「栄のバスの接近情報を教えて」
- 「新栄町のバス停番号を教えて」

## はじめに
Nagoya Bus MCP サーバーは PyPI で公開されています。

### Claude Desktop
`claude_desktop_config.json` に次の設定を追加します。
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
`.vscode/mcp.json` に次の設定を追加します。
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

### 手動で実行する
```shell
# uvx を使う場合
$ uvx nagoya-bus-mcp

# Docker を使う場合
$ docker run -i --rm ghcr.io/ymyzk/nagoya-bus-mcp
```

## 開発者向け
```
# MCP Inspector を使う
$ npx @modelcontextprotocol/inspector uv run nagoya-bus-mcp

# API クライアントを試す
$ uv run python -m nagoya_bus_mcp.client
```

## データの出典
このプロジェクトは名古屋市営バスの公開ウェブサイト (<https://www.kotsu.city.nagoya.jp>) を参照しています。
非公式のプロジェクトであり、名古屋市が運営・公認するものではありません。
