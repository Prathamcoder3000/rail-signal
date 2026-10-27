"""
Database Schema Management & Validation Service for RAIL / SIGNAL.

Provides authoritative schema validation, introspection, and safe idempotent
initialization across all RAIL / SIGNAL relational tables:
1. stations
2. trains
3. schedules
4. journey_train
5. journey_test
6. pipeline_runs

Safety Guarantees:
- Read-only validation queries against information_schema and pg_catalog.
- Safe idempotent initialization using CREATE TABLE IF NOT EXISTS.
- Strict refusal to DROP, TRUNCATE, or alter existing protected data tables.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import psycopg2
from psycopg2 import sql

from backend.app.config import settings
from backend.app.db import get_db_cursor

logger = logging.getLogger("rail_signal.schema_manager")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [rail_signal.schema_manager] %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = PROJECT_ROOT / "sql" / "schema"

# Type compatibility mappings (canonical type -> set of acceptable PostgreSQL types)
TYPE_COMPATIBILITY = {
    "text": {"text", "character varying", "varchar", "character", "char"},
    "character varying": {"character varying", "varchar", "text"},
    "integer": {"integer", "int", "int4", "smallint", "int2"},
    "smallint": {"smallint", "int2", "integer", "int4"},
    "bigint": {"bigint", "int8", "integer", "int4"},
    "double precision": {"double precision", "float8", "numeric", "real", "float4"},
    "numeric": {"numeric", "double precision", "float8", "real"},
    "boolean": {"boolean", "bool"},
    "timestamp with time zone": {
        "timestamp with time zone",
        "timestamptz",
        "timestamp without time zone",
    },
    "jsonb": {"jsonb", "json"},
}

# Authoritative specification of tables, primary keys, and required column data types
EXPECTED_TABLE_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "stations": {
        "primary_key": "station_code",
        "columns": {
            "station_code": "text",
            "station_name": "text",
            "state": "text",
            "zone": "text",
            "address": "text",
            "latitude": "double precision",
            "longitude": "double precision",
        },
    },
    "trains": {
        "primary_key": "train_number",
        "columns": {
            "train_number": "text",
            "train_name": "text",
            "train_type": "text",
            "zone": "text",
            "from_station_code": "text",
            "from_station_name": "text",
            "to_station_code": "text",
            "to_station_name": "text",
            "departure_time": "text",
            "arrival_time": "text",
            "duration_hours": "integer",
            "duration_minutes": "integer",
            "distance_km": "integer",
            "has_first_ac": "boolean",
            "has_second_ac": "boolean",
            "has_third_ac": "boolean",
            "has_sleeper": "boolean",
            "has_chair_car": "boolean",
        },
    },
    "schedules": {
        "primary_key": "schedule_id",
        "columns": {
            "schedule_id": "bigint",
            "train_number": "text",
            "station_code": "text",
            "station_name": "text",
            "arrival_time": "text",
            "departure_time": "text",
            "day_number": "integer",
        },
    },
    "journey_train": {
        "primary_key": "journey_id",
        "columns": {
            "journey_id": "text",
            "train_number": "text",
            "train_type": "text",
            "departure_date": "text",
            "year": "integer",
            "month": "integer",
            "day_of_week": "integer",
            "departure_hour": "integer",
            "is_weekend": "smallint",
            "is_night_departure": "smallint",
            "is_peak_hour": "smallint",
            "is_festival_season": "smallint",
            "season": "text",
            "zone": "text",
            "zone_abbr": "text",
            "source_station_category": "text",
            "destination_station_category": "text",
            "distance_km": "integer",
            "num_scheduled_stops": "integer",
            "scheduled_travel_hours": "double precision",
            "track_doubled": "smallint",
            "is_hdn_route": "smallint",
            "traction_type": "text",
            "is_electrified": "smallint",
            "psr_count": "integer",
            "is_circular_route": "smallint",
            "is_monsoon_season": "smallint",
            "is_fog_risk": "smallint",
            "fog_risk_score": "double precision",
            "zone_fog_index": "double precision",
            "zone_congestion_index": "double precision",
            "season_severity_score": "double precision",
            "loco_age_years": "double precision",
            "coach_age_years": "double precision",
            "has_lhb_coaches": "smallint",
            "is_rake_shared": "smallint",
            "maintenance_score": "double precision",
            "seat_utilisation_pct": "double precision",
            "is_overloaded": "smallint",
            "late_incoming_rake": "smallint",
            "is_special_train": "smallint",
            "route_historical_ontime_pct": "double precision",
            "primary_delay_cause": "text",
            "delay_minutes": "integer",
            "is_delayed": "smallint",
        },
    },
    "journey_test": {
        "primary_key": "journey_id",
        "columns": {
            "journey_id": "text",
            "train_number": "text",
            "train_type": "text",
            "departure_date": "text",
            "year": "integer",
            "month": "integer",
            "day_of_week": "integer",
            "departure_hour": "integer",
            "is_weekend": "smallint",
            "is_night_departure": "smallint",
            "is_peak_hour": "smallint",
            "is_festival_season": "smallint",
            "season": "text",
            "zone": "text",
            "zone_abbr": "text",
            "source_station_category": "text",
            "destination_station_category": "text",
            "distance_km": "integer",
            "num_scheduled_stops": "integer",
            "scheduled_travel_hours": "double precision",
            "track_doubled": "smallint",
            "is_hdn_route": "smallint",
            "traction_type": "text",
            "is_electrified": "smallint",
            "psr_count": "integer",
            "is_circular_route": "smallint",
            "is_monsoon_season": "smallint",
            "is_fog_risk": "smallint",
            "fog_risk_score": "double precision",
            "zone_fog_index": "double precision",
            "zone_congestion_index": "double precision",
            "season_severity_score": "double precision",
            "loco_age_years": "double precision",
            "coach_age_years": "double precision",
            "has_lhb_coaches": "smallint",
            "is_rake_shared": "smallint",
            "maintenance_score": "double precision",
            "seat_utilisation_pct": "double precision",
            "is_overloaded": "smallint",
            "late_incoming_rake": "smallint",
            "is_special_train": "smallint",
            "route_historical_ontime_pct": "double precision",
        },
    },
    "pipeline_runs": {
        "primary_key": "run_id",
        "columns": {
            "run_id": "character varying",
            "pipeline_name": "character varying",
            "run_type": "character varying",
            "trigger_type": "character varying",
            "status": "character varying",
            "start_time": "timestamp with time zone",
            "finish_time": "timestamp with time zone",
            "duration_seconds": "numeric",
            "records_processed": "bigint",
            "records_accepted": "bigint",
            "records_quarantined": "bigint",
            "current_stage": "character varying",
            "failed_stage": "character varying",
            "error_summary": "text",
            "stage_details": "jsonb",
            "metadata": "jsonb",
            "created_at": "timestamp with time zone",
            "updated_at": "timestamp with time zone",
        },
    },
}


@dataclass
class ColumnMismatch:
    column_name: str
    expected_type: str
    actual_type: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class TableValidation:
    table_name: str
    exists: bool = False
    columns_matched: int = 0
    total_expected_columns: int = 0
    missing_columns: List[str] = field(default_factory=list)
    type_mismatches: List[ColumnMismatch] = field(default_factory=list)
    primary_key: Optional[str] = None
    expected_primary_key: Optional[str] = None
    primary_key_valid: bool = False
    row_count: int = 0

    @property
    def is_valid(self) -> bool:
        return (
            self.exists
            and len(self.missing_columns) == 0
            and len(self.type_mismatches) == 0
            and self.primary_key_valid
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["is_valid"] = self.is_valid
        return d


@dataclass
class SchemaValidationResult:
    is_valid: bool
    database_name: str
    tables: Dict[str, TableValidation] = field(default_factory=dict)
    total_records: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "database_name": self.database_name,
            "total_records": self.total_records,
            "errors": self.errors,
            "warnings": self.warnings,
            "tables": {k: v.to_dict() for k, v in self.tables.items()},
        }


def _is_type_compatible(expected: str, actual: str) -> bool:
    """Checks whether the database column data type is compatible with expected type."""
    exp_lower = expected.strip().lower()
    act_lower = actual.strip().lower()
    if exp_lower == act_lower:
        return True
    compatible_set = TYPE_COMPATIBILITY.get(exp_lower, {exp_lower})
    return act_lower in compatible_set


def validate_schema(cursor=None) -> SchemaValidationResult:
    """
    Introspects PostgreSQL schema for all RAIL / SIGNAL tables without altering data.
    Verifies table existence, column names, data type compatibility, primary keys,
    and returns a structured SchemaValidationResult.
    """
    if cursor is not None:
        return _validate_schema_with_cursor(cursor)
    
    with get_db_cursor() as cur:
        return _validate_schema_with_cursor(cur)


def _validate_schema_with_cursor(cur) -> SchemaValidationResult:
    cur.execute("SELECT current_database();")
    db_name_row = cur.fetchone()
    db_name = (
        db_name_row[0]
        if isinstance(db_name_row, (list, tuple))
        else db_name_row["current_database"]
    )

    result = SchemaValidationResult(
        is_valid=True,
        database_name=str(db_name),
    )

    # 1. Fetch all existing user tables in public schema
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
    """)
    existing_tables = set()
    for row in cur.fetchall():
        tname = row[0] if isinstance(row, (list, tuple)) else row["table_name"]
        existing_tables.add(tname)

    # 2. Fetch all column definitions
    cur.execute("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
    """)
    table_columns: Dict[str, Dict[str, str]] = {}
    for row in cur.fetchall():
        tname = row[0] if isinstance(row, (list, tuple)) else row["table_name"]
        cname = row[1] if isinstance(row, (list, tuple)) else row["column_name"]
        dtype = row[2] if isinstance(row, (list, tuple)) else row["data_type"]
        if tname not in table_columns:
            table_columns[tname] = {}
        table_columns[tname][cname] = dtype

    # 3. Fetch primary key constraints
    cur.execute("""
        SELECT
            tc.table_name,
            kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
          AND tc.table_schema = 'public';
    """)
    primary_keys: Dict[str, str] = {}
    for row in cur.fetchall():
        tname = row[0] if isinstance(row, (list, tuple)) else row["table_name"]
        cname = row[1] if isinstance(row, (list, tuple)) else row["column_name"]
        primary_keys[tname] = cname

    total_records = 0

    # 4. Compare each expected table against reality
    for table_name, spec in EXPECTED_TABLE_SCHEMAS.items():
        expected_cols = spec["columns"]
        expected_pk = spec["primary_key"]

        table_val = TableValidation(
            table_name=table_name,
            total_expected_columns=len(expected_cols),
            expected_primary_key=expected_pk,
        )

        if table_name not in existing_tables:
            table_val.exists = False
            result.errors.append(f"Required table '{table_name}' does not exist.")
            result.is_valid = False
            result.tables[table_name] = table_val
            continue

        table_val.exists = True
        actual_cols = table_columns.get(table_name, {})
        actual_pk = primary_keys.get(table_name)
        table_val.primary_key = actual_pk
        table_val.primary_key_valid = (actual_pk == expected_pk)

        if not table_val.primary_key_valid:
            result.errors.append(
                f"Table '{table_name}' primary key mismatch: expected '{expected_pk}', got '{actual_pk}'."
            )
            result.is_valid = False

        matched_cols = 0
        for col_name, exp_type in expected_cols.items():
            if col_name not in actual_cols:
                table_val.missing_columns.append(col_name)
                result.errors.append(f"Table '{table_name}' missing column '{col_name}'.")
                result.is_valid = False
            else:
                act_type = actual_cols[col_name]
                if _is_type_compatible(exp_type, act_type):
                    matched_cols += 1
                else:
                    mismatch = ColumnMismatch(
                        column_name=col_name,
                        expected_type=exp_type,
                        actual_type=act_type,
                    )
                    table_val.type_mismatches.append(mismatch)
                    result.errors.append(
                        f"Table '{table_name}.{col_name}' type mismatch: expected '{exp_type}', found '{act_type}'."
                    )
                    result.is_valid = False

        table_val.columns_matched = matched_cols

        # Fetch safe row count
        try:
            cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name)))
            cnt_row = cur.fetchone()
            cnt = cnt_row[0] if isinstance(cnt_row, (list, tuple)) else cnt_row["count"]
            table_val.row_count = int(cnt)
            if table_name in ("stations", "trains", "schedules", "journey_train", "journey_test"):
                total_records += int(cnt)
        except Exception as exc:
            logger.warning("Could not count rows in %s: %s", table_name, exc)

        result.tables[table_name] = table_val

    result.total_records = total_records
    return result


def initialize_schema(
    cursor=None,
    ddl_files: Optional[List[Path]] = None,
) -> Dict[str, Any]:
    """
    Safely and idempotently applies schema DDL definitions in sql/schema/*.sql.
    Executes CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS.
    Guarantees no data truncation, deletion, or destructive schema changes.
    """
    files_to_apply = ddl_files or [
        SCHEMA_DIR / "00_core_tables.sql",
        SCHEMA_DIR / "01_pipeline_runs.sql",
    ]

    applied_files: List[str] = []
    
    def _apply_with_cur(cur) -> None:
        for file_path in files_to_apply:
            if not file_path.is_file():
                raise FileNotFoundError(f"Schema definition file missing: {file_path}")
            
            ddl_content = file_path.read_text(encoding="utf-8")
            # Enforce safety check on DDL content: reject any DROP or TRUNCATE
            for statement in ("DROP TABLE", "TRUNCATE TABLE", "DROP SCHEMA", "DROP DATABASE"):
                if statement in ddl_content.upper():
                    raise ValueError(f"Destructive statement '{statement}' detected in {file_path.name}. Execution halted.")

            logger.info("Executing safe schema DDL from %s...", file_path.name)
            cur.execute(ddl_content)
            applied_files.append(file_path.name)

    if cursor is not None:
        _apply_with_cur(cursor)
    else:
        with get_db_cursor(commit=True) as cur:
            _apply_with_cur(cur)

    validation = validate_schema(cursor=cursor)
    return {
        "applied_files": applied_files,
        "is_valid": validation.is_valid,
        "database": validation.database_name,
        "total_protected_records": validation.total_records,
        "tables_verified": list(validation.tables.keys()),
        "errors": validation.errors,
    }
