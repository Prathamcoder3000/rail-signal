"""
Unified ETL Orchestration Engine for RAIL / SIGNAL.

Coordinates the end-to-end data lifecycle:
1. Preflight and environment validation
2. Schema validation and idempotent initialization
3. Ingestion and quality quarantine validation
4. Transformation and atomic Parquet generation
5. Safe database loading with overwrite protection
6. Post-load verification and execution observability

Interfaces:
- CLI: `python -m backend.pipeline.orchestrator --mode <mode> [options]`
- Python API: `ETLOrchestrator(config).run()`
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import signal
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import psycopg2
from psycopg2 import sql

from backend.app.config import settings
from backend.app.db import get_db_cursor
from backend.app.logging_config import configure_logging
from backend.pipeline.advisory_lock import (
    AdvisoryLockConnectionError,
    AdvisoryLockContentionError,
    acquire_pipeline_advisory_lock,
    assert_pipeline_advisory_lock_held,
)
from backend.pipeline.database_loader import (
    BATCH_SIZE,
    DATASETS as LOADER_DATASETS,
    load_dataset,
)
from backend.pipeline.monitoring import (
    PipelineExecutionTracker,
    generate_run_id,
    sanitize_error_message,
)
from backend.pipeline.schema_manager import (
    initialize_schema,
    validate_schema,
)
from backend.pipeline.transformation import (
    execute_transformation_pipeline,
)

logger = logging.getLogger("rail_signal.orchestrator")

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class OrchestrationMode(str, Enum):
    PREFLIGHT = "preflight"
    INSPECT = "inspect"
    SCHEMA_VALIDATE = "schema-validate"
    SCHEMA_INIT = "schema-init"
    VALIDATE = "validate"
    ETL = "etl"
    RUN = "run"


@dataclass
class OrchestratorConfig:
    mode: OrchestrationMode = OrchestrationMode.PREFLIGHT
    raw_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "raw")
    processed_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "processed")
    dry_run: bool = False
    keep_dry_run_artifacts: bool = False
    allow_data_replace: bool = False
    max_journey_chunks: Optional[int] = None
    chunk_size: int = 100_000
    trigger_type: str = "CLI"
    json_output: bool = False
    quiet: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["mode"] = self.mode.value
        d["raw_dir"] = str(self.raw_dir)
        d["processed_dir"] = str(self.processed_dir)
        return d


class OrchestratorPreflightError(Exception):
    """Raised when environment or filesystem prerequisites fail."""
    pass


class OrchestratorSchemaError(Exception):
    """Raised when database schema validation fails."""
    pass


class OrchestratorDataSafetyError(Exception):
    """Raised when an operation would unsafely modify or duplicate protected data."""
    pass


class OrchestratorExecutionError(Exception):
    """Raised when an ETL stage execution fails."""
    pass


class ETLOrchestrator:
    """
    Unified Orchestrator coordinating all RAIL / SIGNAL ETL stages with
    strict data safety, transaction boundaries, advisory locking, and observability.
    """

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig()
        configure_logging(quiet=self.config.quiet)
        self._interrupted = False

    def _check_interrupted(self) -> None:
        if self._interrupted:
            raise KeyboardInterrupt("Pipeline execution interrupted by user (SIGINT/Ctrl+C).")

    def run(self) -> Dict[str, Any]:
        """
        Executes the requested orchestration workflow in dependency order.
        Guarantees session-level advisory locking for mutating workflows.
        """
        mode = self.config.mode
        normalized_mode = mode.value if isinstance(mode, OrchestrationMode) else str(mode).lower()

        # Signal interception setup
        prev_sigint = None
        prev_sigterm = None
        def _sig_handler(signum, frame):
            self._interrupted = True
            logger.warning("Interrupt signal received (signum=%s). Initiating graceful shutdown...", signum)

        try:
            prev_sigint = signal.signal(signal.SIGINT, _sig_handler)
            if hasattr(signal, "SIGTERM"):
                prev_sigterm = signal.signal(signal.SIGTERM, _sig_handler)
        except (ValueError, AttributeError):
            pass

        try:
            # Modes that modify shared artifacts or database require the advisory lock
            needs_lock = normalized_mode in ("etl", "run", "validate", "schema-init")
            if needs_lock:
                try:
                    with acquire_pipeline_advisory_lock():
                        return self._dispatch_flow(normalized_mode)
                except AdvisoryLockContentionError as lock_err:
                    err_msg = str(lock_err)
                    logger.error("Concurrency Contention: %s", err_msg)
                    raise OrchestratorExecutionError(err_msg) from lock_err
                except AdvisoryLockConnectionError as conn_err:
                    err_msg = str(conn_err)
                    logger.error("Lock Connection Failure: %s", err_msg)
                    if "Could not connect to database for advisory lock" in err_msg or "Could not configure autocommit" in err_msg:
                        raise OrchestratorPreflightError(err_msg) from conn_err
                    raise OrchestratorExecutionError(err_msg) from conn_err
            else:
                return self._dispatch_flow(normalized_mode)
        finally:
            # Restore previous signal handlers
            try:
                if prev_sigint is not None:
                    signal.signal(signal.SIGINT, prev_sigint)
                if prev_sigterm is not None and hasattr(signal, "SIGTERM"):
                    signal.signal(signal.SIGTERM, prev_sigterm)
            except (ValueError, AttributeError):
                pass

    def _dispatch_flow(self, normalized_mode: str) -> Dict[str, Any]:
        if normalized_mode in ("preflight", "inspect"):
            return self._execute_preflight_flow()
        elif normalized_mode == "schema-validate":
            return self._execute_schema_validate_flow()
        elif normalized_mode == "schema-init":
            return self._execute_schema_init_flow()
        elif normalized_mode == "validate":
            return self._execute_validation_flow()
        elif normalized_mode in ("etl", "run"):
            return self._execute_etl_flow()
        else:
            raise ValueError(f"Unsupported orchestration mode: '{normalized_mode}'")

    # =========================================================================
    # Mode 1: Preflight / Inspect Flow
    # =========================================================================
    def _execute_preflight_flow(self) -> Dict[str, Any]:
        logger.info("Starting PREFLIGHT audit flow...")
        tracker = PipelineExecutionTracker(
            pipeline_name="rail_signal_preflight",
            run_type="INSPECT",
            trigger_type=self.config.trigger_type,
            metadata={"config": self.config.to_dict()},
        )
        with tracker:
            self._check_interrupted()
            # Stage 1: Environment & Config
            tracker.start_stage("01_preflight_and_config")
            config_report = self._check_environment_and_config()
            tracker.finish_stage(
                "01_preflight_and_config",
                status="SUCCESS",
                details=config_report,
            )

            self._check_interrupted()
            # Stage 2: Filesystem Datasets Audit
            tracker.start_stage("02_filesystem_prerequisites")
            fs_report = self._check_filesystem_prerequisites()
            tracker.finish_stage(
                "02_filesystem_prerequisites",
                status="SUCCESS",
                details=fs_report,
            )

            self._check_interrupted()
            # Stage 3: Database Connectivity and Schema Summary
            tracker.start_stage("03_database_connectivity_and_schema")
            db_report = self._check_database_readiness()
            tracker.finish_stage(
                "03_database_connectivity_and_schema",
                status="SUCCESS",
                details=db_report,
            )

        summary = self._build_run_summary(tracker, {
            "config": config_report,
            "filesystem": fs_report,
            "database": db_report,
        })
        logger.info("PREFLIGHT completed successfully: all prerequisites verified.")
        return summary

    # =========================================================================
    # Mode 2: Schema Validate Flow
    # =========================================================================
    def _execute_schema_validate_flow(self) -> Dict[str, Any]:
        logger.info("Starting SCHEMA-VALIDATE flow...")
        tracker = PipelineExecutionTracker(
            pipeline_name="rail_signal_schema_validate",
            run_type="SCHEMA_VALIDATE",
            trigger_type=self.config.trigger_type,
            metadata={"config": self.config.to_dict()},
        )
        with tracker:
            self._check_interrupted()
            tracker.start_stage("01_preflight_and_config")
            config_report = self._check_environment_and_config()
            tracker.finish_stage("01_preflight_and_config", status="SUCCESS", details=config_report)

            self._check_interrupted()
            tracker.start_stage("02_schema_validation")
            validation = validate_schema()
            val_dict = validation.to_dict()

            if not validation.is_valid:
                err_msg = f"Schema validation failed: {'; '.join(validation.errors)}"
                tracker.finish_stage(
                    "02_schema_validation",
                    status="FAILED",
                    details=val_dict,
                    error=err_msg,
                )
                raise OrchestratorSchemaError(err_msg)

            tracker.finish_stage(
                "02_schema_validation",
                status="SUCCESS",
                records_processed=validation.total_records,
                records_accepted=validation.total_records,
                details=val_dict,
            )

        summary = self._build_run_summary(tracker, {"schema_validation": val_dict})
        logger.info("SCHEMA-VALIDATE completed successfully: all tables, columns, types, and primary keys verified.")
        return summary

    # =========================================================================
    # Mode 3: Schema Init Flow
    # =========================================================================
    def _execute_schema_init_flow(self) -> Dict[str, Any]:
        logger.info("Starting SCHEMA-INIT flow...")
        tracker = PipelineExecutionTracker(
            pipeline_name="rail_signal_schema_init",
            run_type="SCHEMA_INIT",
            trigger_type=self.config.trigger_type,
            metadata={"config": self.config.to_dict()},
        )
        with tracker:
            self._check_interrupted()
            tracker.start_stage("01_preflight_and_config")
            config_report = self._check_environment_and_config()
            tracker.finish_stage("01_preflight_and_config", status="SUCCESS", details=config_report)

            self._check_interrupted()
            tracker.start_stage("02_idempotent_schema_init")
            # Verify advisory lock session liveness before executing DDL
            assert_pipeline_advisory_lock_held()
            init_res = initialize_schema()
            if not init_res.get("is_valid", False):
                err_msg = f"Schema initialization failed verification: {'; '.join(init_res.get('errors', []))}"
                tracker.finish_stage(
                    "02_idempotent_schema_init",
                    status="FAILED",
                    details=init_res,
                    error=err_msg,
                )
                raise OrchestratorSchemaError(err_msg)

            tracker.finish_stage(
                "02_idempotent_schema_init",
                status="SUCCESS",
                details=init_res,
            )

        summary = self._build_run_summary(tracker, {"schema_init": init_res})
        logger.info("SCHEMA-INIT completed successfully: DDL applied idempotently and verified.")
        return summary

    # =========================================================================
    # Mode 4: Validation Flow
    # =========================================================================
    def _execute_validation_flow(self) -> Dict[str, Any]:
        logger.info("Starting PIPELINE VALIDATION flow...")
        tracker = PipelineExecutionTracker(
            pipeline_name="rail_signal_validation",
            run_type="VALIDATION",
            trigger_type=self.config.trigger_type,
            metadata={"config": self.config.to_dict()},
        )
        with tracker:
            self._check_interrupted()
            # Stage 1: Environment & Config
            tracker.start_stage("01_environment_and_config")
            config_report = self._check_environment_and_config()
            tracker.finish_stage("01_environment_and_config", status="SUCCESS", details=config_report)

            self._check_interrupted()
            # Stage 2: Raw Datasets Verification
            tracker.start_stage("02_raw_datasets_verification")
            raw_report = self._check_filesystem_prerequisites()
            tracker.finish_stage("02_raw_datasets_verification", status="SUCCESS", details=raw_report)

            self._check_interrupted()
            # Stage 3: Database Connectivity and Row Verification
            tracker.start_stage("03_database_connectivity_and_integrity")
            val_res = validate_schema()
            if not val_res.is_valid:
                err_msg = f"Database schema validation failed: {'; '.join(val_res.errors)}"
                tracker.finish_stage("03_database_connectivity_and_integrity", status="FAILED", details=val_res.to_dict(), error=err_msg)
                raise OrchestratorSchemaError(err_msg)

            db_counts = {t: val.row_count for t, val in val_res.tables.items()}
            total_db_rows = val_res.total_records
            tracker.finish_stage(
                "03_database_connectivity_and_integrity",
                status="SUCCESS",
                records_processed=total_db_rows,
                records_accepted=total_db_rows,
                details={
                    "database": val_res.database_name,
                    "table_counts": db_counts,
                    "total_rows_verified": total_db_rows,
                },
            )

            self._check_interrupted()
            # Stage 4: Processed Storage Artifacts Verification
            tracker.start_stage("04_storage_artifacts_verification")
            storage_report = self._check_storage_artifacts()
            tracker.finish_stage("04_storage_artifacts_verification", status="SUCCESS", details=storage_report)

        summary = self._build_run_summary(tracker, {
            "config": config_report,
            "raw_datasets": raw_report,
            "database_counts": db_counts,
            "storage_artifacts": storage_report,
        })
        logger.info("PIPELINE VALIDATION completed successfully: all components verified.")
        return summary

    # =========================================================================
    # Mode 5: Full ETL Execution Flow
    # =========================================================================
    def _execute_etl_flow(self) -> Dict[str, Any]:
        """
        Coordinates full ETL pipeline execution in strict dependency order:
        Stage 1: Preflight & Environment
        Stage 2: Schema Validation
        Stage 3: Transformation & Parquet Generation (with Quality Quarantine)
        Stage 4: Database Loading (Single Transaction, Overwrite Guard)
        Stage 5: Post-Load Row & Index Verification
        """
        logger.info("Initiating Full ETL Pipeline Execution...")
        tracker = PipelineExecutionTracker(
            pipeline_name="rail_signal_orchestrator",
            run_type="FULL_ETL",
            trigger_type=self.config.trigger_type,
            metadata={"config": self.config.to_dict()},
        )

        dry_run_temp_dir: Optional[str] = None
        effective_processed_dir = self.config.processed_dir

        if self.config.dry_run:
            dry_run_temp_dir = tempfile.mkdtemp(prefix="rail_signal_dryrun_")
            effective_processed_dir = Path(dry_run_temp_dir)
            logger.info("[DRY RUN] Isolated workspace initialized: %s", effective_processed_dir)

        try:
            with tracker:
                self._check_interrupted()
                # -----------------------------------------------------------------
                # Stage 1: Preflight & Environment
                # -----------------------------------------------------------------
                tracker.start_stage("01_preflight_and_config")
                config_report = self._check_environment_and_config()
                fs_report = self._check_filesystem_prerequisites()
                tracker.finish_stage(
                    "01_preflight_and_config",
                    status="SUCCESS",
                    details={"config": config_report, "filesystem": fs_report},
                )

                self._check_interrupted()
                # -----------------------------------------------------------------
                # Stage 2: Schema Validation
                # -----------------------------------------------------------------
                tracker.start_stage("02_schema_validation")
                val_res = validate_schema()
                if not val_res.is_valid:
                    err_msg = f"Schema validation failed: {'; '.join(val_res.errors)}"
                    tracker.finish_stage("02_schema_validation", status="FAILED", details=val_res.to_dict(), error=err_msg)
                    raise OrchestratorSchemaError(err_msg)

                tracker.finish_stage(
                    "02_schema_validation",
                    status="SUCCESS",
                    records_processed=val_res.total_records,
                    records_accepted=val_res.total_records,
                    details=val_res.to_dict(),
                )

                # -----------------------------------------------------------------
                # Overwrite & Idempotency Safeguard Check
                # -----------------------------------------------------------------
                existing_counts = {t: val.row_count for t, val in val_res.tables.items() if t in LOADER_DATASETS}
                has_existing_data = any(cnt > 0 for cnt in existing_counts.values())

                if has_existing_data and not self.config.allow_data_replace and not self.config.dry_run:
                    err_msg = (
                        f"ETL Load Guard: Target database '{val_res.database_name}' already contains "
                        f"{val_res.total_records:,} protected records across tables ({existing_counts}). "
                        "Halting ETL load to prevent data duplication or unapproved overwrite. "
                        "To explicitly authorize replacing data, specify --allow-data-replace or use --dry-run."
                    )
                    logger.error(err_msg)
                    tracker.fail(err_msg, failed_stage="02_schema_validation")
                    raise OrchestratorDataSafetyError(err_msg)

                self._check_interrupted()
                # -----------------------------------------------------------------
                # Stage 3: Transformation & Parquet Generation (with Quarantine)
                # -----------------------------------------------------------------
                tracker.start_stage("03_transformation_and_parquet")
                logger.info("Executing dataset transformations (output_dir=%s)...", effective_processed_dir)
                quality_report = execute_transformation_pipeline(
                    raw_dir=self.config.raw_dir,
                    processed_dir=effective_processed_dir,
                    chunk_size=self.config.chunk_size,
                    max_journey_chunks=self.config.max_journey_chunks,
                )
                total_accepted = sum(quality_report.accepted_counts.values())
                total_quarantined = sum(quality_report.quarantined_counts.values())
                total_processed = total_accepted + total_quarantined

                tracker.finish_stage(
                    "03_transformation_and_parquet",
                    status="SUCCESS",
                    records_processed=total_processed,
                    records_accepted=total_accepted,
                    records_quarantined=total_quarantined,
                    details={
                        "accepted_counts": quality_report.accepted_counts,
                        "quarantined_counts": quality_report.quarantined_counts,
                        "rejection_reasons": quality_report.rejection_reasons,
                        "output_artifacts": quality_report.outputs,
                        "isolated_workspace": str(effective_processed_dir) if self.config.dry_run else None,
                    },
                )

                self._check_interrupted()
                # -----------------------------------------------------------------
                # Stage 4: Database Loading (Single Transaction, Atomic)
                # -----------------------------------------------------------------
                tracker.start_stage("04_database_loading")
                if self.config.dry_run:
                    logger.info("[DRY RUN] Skipping database load stage; no records written.")
                    tracker.finish_stage(
                        "04_database_loading",
                        status="SUCCESS",
                        details={"dry_run": True, "message": "Database load skipped due to dry_run mode."},
                    )
                else:
                    # Detect lost lock session before beginning database writes
                    assert_pipeline_advisory_lock_held()
                    load_summary = self._load_datasets_to_database(quality_report.accepted_counts)
                    tracker.finish_stage(
                        "04_database_loading",
                        status="SUCCESS",
                        records_processed=load_summary["total_loaded"],
                        records_accepted=load_summary["total_loaded"],
                        details=load_summary,
                    )

                self._check_interrupted()
                # -----------------------------------------------------------------
                # Stage 5: Post-Load Verification
                # -----------------------------------------------------------------
                tracker.start_stage("05_post_load_verification")
                post_val = validate_schema()
                if not post_val.is_valid:
                    err_msg = f"Post-load schema verification failed: {'; '.join(post_val.errors)}"
                    tracker.finish_stage("05_post_load_verification", status="FAILED", details=post_val.to_dict(), error=err_msg)
                    raise OrchestratorExecutionError(err_msg)

                tracker.finish_stage(
                    "05_post_load_verification",
                    status="SUCCESS",
                    records_processed=post_val.total_records,
                    records_accepted=post_val.total_records,
                    details={
                        "total_records_in_db": post_val.total_records,
                        "table_counts": {t: v.row_count for t, v in post_val.tables.items()},
                    },
                )

            summary = self._build_run_summary(tracker, {
                "transformation": quality_report.to_dict() if "quality_report" in locals() else None,
                "post_load_records": post_val.total_records if "post_val" in locals() else None,
                "isolated_dry_run_workspace": str(effective_processed_dir) if self.config.dry_run else None,
            })
            logger.info("Full ETL Pipeline completed successfully (Run ID: %s).", tracker.run_id)
            return summary

        finally:
            # Clean up isolated dry-run artifacts unless user explicitly requested to retain them
            if dry_run_temp_dir and not self.config.keep_dry_run_artifacts:
                try:
                    shutil.rmtree(dry_run_temp_dir, ignore_errors=True)
                    logger.info("[DRY RUN] Cleaned up temporary workspace: %s", dry_run_temp_dir)
                except Exception as clean_err:
                    logger.warning("[DRY RUN] Failed to clean up temp workspace: %s", clean_err)

    # =========================================================================
    # Helpers & Validation Subroutines
    # =========================================================================
    def _check_environment_and_config(self) -> Dict[str, Any]:
        """Validates configuration parameters and environment variables."""
        env_file = PROJECT_ROOT / ".env"
        has_env = env_file.is_file()

        required_keys = ["POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"]
        missing_keys = []
        for k in required_keys:
            val = os.environ.get(k) or getattr(settings, k.lower(), None)
            if not val or val == "YOUR_ACTUAL_POSTGRES_PASSWORD":
                missing_keys.append(k)

        if missing_keys:
            raise OrchestratorPreflightError(
                f"Missing required database settings: {', '.join(missing_keys)}. Configure in .env first."
            )

        return {
            "env_file_present": has_env,
            "postgres_host": settings.postgres_host,
            "postgres_port": settings.postgres_port,
            "postgres_db": settings.postgres_db,
            "postgres_user": settings.postgres_user,
            "app_version": settings.app_version,
            "raw_dir": str(self.config.raw_dir),
            "processed_dir": str(self.config.processed_dir),
            "dry_run": self.config.dry_run,
        }

    def _check_filesystem_prerequisites(self) -> Dict[str, Any]:
        """Validates presence and readability of raw datasets."""
        raw_files = {
            "stations": self.config.raw_dir / "datameet" / "stations.json",
            "trains": self.config.raw_dir / "datameet" / "trains.json",
            "schedules": self.config.raw_dir / "datameet" / "schedules.json",
            "journey_train": self.config.raw_dir / "operational_journeys" / "ir_train.csv",
            "journey_test": self.config.raw_dir / "operational_journeys" / "ir_test.csv",
        }

        details: Dict[str, Any] = {}
        missing = []
        for name, path in raw_files.items():
            if path.is_file():
                details[name] = {
                    "path": str(path.relative_to(PROJECT_ROOT) if path.is_relative_to(PROJECT_ROOT) else path),
                    "size_bytes": path.stat().st_size,
                    "readable": os.access(path, os.R_OK),
                }
            else:
                missing.append(name)

        if missing:
            raise OrchestratorPreflightError(
                f"Missing required raw source datasets in {self.config.raw_dir}: {', '.join(missing)}"
            )

        return {"verified_files": details, "all_present": True}

    def _check_database_readiness(self) -> Dict[str, Any]:
        """Verifies database connectivity and lists table row counts."""
        try:
            with get_db_cursor() as cur:
                cur.execute("SELECT current_database(), version();")
                row = cur.fetchone()
                db_name = row[0] if isinstance(row, (list, tuple)) else row["current_database"]
                version = row[1] if isinstance(row, (list, tuple)) else row["version"]

            val_res = validate_schema()
            return {
                "database": db_name,
                "version": version[:40] + "...",
                "is_schema_valid": val_res.is_valid,
                "total_records": val_res.total_records,
                "tables": {t: v.row_count for t, v in val_res.tables.items()},
                "schema_errors": val_res.errors,
            }
        except Exception as exc:
            sanitized = sanitize_error_message(exc)
            raise OrchestratorPreflightError(f"Database readiness check failed: {sanitized}") from exc

    def _check_storage_artifacts(self) -> Dict[str, Any]:
        """Verifies presence of processed Parquet storage artifacts."""
        proc_dir = self.config.processed_dir
        parquet_files = {
            "stations": proc_dir / "stations.parquet",
            "trains": proc_dir / "trains.parquet",
            "schedules": proc_dir / "schedules.parquet",
            "journey_train": proc_dir / "journey_train.parquet",
            "journey_test": proc_dir / "journey_test.parquet",
        }
        details: Dict[str, Any] = {}
        missing = []
        for name, p_path in parquet_files.items():
            if p_path.is_file():
                details[name] = {
                    "path": str(p_path.relative_to(PROJECT_ROOT) if p_path.is_relative_to(PROJECT_ROOT) else p_path),
                    "size_bytes": p_path.stat().st_size,
                }
            else:
                missing.append(name)

        quality_report_file = proc_dir / "quality_report.json"
        details["quality_report_exists"] = quality_report_file.is_file()

        if missing:
            raise OrchestratorExecutionError(f"Missing processed Parquet files: {', '.join(missing)}")

        return {"verified_artifacts": details, "all_present": True}

    def _load_datasets_to_database(self, expected_counts: Dict[str, int]) -> Dict[str, Any]:
        """
        Loads Parquet datasets into PostgreSQL in batches of 5000 inside a single atomic transaction.
        Enforces rollbacks if any dataset load fails.
        """
        # Ensure advisory lock remains held before establishing the write connection
        assert_pipeline_advisory_lock_held()
        from backend.pipeline.database_loader import get_connection

        connection = get_connection()
        loaded_counts: Dict[str, int] = {}
        total_loaded = 0

        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT current_database()")
                    db_name = cursor.fetchone()[0]
                    if db_name != settings.postgres_db:
                        raise RuntimeError(f"Wrong database: {db_name}. Expected {settings.postgres_db}.")

                    for table_name, filename in LOADER_DATASETS.items():
                        # Verify advisory lock remains held throughout every protected write operation
                        assert_pipeline_advisory_lock_held()
                        parquet_path = self.config.processed_dir / filename
                        if not parquet_path.is_file():
                            raise FileNotFoundError(f"Missing Parquet file for load: {parquet_path}")

                        logger.info("Loading %s into table '%s'...", filename, table_name)
                        load_dataset(cursor, table_name, parquet_path)
                        cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name)))
                        cnt = cursor.fetchone()[0]
                        loaded_counts[table_name] = cnt
                        total_loaded += cnt

                    # Final pre-commit lock verification: ensure dedicated lock session is still held
                    logger.info("Verifying advisory lock ownership prior to committing database transaction...")
                    assert_pipeline_advisory_lock_held()

            logger.info("Atomic database load completed: %d total records loaded.", total_loaded)
            return {"total_loaded": total_loaded, "table_counts": loaded_counts}
        finally:
            connection.close()

    def _build_run_summary(
        self, tracker: PipelineExecutionTracker, extra_details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return {
            "run_id": tracker.run_id,
            "pipeline_name": tracker.pipeline_name,
            "run_type": tracker.run_type,
            "trigger_type": tracker.trigger_type,
            "status": tracker.status,
            "start_time": tracker.start_time.isoformat() if tracker.start_time else None,
            "finish_time": tracker.finish_time.isoformat() if tracker.finish_time else None,
            "duration_seconds": tracker.duration_seconds,
            "records_processed": tracker.records_processed,
            "records_accepted": tracker.records_accepted,
            "records_quarantined": tracker.records_quarantined,
            "current_stage": tracker.current_stage,
            "failed_stage": tracker.failed_stage,
            "error_summary": tracker.error_summary,
            "stage_details": [s.to_dict() for s in tracker.stage_outcomes],
            "details": extra_details or {},
        }


# =============================================================================
# CLI Entry Point & Argument Parsing
# =============================================================================
def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.pipeline.orchestrator",
        description="RAIL / SIGNAL — Unified ETL Orchestration & Schema Management Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Execution Modes:
  preflight        Non-destructive environment, directory, raw files, and database readiness audit.
  schema-validate  Deep schema introspection (tables, columns, types, primary keys).
  schema-init      Safe, idempotent DDL execution (CREATE TABLE IF NOT EXISTS).
  validate         Runs full pipeline validation without modifying database tables.
  etl              Executes the full pipeline in dependency order with safety guards.

Safety Rules:
  - The default mode is 'preflight'.
  - Full 'etl' mode refuses to overwrite populated tables unless --allow-data-replace is specified.
  - Test ETL runs safely using --dry-run (isolates outputs to temporary directory).

Examples:
  python -m backend.pipeline.orchestrator --mode preflight
  python -m backend.pipeline.orchestrator --mode schema-validate
  python -m backend.pipeline.orchestrator --mode validate
  python -m backend.pipeline.orchestrator --mode etl --dry-run
        """,
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="preflight",
        choices=["preflight", "inspect", "schema-validate", "schema-init", "validate", "etl", "run"],
        help="Orchestration mode to execute (default: preflight).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution in an isolated temporary directory without modifying PostgreSQL tables.",
    )
    parser.add_argument(
        "--keep-dryrun-artifacts",
        action="store_true",
        help="Preserves isolated temporary dry-run files instead of auto-deleting them.",
    )
    parser.add_argument(
        "--allow-data-replace",
        action="store_true",
        help="Explicitly authorizes data overwrite if tables already contain records.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw",
        help="Path to raw input datasets (default: data/raw).",
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed",
        help="Path to processed output Parquet files (default: data/processed).",
    )
    parser.add_argument(
        "--max-journey-chunks",
        type=int,
        default=None,
        help="Maximum CSV chunks to process for journeys (useful for rapid testing).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=100_000,
        help="Row chunk size for streaming CSV transformations (default: 100,000).",
    )
    parser.add_argument(
        "--trigger-type",
        type=str,
        default="CLI",
        help="Audit trigger source identifier (default: CLI).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured execution result as JSON.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress informational log messages.",
    )
    return parser


