"""Pytest fixtures.

Each test gets its own SQLite file under pytest's tmp_path so tests are
isolated, run in parallel safely, and never touch the dev `lab.db` next
to the source.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the `implementation/` folder importable when pytest is invoked from
# the project root.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import SQLiteAdapter  # noqa: E402
from init_db import create_database  # noqa: E402


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Build a fresh seeded database in a tmp dir and return its path."""
    path = tmp_path / "lab.db"
    create_database(path)
    return path


@pytest.fixture
def adapter(db_path: Path) -> SQLiteAdapter:
    """SQLiteAdapter wired to the per-test database."""
    return SQLiteAdapter(db_path)


@pytest.fixture
def mcp_server(db_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Return the module-level FastMCP instance with its adapter redirected
    to the per-test DB. Tests can drive it through a fastmcp Client."""
    import mcp_server as srv

    monkeypatch.setattr(srv.adapter, "db_path", db_path)
    return srv.mcp
