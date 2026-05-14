# SQLite MCP Server — Implementation Spec

> Spec này khoá lại các quyết định thiết kế cho lab Day26-Track3.
> Mục tiêu: vừa hoàn thành rubric 100pts + 5pts bonus, vừa học hiệu quả qua quy trình chia nhỏ.

---

## 1. Overview

Build một **FastMCP server** expose một SQLite database (`students` / `courses` / `enrollments`) qua MCP protocol với:

- 3 tools: `search`, `insert`, `aggregate`
- 2 resources: `schema://database`, `schema://table/{table_name}`
- Validation chống SQL injection và bad input
- Bonus: **HTTP/SSE transport có Bearer token auth**

Client target: **Claude Code** (stdio cho dev, HTTP cho bonus demo).

---

## 2. Tech Stack

| Component | Choice | Lý do |
|---|---|---|
| Language | Python 3.10+ | FastMCP yêu cầu 3.10+ |
| MCP framework | `fastmcp` (v2) | Theo README, decorators rõ ràng |
| Database | SQLite (file `lab.db`) | Đơn giản, no external service |
| DB driver | stdlib `sqlite3` | Built-in, không cần ORM |
| Testing | `pytest` | Auto test cho rubric Verification |
| Auth (bonus) | Bearer token (env var) | Đơn giản nhất cho HTTP transport |
| Package mgr | `uv` hoặc `pip` + `requirements.txt` | Đề xuất `uv` vì nhanh, nhưng pip OK |

### Dependencies
```
fastmcp>=2.0
pytest>=7.0
httpx  # for HTTP transport tests
```

---

## 3. Data Model

### Schema

```sql
CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    cohort TEXT NOT NULL,            -- ví dụ 'A1', 'A2', 'B1'
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,       -- ví dụ 'CS101'
    title TEXT NOT NULL,
    credits INTEGER NOT NULL CHECK(credits > 0)
);

CREATE TABLE enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id),
    course_id INTEGER NOT NULL REFERENCES courses(id),
    score REAL CHECK(score >= 0 AND score <= 100),
    enrolled_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, course_id)
);
```

### Seed Data (tối thiểu)

- 6 students (2 cohort A1, 2 cohort A2, 2 cohort B1)
- 4 courses (CS101, CS102, MATH101, ENG101)
- ~10 enrollments với điểm phân tán để demo `avg`, `min`, `max`

---

## 4. Project Structure

```
Day26-Track3-MCP-tool-integration/
├── README.md                       # gốc (sẵn có)
├── Rubric.md                       # gốc (sẵn có)
├── Tips.md                         # gốc (sẵn có)
├── docs/
│   └── spec.md                     # file này
├── pseudocode/                     # khung gốc (giữ làm reference)
├── implementation/
│   ├── db.py                       # SQLiteAdapter
│   ├── init_db.py                  # tạo schema + seed
│   ├── mcp_server.py               # FastMCP server (stdio + http)
│   ├── auth.py                     # Bearer token middleware (bonus)
│   ├── requirements.txt
│   ├── start_inspector.sh          # helper script chạy Inspector
│   ├── lab.db                      # SQLite file (gitignore)
│   ├── .env.example                # mẫu env vars
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py             # fixtures (fresh db per test)
│       ├── test_adapter.py         # unit tests cho SQLiteAdapter
│       ├── test_tools.py           # test 3 MCP tools
│       └── test_resources.py       # test 2 MCP resources
└── screenshots/                    # Inspector screenshots cho demo
    ├── tools-list.png
    ├── search-success.png
    ├── search-error.png
    └── schema-resource.png
```

---

## 5. MCP Server Interface

### 5.1 Tool: `search`

**Mục đích**: query rows từ một bảng với filter, sắp xếp, phân trang.

**Input schema:**
```python
{
    "table": str,                              # required, e.g. "students"
    "filters": list[dict] | None,              # optional
    "columns": list[str] | None,               # optional, default = all
    "limit": int = 20,                         # max 100
    "offset": int = 0,
    "order_by": str | None,
    "descending": bool = False
}
```

**Filter format:**
```python
{"column": "cohort", "op": "eq", "value": "A1"}
```

**Operators supported**: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `in`

**Output:**
```python
{
    "table": "students",
    "count": 2,
    "rows": [{"id": 1, "name": "...", ...}, ...],
    "limit": 20,
    "offset": 0
}
```

