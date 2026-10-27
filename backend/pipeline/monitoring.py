"""
Pipeline Execution Monitoring & Audit Logging Service for RAIL / SIGNAL.

Provides authoritative execution tracking, idempotent schema management,
stage-level telemetry, error sanitization, and query services for pipeline runs.

Storage Architecture:
- Authoritative Store: PostgreSQL `pipeline_runs` table in database `rail_signal`.
- Redundant File Audit: `data/processed/pipeline_runs.jsonl` (append-only JSONL log).
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import psycopg2
import psycopg2.extras

from backend.app.config import settings
from backend.app.db import get_db_cursor

logger = logging.getLogger("rail_signal.monitoring")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [rail_signal.monitoring] %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIT_LOG_FILE = PROJECT_ROOT / "data" / "processed" / "pipeline_runs.jsonl"
SCHEMA_SQL_FILE = PROJECT_ROOT / "sql" / "schema" / "01_pipeline_runs.sql"

# Global lock for validation execution to prevent race conditions during rapid API calls
_validation_concurrency_lock = threading.Lock()

# Regex patterns to sanitize sensitive credentials from error logs
_SENSITIVE_PATTERNS = [
    (re.compile(r"password=([^\s;]+)", re.IGNORECASE), "password=***"),
    (re.compile(r"pwd=([^\s;]+)", re.IGNORECASE), "pwd=***"),
    (re.compile(r"(postgres(?:ql)?://[^:]+:)([^@]+)(@)", re.IGNORECASE), r"\1***\3"),
]


def sanitize_error_message(message: Any) -> str:
    """Removes passwords, connection credentials, and sensitive parameters from error logs."""
    if message is None:
        return ""
    text = str(message)
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text.strip()


def generate_run_id(prefix: str = "run") -> str:
    """Generates a concurrency-safe, chronologically sortable run ID."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    random_suffix = uuid.uuid4().hex[:8]
    return f"{prefix}_{timestamp}_{random_suffix}"


