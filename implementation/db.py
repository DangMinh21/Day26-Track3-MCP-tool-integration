"""SQLite adapter for the MCP lab.

The adapter wraps sqlite3 with three things the MCP server needs:

- a configured connection (Row factory + foreign keys on)
- introspection helpers (list_tables, get_table_schema, list_columns)
- identifier validators that raise ValidationError on bad input

Later steps add `search`, `insert`, and `aggregate` methods on the same class.
Those methods rely on the validators here so identifier strings can never reach
SQL without being whitelisted first.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).parent / "lab.db"

# Whitelist of filter operators → SQL fragment template.
# `?` markers are bound parameters; `{placeholders}` is expanded for `in`.
FILTER_OPERATORS: dict[str, str] = {
    "eq":  "{col} = ?",
    "neq": "{col} != ?",
    "gt":  "{col} > ?",
    "gte": "{col} >= ?",
    "lt":  "{col} < ?",
    "lte": "{col} <= ?",
    "like": "{col} LIKE ?",
    "in":  "{col} IN ({placeholders})",
}

MAX_LIMIT = 100

AGGREGATE_METRICS: set[str] = {"count", "avg", "sum", "min", "max"}


class ValidationError(Exception):
    """Raised when a request fails identifier or operator validation."""


class SQLiteAdapter:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)

    # ---- connection ----

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ---- introspection ----

    def list_tables(self) -> list[str]:
        with closing(self.connect()) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            ).fetchall()
        return [r["name"] for r in rows]

    def get_table_schema(self, table: str) -> dict[str, Any]:
        self._require_table(table)
        # PRAGMA does not accept ? placeholders, so `table` is interpolated
        # directly. _require_table above guarantees it is a known table name.
        with closing(self.connect()) as conn:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        columns = [
            {
                "name": r["name"],
                "type": r["type"],
                "not_null": bool(r["notnull"]),
                "default": r["dflt_value"],
                "primary_key": bool(r["pk"]),
            }
            for r in rows
        ]
        return {
            "table": table,
            "columns": columns,
            "primary_key": next(
                (c["name"] for c in columns if c["primary_key"]), None
            ),
        }

    def list_columns(self, table: str) -> list[str]:
        return [c["name"] for c in self.get_table_schema(table)["columns"]]

    # ---- validators ----

    def _require_table(self, table: str) -> None:
        tables = self.list_tables()
        if table not in tables:
            raise ValidationError(
                f"Unknown table '{table}'. Available: {', '.join(tables)}"
            )

    def _require_columns(self, table: str, columns: list[str]) -> None:
        available = self.list_columns(table)
        unknown = [c for c in columns if c not in available]
        if unknown:
            raise ValidationError(
                f"Unknown column(s) {unknown} on table '{table}'. "
                f"Available: {', '.join(available)}"
            )

    def _build_where(
        self, table: str, filters: list[dict] | None
    ) -> tuple[str, list[Any]]:
        """Translate a list of filter dicts into a (sql_fragment, params) pair.

        Returns ("", []) when there are no filters. The fragment always starts
        with " WHERE " when non-empty so callers can concatenate it directly.
        """
        if not filters:
            return "", []
        columns = self.list_columns(table)
        clauses: list[str] = []
        params: list[Any] = []
        for i, flt in enumerate(filters):
            if not isinstance(flt, dict):
                raise ValidationError(
                    f"Filter {i} must be an object with 'column', 'op', 'value'."
                )
            col = flt.get("column")
            op = flt.get("op")
            if col not in columns:
                raise ValidationError(
                    f"Unknown column '{col}' on table '{table}'. "
                    f"Available: {', '.join(columns)}"
                )
            if op not in FILTER_OPERATORS:
                raise ValidationError(
                    f"Unsupported operator '{op}'. "
                    f"Allowed: {', '.join(FILTER_OPERATORS)}"
                )
            if op == "in":
                values = flt.get("value")
                if not isinstance(values, list) or not values:
                    raise ValidationError(
                        f"Filter {i}: 'in' operator requires a non-empty list."
                    )
                placeholders = ",".join(["?"] * len(values))
                clauses.append(
                    FILTER_OPERATORS["in"].format(col=col, placeholders=placeholders)
                )
                params.extend(values)
            else:
                if "value" not in flt:
                    raise ValidationError(f"Filter {i}: missing 'value'.")
                clauses.append(FILTER_OPERATORS[op].format(col=col))
                params.append(flt["value"])
        return " WHERE " + " AND ".join(clauses), params

    # ---- tools ----

    def search(
        self,
        table: str,
        filters: list[dict] | None = None,
        columns: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        self._require_table(table)

        if not isinstance(limit, int) or not (1 <= limit <= MAX_LIMIT):
            raise ValidationError(
                f"limit must be an integer between 1 and {MAX_LIMIT}."
            )
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("offset must be a non-negative integer.")

        available = self.list_columns(table)
        if columns:
            self._require_columns(table, columns)
            select_cols = ", ".join(columns)
        else:
            select_cols = "*"

        where_sql, params = self._build_where(table, filters)

        order_sql = ""
        if order_by is not None:
            if order_by not in available:
                raise ValidationError(
                    f"order_by column '{order_by}' not in table '{table}'."
                )
            direction = "DESC" if descending else "ASC"
            order_sql = f" ORDER BY {order_by} {direction}"

        sql = (
            f"SELECT {select_cols} FROM {table}{where_sql}{order_sql} "
            f"LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])

        with closing(self.connect()) as conn:
            rows = conn.execute(sql, params).fetchall()

        return {
            "table": table,
            "count": len(rows),
            "rows": [dict(r) for r in rows],
            "limit": limit,
            "offset": offset,
        }

    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        self._require_table(table)
        if not isinstance(values, dict):
            raise ValidationError("'values' must be an object mapping column to value.")
        if not values:
            raise ValidationError("'values' must contain at least one column.")

        columns = list(values.keys())
        self._require_columns(table, columns)

        placeholders = ", ".join(["?"] * len(columns))
        col_list = ", ".join(columns)
        sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"

        with closing(self.connect()) as conn:
            try:
                cur = conn.execute(sql, list(values.values()))
                conn.commit()
            except sqlite3.IntegrityError as exc:
                # Surface DB-level constraints (UNIQUE, NOT NULL, CHECK, FK) as
                # ValidationError so the MCP tool layer returns a clean message.
                raise ValidationError(f"Insert rejected by database: {exc}") from exc
            new_id = cur.lastrowid
            row = conn.execute(
                f"SELECT * FROM {table} WHERE rowid = ?", (new_id,)
            ).fetchone()

        return {
            "table": table,
            "inserted_id": new_id,
            "values": dict(row) if row else dict(values),
        }

    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: list[dict] | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        self._require_table(table)

        metric_lower = metric.lower() if isinstance(metric, str) else metric
        if metric_lower not in AGGREGATE_METRICS:
            raise ValidationError(
                f"Unsupported metric '{metric}'. "
                f"Allowed: {', '.join(sorted(AGGREGATE_METRICS))}"
            )

        available = self.list_columns(table)

        if metric_lower == "count":
            if column in (None, "*"):
                metric_expr = "COUNT(*)"
            else:
                if column not in available:
                    raise ValidationError(
                        f"Unknown column '{column}' on table '{table}'."
                    )
                metric_expr = f"COUNT({column})"
        else:
            if not column:
                raise ValidationError(
                    f"Metric '{metric_lower}' requires a 'column' argument."
                )
            if column not in available:
                raise ValidationError(
                    f"Unknown column '{column}' on table '{table}'."
                )
            metric_expr = f"{metric_lower.upper()}({column})"

        where_sql, params = self._build_where(table, filters)

        if group_by is not None:
            if group_by not in available:
                raise ValidationError(
                    f"group_by column '{group_by}' not in table '{table}'."
                )
            select_cols = f"{group_by} AS grp, {metric_expr} AS value"
            group_sql = f" GROUP BY {group_by} ORDER BY {group_by}"
        else:
            select_cols = f"{metric_expr} AS value"
            group_sql = ""

        sql = f"SELECT {select_cols} FROM {table}{where_sql}{group_sql}"

        with closing(self.connect()) as conn:
            rows = conn.execute(sql, params).fetchall()

        return {
            "table": table,
            "metric": metric_lower,
            "column": column,
            "group_by": group_by,
            "rows": [
                {
                    "group": r["grp"] if group_by is not None else None,
                    "value": r["value"],
                }
                for r in rows
            ],
        }


if __name__ == "__main__":
    adapter = SQLiteAdapter()
    tables = adapter.list_tables()
    print("Tables:", tables)
    print()
    for table in tables:
        schema = adapter.get_table_schema(table)
        print(f"{table}  (pk={schema['primary_key']})")
        for col in schema["columns"]:
            flags = []
            if col["primary_key"]:
                flags.append("PK")
            if col["not_null"]:
                flags.append("NOT NULL")
            flag_str = f"  [{', '.join(flags)}]" if flags else ""
            default = f"  default={col['default']!r}" if col["default"] is not None else ""
            print(f"  - {col['name']:<12} {col['type']:<10}{flag_str}{default}")
        print()