### 5.2 Tool: `insert`

**Input:**
```python
{
    "table": str,
    "values": dict[str, Any]   # {"name": "...", "email": "...", "cohort": "A1"}
}
```

**Output:**
```python
{
    "table": "students",
    "inserted_id": 7,
    "values": {...}            # echo back full row including generated id
}
```

### 5.3 Tool: `aggregate`

**Input:**
```python
{
    "table": str,
    "metric": str,             # "count" | "avg" | "sum" | "min" | "max"
    "column": str | None,      # required for avg/sum/min/max, optional for count
    "filters": list[dict] | None,
    "group_by": str | None
}
```

**Output:**
```python
{
    "table": "enrollments",
    "metric": "avg",
    "column": "score",
    "group_by": "course_id",
    "rows": [
        {"group": 1, "value": 85.2},
        {"group": 2, "value": 78.1}
    ]
}
```

### 5.4 Resource: `schema://database`

Return JSON text chứa toàn bộ schema:
```json
{
  "tables": {
    "students": {"columns": [...], "primary_key": "id"},
    "courses":  {...},
    "enrollments": {...}
  }
}
```

### 5.5 Resource template: `schema://table/{table_name}`

Return JSON cho 1 table cụ thể. Reject nếu table không tồn tại.

---

## 6. Validation Rules

| Rule | Hành vi |
|---|---|
| Table name không có trong `list_tables()` | Raise `ValidationError` với message rõ ràng |
| Column name không có trong `PRAGMA table_info` | Raise `ValidationError` |
| Operator không nằm trong whitelist | Raise `ValidationError` |
| `metric` không nằm trong whitelist | Raise `ValidationError` |
| `insert` với `values = {}` | Raise `ValidationError` |
| `limit > 100` hoặc `limit < 1` | Raise `ValidationError` |
| Identifier names trong SQL | Phải đi qua whitelist check, **không** quote raw |
| Values trong SQL | Luôn dùng parameterized `?` placeholders |

### Error format trả về client
FastMCP sẽ wrap exception thành MCP error response. Đảm bảo message ngắn gọn, có actionable hint, ví dụ:
- `"Unknown table 'studetns'. Available: students, courses, enrollments"`
- `"Unsupported operator 'regex'. Allowed: eq, neq, gt, gte, lt, lte, like, in"`

---

## 7. Bonus: HTTP/SSE Transport + Auth

### Approach
- FastMCP hỗ trợ `mcp.run(transport="http")` hoặc `transport="sse"`.
- Thêm middleware kiểm Bearer token từ header `Authorization: Bearer <TOKEN>`.
- Token đọc từ env var `MCP_AUTH_TOKEN` (load qua `.env`).

### CLI

```bash
# Default stdio (cho Claude Code dev)
python mcp_server.py

# HTTP transport với auth
MCP_AUTH_TOKEN=devtoken123 python mcp_server.py --transport http --port 8765
```

### Test
- Test request không header → 401
- Test request sai token → 401
- Test request đúng token → 200 + tool response

---

## 8. Testing Strategy

### Unit tests (`test_adapter.py`)
- `list_tables()` đúng
- `get_table_schema('students')` trả về đúng columns
- `search` với từng operator
- `insert` thành công và reject bad input
- `aggregate` cho mỗi metric (count/avg/sum/min/max)
- Validation errors raise đúng type

### Integration tests (`test_tools.py`, `test_resources.py`)
- Gọi tool qua FastMCP test harness (in-memory client)
- Test discovery: 3 tools + 2 resources visible
- Test resource read `schema://database` và `schema://table/students`

### Manual verification (Inspector)
1. `start_inspector.sh` mở Inspector
2. Screenshot tool list
3. Screenshot 1 valid search → kết quả
4. Screenshot 1 invalid call → error message
5. Screenshot resource list + schema content

### Acceptance script
`verify_server.py` chạy `pytest -q` rồi in PASS/FAIL summary — dùng để chấm tự động.

---

## 9. Claude Code Client Integration

### `.mcp.json` (project root)
```json
{
  "mcpServers": {
    "sqlite-lab": {
      "type": "stdio",
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/implementation/mcp_server.py"],
      "env": {}
    }
  }
}
```

