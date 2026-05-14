"""Integration tests for the three MCP tools via the FastMCP Client."""

from __future__ import annotations

import asyncio

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


def _run(coro):
    return asyncio.run(coro)


def test_three_tools_discovered(mcp_server):
    async def _go():
        async with Client(mcp_server) as c:
            return [t.name for t in await c.list_tools()]

    names = _run(_go())
    assert set(names) == {"search", "insert", "aggregate"}


def test_search_tool_returns_rows(mcp_server):
    async def _go():
        async with Client(mcp_server) as c:
            return await c.call_tool(
                "search",
                {"table": "students", "filters": [{"column": "cohort", "op": "eq", "value": "A1"}]},
            )

    res = _run(_go())
    assert res.structured_content["count"] == 2
    assert {r["name"] for r in res.structured_content["rows"]} == {"Alice Nguyen", "Bob Tran"}


def test_insert_tool_returns_payload(mcp_server):
    async def _go():
        async with Client(mcp_server) as c:
            return await c.call_tool(
                "insert",
                {
                    "table": "courses",
                    "values": {"code": "BIO101", "title": "Biology", "credits": 3},
                },
            )

    res = _run(_go())
    assert res.structured_content["inserted_id"] == 5
    assert res.structured_content["values"]["code"] == "BIO101"


def test_aggregate_tool_with_group_by(mcp_server):
    async def _go():
        async with Client(mcp_server) as c:
            return await c.call_tool(
                "aggregate",
                {
                    "table": "enrollments",
                    "metric": "avg",
                    "column": "score",
                    "group_by": "course_id",
                },
            )

    res = _run(_go())
    assert len(res.structured_content["rows"]) == 4
    assert {r["group"] for r in res.structured_content["rows"]} == {1, 2, 3, 4}


def test_search_tool_unknown_table_clean_error(mcp_server):
    async def _go():
        async with Client(mcp_server) as c:
            return await c.call_tool("search", {"table": "aliens"})

    with pytest.raises(ToolError, match="Unknown table 'aliens'"):
        _run(_go())
