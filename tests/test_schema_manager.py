"""
Tests for Schema Management & Introspection Service (backend/pipeline/schema_manager.py).
Ensures safe schema validation, type checking, primary key detection, and idempotency
without modifying existing database records.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.pipeline.schema_manager import (
    EXPECTED_TABLE_SCHEMAS,
    _is_type_compatible,
    initialize_schema,
    validate_schema,
)


def test_type_compatibility():
    """Verifies PostgreSQL type compatibility mappings."""
    assert _is_type_compatible("text", "text")
    assert _is_type_compatible("text", "character varying")
    assert _is_type_compatible("character varying", "text")
    assert _is_type_compatible("integer", "int4")
    assert _is_type_compatible("bigint", "int8")
    assert _is_type_compatible("double precision", "float8")
    assert _is_type_compatible("timestamp with time zone", "timestamptz")
    assert _is_type_compatible("jsonb", "json")
    # Incompatible types
    assert not _is_type_compatible("integer", "text")
    assert not _is_type_compatible("double precision", "boolean")
    assert not _is_type_compatible("boolean", "integer")


def test_validate_live_schema():
    """
    Validates live database schema against expected tables, columns, and constraints.
    Read-only test ensuring 2,283,664 protected records remain intact.
    """
    result = validate_schema()
    assert result.is_valid is True, f"Validation errors: {result.errors}"
    assert result.database_name == "rail_signal"
    assert result.total_records == 2283664
    assert len(result.errors) == 0

    expected_tables = {"stations", "trains", "schedules", "journey_train", "journey_test", "pipeline_runs"}
    assert set(result.tables.keys()) == expected_tables

    for tname, val in result.tables.items():
        assert val.exists is True
        assert len(val.missing_columns) == 0, f"Table {tname} missing columns: {val.missing_columns}"
        assert len(val.type_mismatches) == 0, f"Table {tname} type mismatches: {val.type_mismatches}"
        assert val.primary_key_valid is True, f"Table {tname} primary key invalid: {val.primary_key}"


def test_validate_schema_missing_table():
    """Verifies that missing tables are caught and marked as invalid."""
    mock_cur = MagicMock()
    # Mock current_database
    mock_cur.fetchone.side_effect = [
        ("mock_db",),  # current_database
        (0,),          # row counts
        (0,),
        (0,),
        (0,),
        (0,),
    ]
    # Mock existing tables: return all EXCEPT 'stations'
    remaining_tables = [("trains",), ("schedules",), ("journey_train",), ("journey_test",), ("pipeline_runs",)]
    mock_cur.fetchall.side_effect = [
        remaining_tables,  # information_schema.tables
        [],                # information_schema.columns
        [],                # information_schema.table_constraints
    ]

    result = validate_schema(cursor=mock_cur)
    assert result.is_valid is False
    assert any("Required table 'stations' does not exist" in err for err in result.errors)
    assert result.tables["stations"].exists is False


def test_validate_schema_missing_column():
    """Verifies that missing columns in an existing table are detected."""
    mock_cur = MagicMock()
    mock_cur.fetchone.side_effect = [
        ("mock_db",),  # current_database
        (0,), (0,), (0,), (0,), (0,), (0,)
    ]
    # All tables exist
    all_tables = [(t,) for t in EXPECTED_TABLE_SCHEMAS]
    # In stations, omit 'latitude'
    mock_cols = [
        ("stations", "station_code", "text"),
        ("stations", "station_name", "text"),
        ("stations", "state", "text"),
        ("stations", "zone", "text"),
        ("stations", "address", "text"),
        ("stations", "longitude", "double precision"),
        # 'latitude' is omitted
    ]
    # Primary key present
    mock_pks = [("stations", "station_code")]

    mock_cur.fetchall.side_effect = [
        all_tables,
        mock_cols,
        mock_pks,
    ]

    result = validate_schema(cursor=mock_cur)
    assert result.is_valid is False
    assert any("Table 'stations' missing column 'latitude'" in err for err in result.errors)
    assert "latitude" in result.tables["stations"].missing_columns


def test_validate_schema_type_mismatch():
    """Verifies that incompatible column data types are flagged."""
    mock_cur = MagicMock()
    mock_cur.fetchone.side_effect = [
        ("mock_db",),
        (0,), (0,), (0,), (0,), (0,), (0,)
    ]
    all_tables = [(t,) for t in EXPECTED_TABLE_SCHEMAS]
    # Stations with 'latitude' defined as 'boolean' instead of 'double precision'
    mock_cols = [
        ("stations", "station_code", "text"),
        ("stations", "station_name", "text"),
        ("stations", "state", "text"),
        ("stations", "zone", "text"),
        ("stations", "address", "text"),
        ("stations", "latitude", "boolean"),  # Mismatch!
        ("stations", "longitude", "double precision"),
    ]
    mock_pks = [("stations", "station_code")]

    mock_cur.fetchall.side_effect = [
        all_tables,
        mock_cols,
        mock_pks,
    ]

    result = validate_schema(cursor=mock_cur)
    assert result.is_valid is False
    assert any("type mismatch: expected 'double precision', found 'boolean'" in err for err in result.errors)


def test_validate_schema_primary_key_mismatch():
    """Verifies that an incorrect or missing primary key is reported."""
    mock_cur = MagicMock()
    mock_cur.fetchone.side_effect = [
        ("mock_db",),
        (0,), (0,), (0,), (0,), (0,), (0,)
    ]
    all_tables = [(t,) for t in EXPECTED_TABLE_SCHEMAS]
    mock_cols = [
        ("stations", "station_code", "text"),
        ("stations", "station_name", "text"),
        ("stations", "state", "text"),
        ("stations", "zone", "text"),
        ("stations", "address", "text"),
        ("stations", "latitude", "double precision"),
        ("stations", "longitude", "double precision"),
    ]
    # Primary key set to wrong column
    mock_pks = [("stations", "station_name")]

    mock_cur.fetchall.side_effect = [
        all_tables,
        mock_cols,
        mock_pks,
    ]

    result = validate_schema(cursor=mock_cur)
    assert result.is_valid is False
    assert any("primary key mismatch" in err for err in result.errors)
    assert result.tables["stations"].primary_key_valid is False


def test_initialize_schema_idempotent_live():
    """
    Verifies that calling initialize_schema against the live database is safe,
    idempotent, and leaves all protected records untouched.
    """
    res = initialize_schema()
    assert res["is_valid"] is True
    assert res["database"] == "rail_signal"
    assert res["total_protected_records"] == 2283664
    assert "00_core_tables.sql" in res["applied_files"]
    assert "01_pipeline_runs.sql" in res["applied_files"]


def test_initialize_schema_rejects_destructive_statements(tmp_path):
    """Verifies that initialize_schema strictly refuses to execute DDL with DROP or TRUNCATE."""
    bad_ddl = tmp_path / "bad.sql"
    bad_ddl.write_text("DROP TABLE stations;", encoding="utf-8")

    mock_cur = MagicMock()
    with pytest.raises(ValueError, match="Destructive statement 'DROP TABLE' detected"):
        initialize_schema(cursor=mock_cur, ddl_files=[bad_ddl])