### Demo commands trong Claude Code
- `@sqlite-lab:schema://database` — đọc full schema
- `@sqlite-lab:schema://table/students` — đọc schema bảng cụ thể
- Prompt: *"Use sqlite-lab to find all students in cohort A1"*
- Prompt: *"Use sqlite-lab to compute average score per course"*

---

## 10. Build Sequence (vibe-code workflow)

Mỗi bước = 1 commit, mỗi commit nên chạy được (server start hoặc tests pass).

| # | Bước | Output | Học gì |
|---|---|---|---|
| 1 | `init_db.py` + schema SQL | `lab.db` được tạo với seed data | DDL, sqlite3 module |
| 2 | `db.py` — `connect`, `list_tables`, `get_table_schema` | Adapter cơ bản | PRAGMA, row_factory |
| 3 | `db.py` — `search` + validation | search hoạt động qua REPL | Parameterized SQL, identifier whitelist |
| 4 | `db.py` — `insert` | Insert hoạt động | RETURNING / lastrowid |
| 5 | `db.py` — `aggregate` | 5 metrics + group_by | SQL aggregation |
| 6 | `mcp_server.py` — wrap 3 tools với `@mcp.tool` | Server start + Inspector thấy 3 tools | FastMCP decorators |
| 7 | `mcp_server.py` — 2 resources | Inspector đọc được schema | `@mcp.resource` template |
| 8 | `tests/` — unit + integration tests | `pytest -q` PASS | pytest fixtures, MCP testing |
| 9 | Claude Code config + demo | Screenshot demo | MCP client integration |
| 10 | **Bonus**: `auth.py` + HTTP transport | HTTP server với token check | FastMCP HTTP, middleware |
| 11 | README implementation + demo video script | Submission ready | Documentation |

**Quy tắc học hiệu quả**: trước khi vào bước `N`, đọc hoặc hỏi AI giải thích _khái niệm chính_ ở cột "Học gì", sau đó mới code. Sau mỗi bước, tự nói lại bằng lời mình đã làm gì.

---

## 11. Acceptance Checklist (map sang Rubric)

### Server Foundation (20pts)
- [ ] `python mcp_server.py` start không lỗi
- [ ] Project structure rõ: `db.py` ≠ `mcp_server.py`
- [ ] `init_db.py` chạy idempotent (re-run không break)
- [ ] `requirements.txt` đầy đủ

### Required Tools (30pts)
- [ ] `search` có filters, ordering, pagination — test ≥ 3 case
- [ ] `insert` trả về inserted row + id
- [ ] `aggregate` hỗ trợ count/avg/sum/min/max + group_by

### MCP Resources (15pts)
- [ ] `schema://database` đọc được
- [ ] `schema://table/{name}` đọc được, reject bảng lạ

### Safety (15pts)
- [ ] Bảng/cột lạ → ValidationError clear
- [ ] Operator/metric không hỗ trợ → ValidationError clear
- [ ] Mọi WHERE/VALUES dùng `?` placeholders

### Verification (10pts)
- [ ] `pytest -q` xanh
- [ ] Inspector screenshot tool list
- [ ] Inspector screenshot success + error cases

### Client + Demo (10pts)
- [ ] Claude Code `.mcp.json` hoạt động
- [ ] README implementation có: setup, run, test, demo
- [ ] Video demo ~2 phút

### Bonus (+5pts)
- [ ] HTTP transport chạy được
- [ ] Bearer auth chặn no-token và bad-token
- [ ] Auth test trong pytest

---

## 12. Open Questions / Quyết định mặc định

Các điểm sau dùng mặc định, có thể đổi sau:

- **Limit max trong `search`**: 100 (đổi nếu cần demo dataset lớn hơn)
- **Auth token storage**: env var đơn lẻ (production nên dùng secrets manager)
- **Pagination cursor vs offset**: dùng offset cho đơn giản
- **HTTP port**: 8765 (đổi nếu trùng)
- **Database path**: `./lab.db` relative tới cwd của server process (có thể override qua env `DB_PATH`)
- **Resource MIME type**: `application/json` cho schema responses

---

## 13. References

- FastMCP quickstart: https://gofastmcp.com/v2/getting-started/quickstart
- FastMCP resources: https://gofastmcp.com/v2/servers/resources
- MCP Inspector: https://modelcontextprotocol.io/docs/tools/inspector
- Claude Code MCP: https://code.claude.com/docs/en/mcp
