"""FastMCP server exposing the SQLite lab database.

Tools:
- search:    query rows with filters / ordering / pagination
- insert:    add a row to a table
- aggregate: count / avg / sum / min / max, optionally grouped

Resources are added in Step 7. Bonus HTTP/auth transport in Step 10.

Run (stdio for Claude Code / Inspector):

    python implementation/mcp_server.py
"""

from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP

from db import SQLiteAdapter, ValidationError

mcp = FastMCP("SQLite Lab MCP Server")
adapter = SQLiteAdapter()


@mcp.tool
def search(
    table: str,
    filters: list[dict] | None = None,
    columns: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str | None = None,
    descending: bool = False,
) -> dict[str, Any]:
    """Search rows in a table.

    Args:
        table: target table name (e.g. 'students').
        filters: optional list of {"column": str, "op": str, "value": any}.
            Supported ops: eq, neq, gt, gte, lt, lte, like, in.
            For op="in", value must be a non-empty list.
        columns: optional projection list. Defaults to all columns.
        limit: max rows to return (1-100, default 20).
        offset: pagination offset (default 0).
        order_by: column to ORDER BY.
        descending: reverse ordering when True.

    Returns:
        {"table": str, "count": int, "rows": [...], "limit": int, "offset": int}
    """
    return adapter.search(
        table=table,
        filters=filters,
        columns=columns,
        limit=limit,
        offset=offset,
        order_by=order_by,
        descending=descending,
    )


@mcp.tool
def insert(table: str, values: dict[str, Any]) -> dict[str, Any]:
    """Insert a single row.

    Args:
        table: target table name.
        values: column → value mapping. All columns must exist on the table.
            Server-side defaults (e.g. created_at) are filled automatically.

    Returns:
        {"table": str, "inserted_id": int, "values": {...full row...}}
    """
    return adapter.insert(table=table, values=values)


@mcp.tool
def aggregate(
    table: str,
    metric: str,
    column: str | None = None,
    filters: list[dict] | None = None,
    group_by: str | None = None,
) -> dict[str, Any]:
    """Compute an aggregate metric.

    Args:
        table: target table name.
        metric: one of "count", "avg", "sum", "min", "max".
        column: required for avg/sum/min/max. For count, pass None or "*"
            to count all rows, or a column name to count non-null values.
        filters: optional list of filter dicts (same shape as search).
        group_by: optional column to GROUP BY.

    Returns:
        {"table": str, "metric": str, "column": str|None, "group_by": str|None,
         "rows": [{"group": value|None, "value": number}]}
    """
    return adapter.aggregate(
        table=table,
        metric=metric,
        column=column,
        filters=filters,
        group_by=group_by,
    )


@mcp.resource("schema://database", mime_type="application/json")
def database_schema() -> str:
    """Snapshot of every table in the database, as JSON."""
    payload = {
        "tables": {t: adapter.get_table_schema(t) for t in adapter.list_tables()}
    }
    return json.dumps(payload, indent=2)


@mcp.resource("schema://table/{table_name}", mime_type="application/json")
def table_schema(table_name: str) -> str:
    """Schema for a single table, identified by URI segment."""
    return json.dumps(adapter.get_table_schema(table_name), indent=2)


def _run_cli() -> None:
    import argparse
    import os

    parser = argparse.ArgumentParser(description="SQLite Lab MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="MCP transport to use (default: stdio).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host (http only).")
    parser.add_argument("--port", type=int, default=8765, help="HTTP port (http only).")
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run()
        return

    # HTTP transport: bonus task. Require MCP_AUTH_TOKEN.
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    token = os.getenv("MCP_AUTH_TOKEN")
    if not token:
        raise SystemExit(
            "MCP_AUTH_TOKEN is required for --transport http. "
            "Copy .env.example to .env or export the variable."
        )

    import uvicorn

    from auth import build_http_app

    app = build_http_app(mcp, token=token)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    _run_cli()
