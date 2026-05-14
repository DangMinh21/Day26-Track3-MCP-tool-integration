"""Bearer token auth for the HTTP transport (bonus task).

Usage:

    from auth import build_http_app
    app = build_http_app(mcp, token="secret")
    uvicorn.run(app, host="127.0.0.1", port=8765)

Clients must send:

    Authorization: Bearer <token>

Missing or wrong tokens get a 401 response before reaching MCP code.
"""

from __future__ import annotations

from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class BearerAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next):
        header = request.headers.get("authorization", "")
        prefix = "Bearer "
        if not header.startswith(prefix) or header[len(prefix):] != self._token:
            return JSONResponse(
                {"error": "unauthorized", "detail": "missing or invalid Bearer token"},
                status_code=401,
            )
        return await call_next(request)


def build_http_app(mcp, token: str):
    """Wrap the FastMCP HTTP app with Bearer auth middleware."""
    if not token:
        raise ValueError("token must be a non-empty string")
    return mcp.http_app(
        middleware=[Middleware(BearerAuthMiddleware, token=token)],
    )
