#!/usr/bin/env bash
# Launch MCP Inspector pointed at this lab's FastMCP server.
#
# Requires: Node.js + npx. The first run downloads the inspector package.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
SERVER="$HERE/mcp_server.py"

if [[ ! -f "$SERVER" ]]; then
    echo "Cannot find $SERVER" >&2
    exit 1
fi

mkdir -p "$HERE/.npm-cache"

echo "Launching MCP Inspector..."
echo "  python : $PYTHON_BIN"
echo "  server : $SERVER"
echo

NPM_CONFIG_CACHE="$HERE/.npm-cache" \
    npx -y @modelcontextprotocol/inspector "$PYTHON_BIN" "$SERVER"
