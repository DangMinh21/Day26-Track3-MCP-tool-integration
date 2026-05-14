"""Integration tests for MCP resources."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastmcp import Client
from mcp.shared.exceptions import McpError


def _run(coro):
    return asyncio.run(coro)


def test_static_resource_discoverable(mcp_server):
    async def _go():
        async with Client(mcp_server) as c:
            return await c.list_resources()

    items = _run(_go())
    uris = [str(r.uri) for r in items]
    assert "schema://database" in uris


def test_template_resource_discoverable(mcp_server):
    async def _go():
        async with Client(mcp_server) as c:
            return await c.list_resource_templates()

    items = _run(_go())
    templates = [r.uriTemplate for r in items]
    assert "schema://table/{table_name}" in templates


def test_read_database_schema(mcp_server):
    async def _go():
        async with Client(mcp_server) as c:
            return await c.read_resource("schema://database")

    result = _run(_go())
    payload = json.loads(result[0].text)
    assert set(payload["tables"].keys()) == {"students", "courses", "enrollments"}


def test_read_table_schema(mcp_server):
    async def _go():
        async with Client(mcp_server) as c:
            return await c.read_resource("schema://table/students")

    result = _run(_go())
    payload = json.loads(result[0].text)
    assert payload["table"] == "students"
    assert payload["primary_key"] == "id"


def test_read_unknown_table_raises(mcp_server):
    async def _go():
        async with Client(mcp_server) as c:
            return await c.read_resource("schema://table/ghost")

    with pytest.raises(McpError, match="Unknown table 'ghost'"):
        _run(_go())
