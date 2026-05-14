"""Unit tests for SQLiteAdapter."""

from __future__ import annotations

import pytest

from db import SQLiteAdapter, ValidationError


# ---- introspection ----

def test_list_tables(adapter: SQLiteAdapter):
    assert adapter.list_tables() == ["courses", "enrollments", "students"]


def test_get_table_schema_known(adapter: SQLiteAdapter):
    schema = adapter.get_table_schema("students")
    assert schema["table"] == "students"
    assert schema["primary_key"] == "id"
    assert {c["name"] for c in schema["columns"]} == {
        "id", "name", "email", "cohort", "created_at"
    }


def test_get_table_schema_unknown_raises(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="Unknown table 'ghost'"):
        adapter.get_table_schema("ghost")


# ---- search ----

def test_search_returns_all_rows_by_default(adapter: SQLiteAdapter):
    res = adapter.search("students")
    assert res["count"] == 6
    assert res["limit"] == 20 and res["offset"] == 0


def test_search_filters_eq(adapter: SQLiteAdapter):
    res = adapter.search("students", filters=[{"column": "cohort", "op": "eq", "value": "A1"}])
    assert res["count"] == 2
    assert {r["name"] for r in res["rows"]} == {"Alice Nguyen", "Bob Tran"}


def test_search_filters_in(adapter: SQLiteAdapter):
    res = adapter.search(
        "students",
        filters=[{"column": "cohort", "op": "in", "value": ["A1", "B1"]}],
    )
    assert res["count"] == 4


def test_search_filters_like(adapter: SQLiteAdapter):
    res = adapter.search(
        "students",
        filters=[{"column": "email", "op": "like", "value": "%@example.com"}],
    )
    assert res["count"] == 6


def test_search_order_and_pagination(adapter: SQLiteAdapter):
    res = adapter.search(
        "enrollments", order_by="score", descending=True, limit=2, offset=1
    )
    assert res["count"] == 2
    assert res["rows"][0]["score"] == 92.0  # 2nd highest after 95


def test_search_columns_projection(adapter: SQLiteAdapter):
    res = adapter.search("students", columns=["id", "name"], limit=1)
    assert set(res["rows"][0].keys()) == {"id", "name"}


def test_search_unknown_op_raises(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="Unsupported operator 'regex'"):
        adapter.search(
            "students", filters=[{"column": "cohort", "op": "regex", "value": "A.*"}]
        )


def test_search_unknown_column_filter_raises(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="Unknown column 'ghost'"):
        adapter.search(
            "students", filters=[{"column": "ghost", "op": "eq", "value": 1}]
        )


def test_search_limit_too_high_raises(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="limit must be an integer between 1 and 100"):
        adapter.search("students", limit=999)


def test_search_unknown_order_column_raises(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="order_by column 'nope'"):
        adapter.search("students", order_by="nope")


def test_search_empty_in_list_raises(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="non-empty list"):
        adapter.search("students", filters=[{"column": "cohort", "op": "in", "value": []}])


# ---- insert ----

def test_insert_returns_full_row(adapter: SQLiteAdapter):
    res = adapter.insert(
        "students", {"name": "Heidi", "email": "heidi@example.com", "cohort": "A2"}
    )
    assert res["inserted_id"] == 7
    assert res["values"]["name"] == "Heidi"
    assert "created_at" in res["values"]  # default filled by DB


def test_insert_empty_values_raises(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="at least one column"):
        adapter.insert("students", {})


def test_insert_unknown_column_raises(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="Unknown column"):
        adapter.insert("students", {"name": "x", "bogus": "?"})


def test_insert_unique_violation_raises(adapter: SQLiteAdapter):
    adapter.insert("students", {"name": "A", "email": "dup@example.com", "cohort": "A1"})
    with pytest.raises(ValidationError, match="UNIQUE constraint failed"):
        adapter.insert(
            "students", {"name": "B", "email": "dup@example.com", "cohort": "A1"}
        )


def test_insert_check_violation_raises(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="CHECK constraint failed"):
        adapter.insert("courses", {"code": "X", "title": "y", "credits": 0})


# ---- aggregate ----

def test_aggregate_count_all(adapter: SQLiteAdapter):
    res = adapter.aggregate("students", "count")
    assert res["rows"] == [{"group": None, "value": 6}]


def test_aggregate_avg_score(adapter: SQLiteAdapter):
    res = adapter.aggregate("enrollments", "avg", column="score")
    assert res["rows"][0]["value"] == pytest.approx(77.666, rel=1e-3)


def test_aggregate_grouped_by(adapter: SQLiteAdapter):
    res = adapter.aggregate("students", "count", group_by="cohort")
    assert {r["group"] for r in res["rows"]} == {"A1", "A2", "B1"}
    assert all(r["value"] == 2 for r in res["rows"])


def test_aggregate_with_filter(adapter: SQLiteAdapter):
    res = adapter.aggregate(
        "enrollments", "max", column="score",
        filters=[{"column": "course_id", "op": "eq", "value": 1}],
    )
    assert res["rows"] == [{"group": None, "value": 92.0}]


def test_aggregate_unknown_metric_raises(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="Unsupported metric 'median'"):
        adapter.aggregate("students", "median")


def test_aggregate_avg_without_column_raises(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="requires a 'column'"):
        adapter.aggregate("students", "avg")


def test_aggregate_unknown_group_column_raises(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="group_by column 'ghost'"):
        adapter.aggregate("students", "count", group_by="ghost")
