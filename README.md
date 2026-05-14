# Day 26 — Track 3: MCP Tool Integration

**Học viên**: Đặng Văn Minh
**MSHV**: 2A202600027
**Bài**: Build a Database MCP Server with FastMCP and SQLite

---

## Tổng quan

Bài nộp này xây dựng một **MCP server** dùng [FastMCP](https://gofastmcp.com) v3 expose một SQLite database (`students` / `courses` / `enrollments`) qua chuẩn Model Context Protocol. Server cung cấp:

- **3 tools**: `search`, `insert`, `aggregate` — đầy đủ filter / ordering / pagination / 5 metric aggregate / group_by
- **2 resources**: `schema://database` (full schema) + `schema://table/{table_name}` (template, per-table)
- **Validation an toàn**: whitelist identifier (table/column/operator/metric) + parameterized SQL → chống SQL injection
- **40 pytest tests** xanh (26 unit + 5 client + 5 resource + 4 auth)
- **Bonus**: HTTP/Streamable-HTTP transport có Bearer-token auth

Client target chính: **Claude Code** (stdio). Cũng tương thích Codex, Gemini CLI, MCP Inspector.

---

## Cấu trúc repo

```text
Day26-Track3-MCP-tool-integration/
├── README.md                       # ← file này (cho người chấm)
├── Rubric.md                       # tiêu chí chấm (do giảng viên cung cấp)
├── Tips.md                         # gợi ý của giảng viên về client setup
├── .mcp.json                       # config Claude Code (auto-discover)
├── docs/
│   └── spec.md                     # design spec đầy đủ (13 sections)
├── pseudocode/                     # skeleton gốc của lab (tham khảo)
└── implementation/                 # CODE NỘP — toàn bộ ở đây
    ├── README.md                   # hướng dẫn chi tiết cho người dev
    ├── db.py                       # SQLiteAdapter + validation
    ├── init_db.py                  # tạo schema + seed data
    ├── mcp_server.py               # FastMCP server (stdio + http)
    ├── auth.py                     # Bearer auth middleware (bonus)
    ├── requirements.txt
    ├── start_inspector.sh          # script chạy MCP Inspector
    ├── .env.example                # template env cho bonus auth
    └── tests/
        ├── conftest.py             # fixtures (tmp_path → fresh DB per test)
        ├── test_adapter.py         # 26 unit tests cho SQLiteAdapter
        ├── test_tools.py           # 5 integration tests qua FastMCP Client
        ├── test_resources.py       # 5 tests cho 2 resources
        └── test_auth.py            # 4 tests cho Bearer middleware
```

---

## Quick start (60 giây)

```bash
cd implementation
python3 -m pip install -r requirements.txt   # cài fastmcp, pytest, httpx, python-dotenv
python3 init_db.py                           # tạo lab.db với schema + 6/4/12 rows
python3 -m pytest tests/ -v                  # chạy 40 tests → all pass
python3 mcp_server.py                        # khởi động server (stdio)
```

---

## Hướng dẫn chấm bài

Mỗi mục bên dưới ánh xạ trực tiếp với [Rubric.md](Rubric.md).

### 1. Server Foundation (20 pts)

```bash
cd implementation
python3 mcp_server.py
```

Kết quả mong đợi: banner FastMCP hiện ra, log `Starting MCP server 'SQLite Lab MCP Server' with transport 'stdio'`. Ctrl-C để thoát.

- ✅ Cấu trúc tách biệt: [db.py](implementation/db.py) (DB logic) ≠ [mcp_server.py](implementation/mcp_server.py) (MCP wrapping)
- ✅ Schema reproducible: chạy lại `python3 init_db.py` luôn ra cùng 6/4/12 rows (DROP + CREATE + seed idempotent)

### 2. Required Tools (30 pts)

```bash
python3 -m pytest tests/test_tools.py tests/test_adapter.py -v
```

26 + 5 = 31 tests phải pass. Hoặc test thủ công bằng MCP Inspector (mục 5).

| Tool | Test reference | Demo prompt trong Claude Code |
| --- | --- | --- |
| `search` | `test_search_*` (12 case) | *"Use sqlite-lab to list all students in cohort A1."* |
| `insert` | `test_insert_*` (5 case) | *"Use sqlite-lab to insert Ivan (cohort B1, email `ivan@example.com`)."* |
| `aggregate` | `test_aggregate_*` (7 case) | *"Use sqlite-lab to compute average score per course."* |

### 3. MCP Resources (15 pts)

```bash
python3 -m pytest tests/test_resources.py -v
```

- ✅ `schema://database` — [test_read_database_schema](implementation/tests/test_resources.py)
- ✅ `schema://table/{table_name}` — [test_read_table_schema](implementation/tests/test_resources.py)
- ✅ Reject unknown table — [test_read_unknown_table_raises](implementation/tests/test_resources.py)

Trong Claude Code, gõ `@sqlite-lab:schema://database` để đọc trực tiếp.

### 4. Safety & Error Handling (15 pts)

Xem [db.py:96-145](implementation/db.py#L96-L145) (`_build_where`) và [db.py:97-104](implementation/db.py#L97-L104) (`_require_table` / `_require_columns`).

| Rule | Test |
| --- | --- |
| Unknown table → ValidationError | `test_get_table_schema_unknown_raises`, `test_search_tool_unknown_table_clean_error` |
| Unknown column trong filter | `test_search_unknown_column_filter_raises` |
| Unsupported operator | `test_search_unknown_op_raises` |
| Bad aggregate metric | `test_aggregate_unknown_metric_raises` |
| Empty insert | `test_insert_empty_values_raises` |
| DB constraint violation | `test_insert_unique_violation_raises`, `test_insert_check_violation_raises` |
| Parameterized SQL | Xem `?` placeholders ở [db.py search/insert/aggregate](implementation/db.py) — identifier qua whitelist, value qua `?` |

### 5. Verification (10 pts)

**Cách A — tự động (khuyến nghị):**

```bash
cd implementation
python3 -m pytest tests/ -v
# expect: 40 passed
```

**Cách B — MCP Inspector (visual):**

```bash
cd implementation
./start_inspector.sh
```

Inspector mở trên browser. Trong tab Tools:

1. Thấy 3 tools (`search`, `insert`, `aggregate`) với schema chi tiết
2. Gọi `search` với `{"table":"students","filters":[{"column":"cohort","op":"eq","value":"A1"}]}` → 2 rows
3. Gọi `search` với `{"table":"aliens"}` → error rõ ràng: *"Unknown table 'aliens'. Available: courses, enrollments, students"*

Trong tab Resources:

1. Thấy `schema://database` + template `schema://table/{table_name}`
2. Click đọc → JSON schema sạch sẽ

Screenshots ở `screenshots/` (nếu có) là minh chứng cho buổi demo.

### 6. Client Integration & Demo (10 pts)

Repo đã ship sẵn [.mcp.json](.mcp.json) ở root.

**Để verify Claude Code kết nối:**

1. Mở thư mục repo trong Claude Code
2. Tin "sqlite-lab" hiện trong `/mcp` list
3. Demo prompts:
   - `@sqlite-lab:schema://database`
   - *"Use sqlite-lab to find top 3 students by max score."*
   - *"Use sqlite-lab to insert a new course CS999, title 'AI Ops', 3 credits."*
   - *"Use sqlite-lab to search a missing table 'aliens' — show me the error."*

Hướng dẫn chi tiết hơn (regenerate path khi không trùng máy): [implementation/README.md](implementation/README.md).

### 7. Bonus — HTTP + Bearer Auth (+5 pts)

```bash
cd implementation
cp .env.example .env                                    # chứa MCP_AUTH_TOKEN=devtoken123
python3 mcp_server.py --transport http --port 8765
```

Verify (terminal khác):

```bash
# missing → 401
curl -i -X POST http://127.0.0.1:8765/mcp/

# wrong → 401
curl -i -X POST http://127.0.0.1:8765/mcp/ -H "Authorization: Bearer wrong"

# correct → MCP routing (307)
curl -i -X POST http://127.0.0.1:8765/mcp/ -H "Authorization: Bearer devtoken123"
```

Hoặc chạy `python3 -m pytest tests/test_auth.py -v` (4 tests xanh).

Implementation: [auth.py](implementation/auth.py) dùng Starlette `BaseHTTPMiddleware`, wrap vào FastMCP qua `mcp.http_app(middleware=[...])`.

---

## Checklist nộp bài

| Item | Status |
| --- | --- |
| FastMCP server start được | ✅ |
| SQLite DB + seed reproducible | ✅ |
| 3 tools (`search`, `insert`, `aggregate`) | ✅ |
| 2 resources (static + template) | ✅ |
| Validation 8 operator + 5 metric + identifier whitelist | ✅ |
| 40 pytest tests xanh | ✅ |
| Claude Code `.mcp.json` config | ✅ |
| Implementation README + demo prompts | ✅ |
| Inspector helper script | ✅ |
| **Bonus**: HTTP transport + Bearer auth | ✅ |
| Demo video ~2 phút | ⏳ (sẽ quay) |
| Inspector screenshots | ⏳ (sẽ chụp) |

---

## Tài liệu thiết kế

- [docs/spec.md](docs/spec.md) — design spec đầy đủ (13 sections): data model, MCP interface, validation rules, bonus design, build sequence
- [implementation/README.md](implementation/README.md) — hướng dẫn dev/troubleshooting chi tiết
- [Rubric.md](Rubric.md) — tiêu chí chấm gốc (giảng viên cung cấp)

## Tham khảo

- FastMCP v3: <https://gofastmcp.com>
- MCP spec: <https://modelcontextprotocol.io>
- MCP Inspector: <https://modelcontextprotocol.io/docs/tools/inspector>
- Claude Code MCP: <https://code.claude.com/docs/en/mcp>
