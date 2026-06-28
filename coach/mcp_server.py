"""
mcp_server.py — MCP server exposing the garmin-analytics database to AI clients.

Exposes three tools over stdio so Claude Desktop / Claude Code can answer
ad-hoc coaching questions using live data from the local SQLite database.

Tools:
  query_sql        — run a read-only SELECT query, returns JSON rows
  training_summary — return the full CoachSummary as structured JSON
  goal_progress    — return the sub-60 10K projection

Claude Desktop configuration (add to claude_desktop_config.json):
    {
      "mcpServers": {
        "garmin-analytics": {
          "command": "python",
          "args": ["-m", "coach.mcp_server"],
          "cwd": "C:/Users/kitti/garmin-analytics"
        }
      }
    }

Claude Code configuration (add to .claude/settings.json in this repo):
    {
      "mcpServers": {
        "garmin-analytics": {
          "command": "python",
          "args": ["-m", "coach.mcp_server"]
        }
      }
    }
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from .features import _conn, sub60_projection, summary_as_dict

DB_PATH = Path(__file__).parents[1] / "data" / "db" / "garmin.sqlite"

app = Server("garmin-analytics")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="query_sql",
            description=(
                "Run a read-only SQL SELECT query against the garmin-analytics SQLite database. "
                "Tables: activities, activity_laps, daily_summary, sleep, hrv, training, "
                "personal_records, sync_log. All dates are ISO YYYY-MM-DD strings. "
                "Only SELECT statements are allowed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "A read-only SELECT statement",
                    },
                },
                "required": ["sql"],
            },
        ),
        types.Tool(
            name="training_summary",
            description=(
                "Return a structured JSON summary of the athlete's training over the last 7/28 days: "
                "recent runs, weekly km, acute:chronic load ratio, pace trend, VO2max trend, "
                "avg sleep score, avg HRV, resting HR, recovery status, and sub-60 10K projection."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "as_of": {
                        "type": "string",
                        "description": "Reference date YYYY-MM-DD (defaults to today)",
                    },
                },
            },
        ),
        types.Tool(
            name="goal_progress",
            description=(
                "Return the sub-60 10K projection based on the most recent qualifying run "
                "(Riegel formula). Includes predicted pace (min/km), predicted finish time (min), "
                "gap to the 60-minute goal, and whether the goal is within reach today."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "query_sql":
        sql = (arguments.get("sql") or "").strip()
        if not sql.upper().startswith("SELECT"):
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": "Only SELECT queries are allowed"}),
            )]
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = [dict(r) for r in conn.execute(sql).fetchall()]
            conn.close()
            return [types.TextContent(
                type="text",
                text=json.dumps(rows, default=str, indent=2),
            )]
        except Exception as exc:
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": str(exc)}),
            )]

    elif name == "training_summary":
        as_of = arguments.get("as_of")
        try:
            summary = summary_as_dict(as_of)
            return [types.TextContent(
                type="text",
                text=json.dumps(summary, default=str, indent=2),
            )]
        except Exception as exc:
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": str(exc)}),
            )]

    elif name == "goal_progress":
        try:
            conn = _conn()
            proj = sub60_projection(conn)
            conn.close()
            return [types.TextContent(
                type="text",
                text=json.dumps(proj, default=str, indent=2),
            )]
        except Exception as exc:
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": str(exc)}),
            )]

    return [types.TextContent(
        type="text",
        text=json.dumps({"error": f"Unknown tool: {name}"}),
    )]


async def _main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_main())