def ensure_pipeline_runs_table() -> None:
    """
    Idempotently verifies and creates the pipeline_runs table and required indexes
    in PostgreSQL if they do not yet exist.
    """
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        run_id VARCHAR(64) PRIMARY KEY,
        pipeline_name VARCHAR(128) NOT NULL,
        run_type VARCHAR(32) NOT NULL DEFAULT 'VALIDATION',
        trigger_type VARCHAR(32) NOT NULL DEFAULT 'MANUAL_API',
        status VARCHAR(32) NOT NULL DEFAULT 'RUNNING'
            CHECK (status IN ('PENDING', 'RUNNING', 'SUCCESS', 'FAILED')),
        start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        finish_time TIMESTAMPTZ,
        duration_seconds NUMERIC(10, 3),
        records_processed BIGINT NOT NULL DEFAULT 0,
        records_accepted BIGINT NOT NULL DEFAULT 0,
        records_quarantined BIGINT NOT NULL DEFAULT 0,
        current_stage VARCHAR(128),
        failed_stage VARCHAR(128),
        error_summary TEXT,
        stage_details JSONB NOT NULL DEFAULT '[]'::jsonb,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created_at ON pipeline_runs (created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs (status);
    CREATE INDEX IF NOT EXISTS idx_pipeline_runs_pipeline_name ON pipeline_runs (pipeline_name);
    CREATE INDEX IF NOT EXISTS idx_pipeline_runs_run_type ON pipeline_runs (run_type);
    """
    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute(create_table_sql)
        logger.info("Verified pipeline_runs table and indexes in PostgreSQL.")
    except Exception as exc:
        sanitized = sanitize_error_message(exc)
        logger.error("Failed to ensure pipeline_runs table: %s", sanitized)
        raise exc


def _append_audit_log_file(record: Dict[str, Any]) -> None:
    """Appends execution outcome to the secondary filesystem JSONL audit log."""
    try:
        AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception as exc:
        logger.warning("Could not append to JSONL audit log (%s): %s", AUDIT_LOG_FILE, exc)


@dataclass
class StageOutcome:
    """Stage-level execution outcome and record tallies."""
    stage_name: str
    status: str = "RUNNING"  # "RUNNING", "SUCCESS", "FAILED", "SKIPPED"
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ended_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    records_processed: int = 0
    records_accepted: int = 0
    records_quarantined: int = 0
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PipelineExecutionTracker:
    """
    Context manager and tracker for monitoring pipeline execution lifecycles.
    
    Guarantees:
    - Never leaves a record stuck in RUNNING status upon handled or unhandled failures.
    - Captures stage-by-stage timing and record counters.
    - Sanitizes all logged error strings.
    - Synchronizes with PostgreSQL as authoritative store and JSONL as append-only audit.
    """

    def __init__(
        self,
        pipeline_name: str,
        run_type: str = "VALIDATION",
        trigger_type: str = "MANUAL_API",
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.pipeline_name = pipeline_name
        self.run_type = run_type
        self.trigger_type = trigger_type
        self.run_id = run_id or generate_run_id()
        self.metadata = metadata or {}
        
        self.status = "RUNNING"
        self.start_time = datetime.now(timezone.utc)
        self.finish_time: Optional[datetime] = None
        self.duration_seconds: Optional[float] = None
        
        self.records_processed = 0
        self.records_accepted = 0
        self.records_quarantined = 0
        
        self.current_stage: Optional[str] = None
        self.failed_stage: Optional[str] = None
        self.error_summary: Optional[str] = None
        
        self.stage_outcomes: List[StageOutcome] = []
        self._current_stage_start: Optional[datetime] = None
        self._is_completed = False

    def __enter__(self) -> PipelineExecutionTracker:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_val is not None and not self._is_completed:
            self.fail(
                error_message=str(exc_val),
                failed_stage=self.current_stage or "unknown_stage",
            )
        elif not self._is_completed:
            self.succeed()

    def start(self) -> None:
        """Initializes the pipeline run record in PostgreSQL."""
        ensure_pipeline_runs_table()
        insert_sql = """
        INSERT INTO pipeline_runs (
            run_id, pipeline_name, run_type, trigger_type, status,
            start_time, current_stage, stage_details, metadata, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, NOW(), NOW()
        );
        """
        try:
            with get_db_cursor(commit=True) as cur:
                cur.execute(
                    insert_sql,
                    (
                        self.run_id,
                        self.pipeline_name,
                        self.run_type,
                        self.trigger_type,
                        self.status,
                        self.start_time,
                        self.current_stage,
                        psycopg2.extras.Json([s.to_dict() for s in self.stage_outcomes]),
                        psycopg2.extras.Json(self.metadata),
                    ),
                )
            logger.info("Initialized pipeline run %s ('%s', %s)", self.run_id, self.pipeline_name, self.run_type)
        except Exception as exc:
            sanitized = sanitize_error_message(exc)
            logger.warning("Failed to persist initial pipeline run %s in database: %s", self.run_id, sanitized)

    def start_stage(self, stage_name: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Begins tracking a named execution stage."""
        now_dt = datetime.now(timezone.utc)
        self.current_stage = stage_name
        self._current_stage_start = now_dt
        
        stage = StageOutcome(
            stage_name=stage_name,
            status="RUNNING",
            started_at=now_dt.isoformat(),
            details=details or {},
        )
        self.stage_outcomes.append(stage)
        
        self._update_db(current_stage=stage_name)
        logger.info("Started stage '%s' for run %s", stage_name, self.run_id)

    def finish_stage(
        self,
        stage_name: str,
        status: str = "SUCCESS",
        records_processed: int = 0,
        records_accepted: int = 0,
        records_quarantined: int = 0,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Completes tracking of the specified stage."""
        now_dt = datetime.now(timezone.utc)
        duration: Optional[float] = None
        if self._current_stage_start:
            duration = round((now_dt - self._current_stage_start).total_seconds(), 3)

        # Locate stage outcome object
        for s in reversed(self.stage_outcomes):
            if s.stage_name == stage_name:
                s.status = status
                s.ended_at = now_dt.isoformat()
                s.duration_seconds = duration
                s.records_processed = records_processed
                s.records_accepted = records_accepted
                s.records_quarantined = records_quarantined
                if details:
                    s.details.update(details)
                if error:
                    s.error = sanitize_error_message(error)
                break

        # Accumulate metrics
        self.records_processed += records_processed
        self.records_accepted += records_accepted
        self.records_quarantined += records_quarantined

        self._update_db()
        logger.info("Finished stage '%s' (%s, %.3fs) for run %s", stage_name, status, duration or 0.0, self.run_id)

    def succeed(self, details: Optional[Dict[str, Any]] = None) -> None:
        """Marks the overall pipeline execution as successfully completed."""
        if self._is_completed:
            return
        now_dt = datetime.now(timezone.utc)
        self.finish_time = now_dt
        self.duration_seconds = round((now_dt - self.start_time).total_seconds(), 3)
        self.status = "SUCCESS"
        self.current_stage = None
        if details:
            self.metadata.update(details)
        self._is_completed = True

        self._update_db(is_final=True)
        self._write_audit_record()
        logger.info("Pipeline run %s SUCCESS (duration: %.3fs)", self.run_id, self.duration_seconds)

    def fail(self, error_message: str, failed_stage: Optional[str] = None) -> None:
        """Marks the overall pipeline execution as failed with sanitized diagnostics."""
        if self._is_completed:
            return
        now_dt = datetime.now(timezone.utc)
        self.finish_time = now_dt
        self.duration_seconds = round((now_dt - self.start_time).total_seconds(), 3)
        self.status = "FAILED"
        self.failed_stage = failed_stage or self.current_stage
        self.error_summary = sanitize_error_message(error_message)
        
        # If active stage is still RUNNING, mark it FAILED
        if self.current_stage:
            for s in reversed(self.stage_outcomes):
                if s.stage_name == self.current_stage and s.status == "RUNNING":
                    s.status = "FAILED"
                    s.ended_at = now_dt.isoformat()
                    s.error = self.error_summary
                    if self._current_stage_start:
                        s.duration_seconds = round((now_dt - self._current_stage_start).total_seconds(), 3)
                    break
        
        self.current_stage = None
        self._is_completed = True

        self._update_db(is_final=True)
        self._write_audit_record()
        logger.error("Pipeline run %s FAILED at '%s': %s", self.run_id, self.failed_stage, self.error_summary)

    def _update_db(self, current_stage: Optional[str] = None, is_final: bool = False) -> None:
        """Persists intermediate or final execution telemetry to PostgreSQL."""
        update_sql = """
        UPDATE pipeline_runs
        SET
            status = %s,
            finish_time = %s,
            duration_seconds = %s,
            records_processed = %s,
            records_accepted = %s,
            records_quarantined = %s,
            current_stage = %s,
            failed_stage = %s,
            error_summary = %s,
            stage_details = %s,
            metadata = %s,
            updated_at = NOW()
        WHERE run_id = %s;
        """
        try:
            with get_db_cursor(commit=True) as cur:
                cur.execute(
                    update_sql,
                    (
                        self.status,
                        self.finish_time,
                        self.duration_seconds,
                        self.records_processed,
                        self.records_accepted,
                        self.records_quarantined,
                        current_stage or self.current_stage,
                        self.failed_stage,
                        self.error_summary,
                        psycopg2.extras.Json([s.to_dict() for s in self.stage_outcomes]),
                        psycopg2.extras.Json(self.metadata),
                        self.run_id,
                    ),
                )
        except Exception as exc:
            sanitized = sanitize_error_message(exc)
            logger.warning("Failed to update pipeline run %s in database: %s", self.run_id, sanitized)

    def _write_audit_record(self) -> None:
        """Writes execution summary to local JSONL file."""
        record = {
            "run_id": self.run_id,
            "pipeline_name": self.pipeline_name,
            "run_type": self.run_type,
            "trigger_type": self.trigger_type,
            "status": self.status,
            "start_time": self.start_time.isoformat(),
            "finish_time": self.finish_time.isoformat() if self.finish_time else None,
            "duration_seconds": self.duration_seconds,
            "records_processed": self.records_processed,
            "records_accepted": self.records_accepted,
            "records_quarantined": self.records_quarantined,
            "failed_stage": self.failed_stage,
            "error_summary": self.error_summary,
            "stage_details": [s.to_dict() for s in self.stage_outcomes],
            "metadata": self.metadata,
        }
        _append_audit_log_file(record)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "pipeline_name": self.pipeline_name,
            "run_type": self.run_type,
            "trigger_type": self.trigger_type,
            "status": self.status,
            "start_time": self.start_time,
            "finish_time": self.finish_time,
            "duration_seconds": self.duration_seconds,
            "records_processed": self.records_processed,
            "records_accepted": self.records_accepted,
            "records_quarantined": self.records_quarantined,
            "current_stage": self.current_stage,
            "failed_stage": self.failed_stage,
            "error_summary": self.error_summary,
            "stage_details": [s.to_dict() for s in self.stage_outcomes],
            "metadata": self.metadata,
        }


# ==============================================================================
# Safe Validation-Only Pipeline Execution Routine
# ==============================================================================

def execute_validation_pipeline(
    trigger_type: str = "MANUAL_API",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes a safe, non-destructive validation-only pipeline run.
    
    Verifies:
    1. Environment & configuration prerequisites.
    2. Raw dataset file existence and file integrity.
    3. PostgreSQL connectivity and baseline table counts.
    4. Processed Parquet storage and quality report artifacts.

    Guarantees:
    - Never modifies, reloads, or deletes existing PostgreSQL data tables.
    - Persists actual stage-by-stage outcomes into PostgreSQL `pipeline_runs`.
    - Explicitly badges run_type as 'VALIDATION'.
    """
    if not _validation_concurrency_lock.acquire(blocking=False):
        raise RuntimeError("Another pipeline execution is already in progress. Please wait for it to complete.")

    try:
        tracker = PipelineExecutionTracker(
            pipeline_name="RAIL / SIGNAL Validation Pipeline",
            run_type="VALIDATION",
            trigger_type=trigger_type,
            metadata=metadata or {},
        )

        with tracker:
            # -------------------------------------------------------------
            # Stage 1: Environment & Config
            # -------------------------------------------------------------
            tracker.start_stage("01_environment_and_config")
            env_file = PROJECT_ROOT / ".env"
            has_env = env_file.is_file()
            config_details = {
                "env_file_present": has_env,
                "postgres_host": settings.postgres_host,
                "postgres_port": settings.postgres_port,
                "postgres_db": settings.postgres_db,
                "app_version": settings.app_version,
            }
            if not settings.postgres_db:
                raise ValueError("POSTGRES_DB configuration setting is missing.")
            tracker.finish_stage("01_environment_and_config", status="SUCCESS", details=config_details)

            # -------------------------------------------------------------
            # Stage 2: Raw Datasets Verification
            # -------------------------------------------------------------
            tracker.start_stage("02_raw_datasets_verification")
            raw_dir = PROJECT_ROOT / "data" / "raw"
            required_raw_files = {
                "stations": raw_dir / "datameet" / "stations.json",
                "trains": raw_dir / "datameet" / "trains.json",
                "schedules": raw_dir / "datameet" / "schedules.json",
                "journey_train": raw_dir / "operational_journeys" / "ir_train.csv",
                "journey_test": raw_dir / "operational_journeys" / "ir_test.csv",
            }
            raw_details: Dict[str, Any] = {}
            missing_files: List[str] = []
            for name, path in required_raw_files.items():
                if path.is_file():
                    raw_details[name] = {"path": str(path.relative_to(PROJECT_ROOT)), "size_bytes": path.stat().st_size}
                else:
                    missing_files.append(name)

            if missing_files:
                err_msg = f"Missing required raw source files: {', '.join(missing_files)}"
                tracker.finish_stage(
                    "02_raw_datasets_verification",
                    status="FAILED",
                    details=raw_details,
                    error=err_msg,
                )
                raise FileNotFoundError(err_msg)

            tracker.finish_stage(
                "02_raw_datasets_verification",
                status="SUCCESS",
                details={"verified_datasets": raw_details, "all_present": True},
            )

            # -------------------------------------------------------------
            # Stage 3: PostgreSQL Database Connectivity & Row Counts
            # -------------------------------------------------------------
            tracker.start_stage("03_database_connectivity_and_integrity")
            db_counts: Dict[str, int] = {}
            with get_db_cursor() as cur:
                for table in ("stations", "trains", "schedules", "journey_train", "journey_test"):
                    cur.execute(f"SELECT COUNT(*) AS cnt FROM {table};")
                    db_counts[table] = int(cur.fetchone()["cnt"])

            total_db_rows = sum(db_counts.values())
            db_details = {
                "database": settings.postgres_db,
                "table_counts": db_counts,
                "total_rows_verified": total_db_rows,
                "expected_baseline": 2283664,
                "matches_baseline": total_db_rows == 2283664,
            }
            tracker.finish_stage(
                "03_database_connectivity_and_integrity",
                status="SUCCESS",
                records_processed=total_db_rows,
                records_accepted=total_db_rows,
                details=db_details,
            )

            # -------------------------------------------------------------
            # Stage 4: Processed Storage Artifacts Verification
            # -------------------------------------------------------------
            tracker.start_stage("04_storage_artifacts_verification")
            proc_dir = PROJECT_ROOT / "data" / "processed"
            parquet_files = {
                "stations": proc_dir / "stations.parquet",
                "trains": proc_dir / "trains.parquet",
                "schedules": proc_dir / "schedules.parquet",
                "journey_train": proc_dir / "journey_train.parquet",
                "journey_test": proc_dir / "journey_test.parquet",
            }
            proc_details: Dict[str, Any] = {}
            missing_parquet: List[str] = []
            for name, p_path in parquet_files.items():
                if p_path.is_file():
                    proc_details[name] = {"path": str(p_path.relative_to(PROJECT_ROOT)), "size_bytes": p_path.stat().st_size}
                else:
                    missing_parquet.append(name)

            quality_report_file = proc_dir / "quality_report.json"
            proc_details["quality_report_exists"] = quality_report_file.is_file()

            if missing_parquet:
                err_msg = f"Missing processed Parquet files: {', '.join(missing_parquet)}"
                tracker.finish_stage(
                    "04_storage_artifacts_verification",
                    status="FAILED",
                    details=proc_details,
                    error=err_msg,
                )
                raise FileNotFoundError(err_msg)

            tracker.finish_stage(
                "04_storage_artifacts_verification",
                status="SUCCESS",
                details=proc_details,
            )

        return tracker.to_dict()

    finally:
        _validation_concurrency_lock.release()


# ==============================================================================
# Execution History Query Functions
# ==============================================================================

def get_pipeline_runs(
    page: int = 1,
    page_size: int = 10,
    status: Optional[str] = None,
    run_type: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Retrieves a paginated list of historical pipeline execution runs from PostgreSQL.
    """
    ensure_pipeline_runs_table()
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    offset = (page - 1) * page_size

    filters: List[str] = []
    params: List[Any] = []

    if status and status.strip():
        filters.append("status = %s")
        params.append(status.strip().upper())

    if run_type and run_type.strip():
        filters.append("run_type = %s")
        params.append(run_type.strip().upper())

    where_clause = ("WHERE " + " AND ".join(filters)) if filters else ""

    with get_db_cursor() as cur:
        # Count total matches
        count_sql = f"SELECT COUNT(*) AS total FROM pipeline_runs {where_clause};"
        cur.execute(count_sql, params)
        total_count = int(cur.fetchone()["total"])

        # Fetch page
        data_sql = f"""
        SELECT
            run_id, pipeline_name, run_type, trigger_type, status,
            start_time, finish_time, duration_seconds,
            records_processed, records_accepted, records_quarantined,
            current_stage, failed_stage, error_summary,
            jsonb_array_length(stage_details) AS stage_count,
            created_at, updated_at
        FROM pipeline_runs
        {where_clause}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s;
        """
        cur.execute(data_sql, params + [page_size, offset])
        rows = cur.fetchall()

        return [dict(r) for r in rows], total_count


def get_pipeline_run_by_id(run_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves complete execution details for a specific pipeline run by run_id.
    """
    ensure_pipeline_runs_table()
    clean_id = run_id.strip()
    with get_db_cursor() as cur:
        query = """
        SELECT
            run_id, pipeline_name, run_type, trigger_type, status,
            start_time, finish_time, duration_seconds,
            records_processed, records_accepted, records_quarantined,
            current_stage, failed_stage, error_summary,
            stage_details, metadata, created_at, updated_at
        FROM pipeline_runs
        WHERE run_id = %s
        LIMIT 1;
        """
        cur.execute(query, (clean_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_pipeline_history_stats() -> Dict[str, Any]:
    """
    Computes database-wide aggregate metrics across all historical pipeline executions.
    """
    ensure_pipeline_runs_table()
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(*) AS total_runs,
                COUNT(*) FILTER (WHERE status = 'SUCCESS') AS successful_runs,
                COUNT(*) FILTER (WHERE status = 'FAILED') AS failed_runs,
                COUNT(*) FILTER (WHERE status = 'RUNNING') AS running_runs
            FROM pipeline_runs;
        """)
        agg = cur.fetchone()

        cur.execute("""
            SELECT status, start_time, duration_seconds
            FROM pipeline_runs
            ORDER BY created_at DESC
            LIMIT 1;
        """)
        latest = cur.fetchone()

        return {
            "total_runs": int(agg["total_runs"] or 0),
            "successful_runs": int(agg["successful_runs"] or 0),
            "failed_runs": int(agg["failed_runs"] or 0),
            "running_runs": int(agg["running_runs"] or 0),
            "latest_run_status": latest["status"] if latest else None,
            "latest_run_timestamp": latest["start_time"] if latest else None,
            "latest_run_duration_seconds": float(latest["duration_seconds"]) if latest and latest["duration_seconds"] is not None else None,
        }