def main(args: Optional[Sequence[str]] = None) -> int:
    """CLI entry point returning exit code (0 for success, 1 for failure, 2 for config error, 130 for SIGINT)."""
    parser = build_cli_parser()
    parsed_args = parser.parse_args(args)

    config = OrchestratorConfig(
        mode=OrchestrationMode(parsed_args.mode),
        raw_dir=parsed_args.raw_dir,
        processed_dir=parsed_args.processed_dir,
        dry_run=parsed_args.dry_run,
        keep_dry_run_artifacts=parsed_args.keep_dryrun_artifacts,
        allow_data_replace=parsed_args.allow_data_replace,
        max_journey_chunks=parsed_args.max_journey_chunks,
        chunk_size=parsed_args.chunk_size,
        trigger_type=parsed_args.trigger_type,
        json_output=parsed_args.json,
        quiet=parsed_args.quiet,
    )

    orchestrator = ETLOrchestrator(config)

    try:
        result = orchestrator.run()
        if config.json_output:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"\n==================================================================")
            print(f"RAIL / SIGNAL Orchestration Result: {result['status']}")
            print(f"Run ID:            {result['run_id']}")
            print(f"Pipeline:          {result['pipeline_name']}")
            print(f"Mode:              {result['run_type']}")
            print(f"Duration:          {result['duration_seconds']}s")
            print(f"Records Processed: {result['records_processed']:,}")
            print(f"Records Accepted:  {result['records_accepted']:,}")
            print(f"Quarantined:       {result['records_quarantined']:,}")
            print(f"Stages Executed:   {len(result['stage_details'])}")
            for st in result["stage_details"]:
                print(f"  - [{st['status']}] {st['stage_name']} ({st.get('duration_seconds', 0)}s)")
            print(f"==================================================================\n")
        return 0

    except KeyboardInterrupt as ki:
        logger.warning("Pipeline execution cancelled by user: %s", ki)
        if config.json_output:
            print(json.dumps({"status": "FAILED", "error_type": "KeyboardInterrupt", "error": "Execution interrupted by user (Ctrl+C)"}))
        else:
            print("\n[INTERRUPTED] Pipeline execution cancelled by user (Ctrl+C).\n", file=sys.stderr)
        return 130

    except (OrchestratorPreflightError, ValueError) as preflight_err:
        sanitized = sanitize_error_message(preflight_err)
        logger.error("Preflight Configuration Error: %s", sanitized)
        if config.json_output:
            print(json.dumps({"status": "FAILED", "error_type": "PreflightError", "error": sanitized}))
        else:
            print(f"\n[PREFLIGHT ERROR] {sanitized}\n", file=sys.stderr)
        return 2

    except (OrchestratorSchemaError, OrchestratorDataSafetyError, OrchestratorExecutionError) as orch_err:
        sanitized = sanitize_error_message(orch_err)
        logger.error("Orchestrator Pipeline Failure: %s", sanitized)
        if config.json_output:
            print(json.dumps({"status": "FAILED", "error_type": type(orch_err).__name__, "error": sanitized}))
        else:
            print(f"\n[ORCHESTRATION FAILURE] {sanitized}\n", file=sys.stderr)
        return 1

    except Exception as exc:
        sanitized = sanitize_error_message(exc)
        logger.exception("Unexpected Orchestration Exception: %s", sanitized)
        if config.json_output:
            print(json.dumps({"status": "FAILED", "error_type": "UnexpectedException", "error": sanitized}))
        else:
            print(f"\n[UNEXPECTED FAILURE] {sanitized}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
