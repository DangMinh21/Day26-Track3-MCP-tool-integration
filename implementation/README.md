# SQLite Lab MCP Server — Implementation

FastMCP server exposing a small SQLite database (`students` / `courses` /
`enrollments`) through three MCP tools and two MCP resources, with optional
HTTP transport guarded by a Bearer token.

## Layout

```
implementation/
├── db.py                   # SQLiteAdapter + validators
├── init_db.py              # schema + seed
├── mcp_server.py           # FastMCP server (stdio + http)
├── auth.py                 # Bearer auth middleware (bonus)
├── requirements.txt
├── start_inspector.sh      # launch MCP Inspector
├── .env.example            # template for HTTP transport
└── tests/
    ├── conftest.py
    ├── test_adapter.py     # 26 adapter unit tests
    ├── test_tools.py       # 5 FastMCP Client tests
    ├── test_resources.py   # 5 resource tests
    └── test_auth.py        # 4 Bearer auth tests
```

## Setup

```bash
cd implementation
python3 -m pip install -r requirements.txt
python3 init_db.py
```

The init script creates `lab.db` next to the source files and prints row counts.
Re-running it resets the database to the seed state.

## Run the server (stdio, default)

```bash
python3 mcp_server.py
```

This is the transport every MCP client uses by default (Claude Code, Codex,
Gemini CLI, Inspector).

## Run the tests

```bash
python3 -m pytest tests/ -v
# 40 passed
```

## Tools

| Tool        | Purpose                                                  |
|-------------|----------------------------------------------------------|
| `search`    | Read rows with filters (`eq/neq/gt/gte/lt/lte/like/in`), `order_by`, `limit`, `offset`. |
| `insert`    | Insert one row, returns the persisted payload including server-side defaults. |
| `aggregate` | `count`/`avg`/`sum`/`min`/`max`, with optional filters and `group_by`. |

Invalid input (unknown table/column/op/metric, empty insert, oversized limit,
DB constraint violation) is surfaced as a clean `ToolError`/`McpError` with an
actionable message — no stack traces leak to the client.

## Resources

| URI                              | Type            | Content                                          |
|----------------------------------|-----------------|--------------------------------------------------|
| `schema://database`              | static          | JSON snapshot of every table in the database.    |
| `schema://table/{table_name}`    | template        | JSON schema for a single table.                  |

## Connect Claude Code

The repo ships a `.mcp.json` at the project root pointing at this server. Open
the project in Claude Code and the `sqlite-lab` server is auto-discovered.

If the paths in `.mcp.json` don't match your machine, regenerate them:

```bash
python3 - <<'PY'
import json, sys, shutil, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
cfg = {
    "mcpServers": {
        "sqlite-lab": {
            "type": "stdio",
            "command": shutil.which("python3"),
            "args": [str(root / "implementation" / "mcp_server.py")],
            "env": {},
        }
    }
}
print(json.dumps(cfg, indent=2))
PY
```

### Demo prompts in Claude Code

- `@sqlite-lab:schema://database` — read full schema
- `@sqlite-lab:schema://table/enrollments` — read one table schema
- *"Use sqlite-lab to list all students in cohort A1."*
- *"Use sqlite-lab to compute the average score per course."*
- *"Use sqlite-lab to insert a new student named Ivan, cohort B1, email ivan@example.com."*
- *"Use sqlite-lab to search a missing table 'aliens' — show me the error."*

## MCP Inspector

The Inspector is the easiest way to verify tool discovery and to capture demo
screenshots.

```bash
./start_inspector.sh
```

The script downloads `@modelcontextprotocol/inspector` on first run, points it
at `mcp_server.py`, then opens a browser tab. Suggested screenshots:

1. The three tools listed with their schemas.
2. A successful `search` call returning rows.
3. A failing `search` call (e.g. `table: aliens`) showing the error message.
4. The two resources discoverable.
5. The body of `schema://database`.

Save screenshots into `../screenshots/` so they ship with the submission.

## Bonus: HTTP transport with Bearer auth

```bash
cp .env.example .env          # then edit MCP_AUTH_TOKEN
python3 mcp_server.py --transport http --port 8765
```

The server reads `MCP_AUTH_TOKEN` from the environment (or `.env`) and rejects
any request whose `Authorization: Bearer <token>` header doesn't match.

Smoke check with curl:

```bash
# missing header → 401
curl -i -X POST http://127.0.0.1:8765/mcp/

# wrong token → 401
curl -i -X POST http://127.0.0.1:8765/mcp/ -H "Authorization: Bearer wrong"

# correct token → MCP handshake proceeds (307 + standard streamable-http)
curl -i -X POST http://127.0.0.1:8765/mcp/ -H "Authorization: Bearer devtoken123"
```

## Troubleshooting

- **`ModuleNotFoundError: fastmcp`** — run `pip install -r requirements.txt`
  with the same Python interpreter the server launches with.
- **`Database created at ...` but Inspector still 0 rows** — Inspector uses
  the server's working directory; the adapter resolves `lab.db` relative to
  `db.py`, so this should be consistent. If you moved files, re-run
  `python3 init_db.py`.
- **HTTP 401 with correct token** — make sure `MCP_AUTH_TOKEN` is set in the
  environment the server actually sees. `echo $MCP_AUTH_TOKEN` before launch.
- **Inspector cannot run** — Node.js is required for `npx`. Install it or use
  `pytest` + Claude Code as the verification path.
