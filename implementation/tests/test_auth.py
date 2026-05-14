"""Tests for the bonus HTTP transport with Bearer auth."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from auth import build_http_app


TOKEN = "test-token-123"


def _post(app, headers: dict[str, str] | None = None):
    async def _go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            # FastMCP's HTTP transport mounts at /mcp/ by default in v3.
            return await client.post(
                "/mcp/",
                headers=headers or {},
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
            )

    return asyncio.run(_go())


def test_missing_header_returns_401(mcp_server):
    app = build_http_app(mcp_server, token=TOKEN)
    resp = _post(app)
    assert resp.status_code == 401
    assert resp.json()["error"] == "unauthorized"


def test_wrong_token_returns_401(mcp_server):
    app = build_http_app(mcp_server, token=TOKEN)
    resp = _post(app, headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


def test_correct_token_passes_auth(mcp_server):
    app = build_http_app(mcp_server, token=TOKEN)
    resp = _post(app, headers={"Authorization": f"Bearer {TOKEN}"})
    # The middleware should pass auth; the underlying MCP handshake may
    # still reject the body shape (this is fine — we only assert it is
    # NOT a 401 from our middleware).
    assert resp.status_code != 401


def test_empty_token_rejected_at_build_time(mcp_server):
    with pytest.raises(ValueError, match="non-empty string"):
        build_http_app(mcp_server, token="")
