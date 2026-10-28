"""
Comprehensive Unit and Integration Tests for Unified ETL Orchestrator.
Tests dependency order, preflight checks, schema validation, execution modes,
failure handling, stage skipping, exit codes, and data overwrite safeguards.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.pipeline.orchestrator import (
    ETLOrchestrator,
    OrchestrationMode,
    OrchestratorConfig,
    OrchestratorDataSafetyError,
    OrchestratorExecutionError,
    OrchestratorPreflightError,
    OrchestratorSchemaError,
    main,
)
from backend.pipeline.schema_manager import SchemaValidationResult, TableValidation


# =============================================================================
# CLI Tests & Exit Codes
# =============================================================================
def test_cli_help(capsys):
    """Verifies that --help prints usage information and exits with code 0."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "RAIL / SIGNAL" in captured.out
    assert "--mode" in captured.out
    assert "preflight" in captured.out


def test_cli_invalid_mode(capsys):
    """Verifies that an invalid mode argument exits with code 2."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--mode", "invalid_mode_name"])
    assert excinfo.value.code == 2


def test_cli_preflight_exit_code_zero():
    """Verifies that running preflight via CLI main() exits with code 0."""
    exit_code = main(["--mode", "preflight", "--quiet"])
    assert exit_code == 0


def test_cli_preflight_json_output(capsys):
    """Verifies that running preflight with --json outputs valid JSON."""
    exit_code = main(["--mode", "preflight", "--quiet", "--json"])
    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "SUCCESS"
    assert data["pipeline_name"] == "rail_signal_preflight"
    assert data["run_type"] == "INSPECT"
    assert len(data["stage_details"]) == 3


def test_cli_schema_validate_exit_code_zero():
    """Verifies that running schema-validate via CLI main() exits with code 0."""
    exit_code = main(["--mode", "schema-validate", "--quiet"])
    assert exit_code == 0


def test_cli_validate_exit_code_zero():
    """Verifies that running pipeline validation via CLI main() exits with code 0."""
    exit_code = main(["--mode", "validate", "--quiet"])
    assert exit_code == 0


def test_cli_etl_safeguard_exit_code_one(capsys):
    """
    Verifies that running full ETL against populated tables without --allow-data-replace
    is blocked by the overwrite guard and exits with code 1.
    """
    exit_code = main(["--mode", "etl", "--quiet"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "ETL Load Guard" in captured.err or "ORCHESTRATION FAILURE" in captured.err


def test_cli_preflight_missing_raw_dir_exit_code_two(tmp_path, capsys):
    """Verifies that preflight failure returns exit code 2."""
    empty_dir = tmp_path / "empty_raw"
    empty_dir.mkdir()
    exit_code = main(["--mode", "preflight", "--raw-dir", str(empty_dir), "--quiet"])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "PREFLIGHT ERROR" in captured.err


# =============================================================================
# Programmatic Orchestration Flow Tests
# =============================================================================
def test_orchestrator_preflight_flow():
    """Verifies preflight flow execution, stage outcomes, and metadata."""
    config = OrchestratorConfig(mode=OrchestrationMode.PREFLIGHT, quiet=True)
    orchestrator = ETLOrchestrator(config)
    result = orchestrator.run()

    assert result["status"] == "SUCCESS"
    assert result["pipeline_name"] == "rail_signal_preflight"
    assert result["run_type"] == "INSPECT"
    assert result["duration_seconds"] > 0
    assert len(result["stage_details"]) == 3

    stages = [s["stage_name"] for s in result["stage_details"]]
    assert stages == [
        "01_preflight_and_config",
        "02_filesystem_prerequisites",
        "03_database_connectivity_and_schema",
    ]
    for s in result["stage_details"]:
        assert s["status"] == "SUCCESS"
        assert s["duration_seconds"] is not None


def test_orchestrator_schema_validate_flow():
    """Verifies schema validation flow passes and reports verified records."""
    config = OrchestratorConfig(mode=OrchestrationMode.SCHEMA_VALIDATE, quiet=True)
    orchestrator = ETLOrchestrator(config)
    result = orchestrator.run()

    assert result["status"] == "SUCCESS"
    assert result["run_type"] == "SCHEMA_VALIDATE"
    assert result["records_processed"] == 2283664
    assert result["records_accepted"] == 2283664
    assert len(result["stage_details"]) == 2


def test_orchestrator_schema_init_flow():
    """Verifies safe idempotent schema init execution."""
    config = OrchestratorConfig(mode=OrchestrationMode.SCHEMA_INIT, quiet=True)
    orchestrator = ETLOrchestrator(config)
    result = orchestrator.run()

    assert result["status"] == "SUCCESS"
    assert result["run_type"] == "SCHEMA_INIT"
    assert len(result["stage_details"]) == 2
    init_details = result["details"]["schema_init"]
    assert init_details["is_valid"] is True
    assert "00_core_tables.sql" in init_details["applied_files"]


def test_orchestrator_validate_flow():
    """Verifies 4-stage pipeline validation flow."""
    config = OrchestratorConfig(mode=OrchestrationMode.VALIDATE, quiet=True)
    orchestrator = ETLOrchestrator(config)
    result = orchestrator.run()

    assert result["status"] == "SUCCESS"
    assert result["run_type"] == "VALIDATION"
    assert result["records_processed"] == 2283664
    assert len(result["stage_details"]) == 4

    stages = [s["stage_name"] for s in result["stage_details"]]
    assert stages == [
        "01_environment_and_config",
        "02_raw_datasets_verification",
        "03_database_connectivity_and_integrity",
        "04_storage_artifacts_verification",
    ]


# =============================================================================
# Error Handling, Stage Skipping & Safeguards
# =============================================================================
def test_preflight_fails_on_missing_config():
    """Verifies preflight raises OrchestratorPreflightError when a required setting is absent."""
    config = OrchestratorConfig(mode=OrchestrationMode.PREFLIGHT, quiet=True)
    orchestrator = ETLOrchestrator(config)

    with patch.dict("os.environ", {"POSTGRES_DB": ""}), patch("backend.app.config.settings.postgres_db", ""):
        with pytest.raises(OrchestratorPreflightError, match="Missing required database settings"):
            orchestrator.run()


def test_preflight_fails_on_missing_dataset(tmp_path):
    """Verifies preflight raises OrchestratorPreflightError when raw datasets are missing."""
    empty_raw = tmp_path / "raw"
    empty_raw.mkdir()

    config = OrchestratorConfig(mode=OrchestrationMode.PREFLIGHT, raw_dir=empty_raw, quiet=True)
    orchestrator = ETLOrchestrator(config)

    with pytest.raises(OrchestratorPreflightError, match="Missing required raw source datasets"):
        orchestrator.run()


def test_schema_validate_halts_on_invalid_schema():
    """Verifies that schema validation failure raises OrchestratorSchemaError."""
    config = OrchestratorConfig(mode=OrchestrationMode.SCHEMA_VALIDATE, quiet=True)
    orchestrator = ETLOrchestrator(config)

    mock_invalid = SchemaValidationResult(
        is_valid=False,
        database_name="rail_signal",
        errors=["Required table 'stations' does not exist."],
    )

    with patch("backend.pipeline.orchestrator.validate_schema", return_value=mock_invalid):
        with pytest.raises(OrchestratorSchemaError, match="Required table 'stations' does not exist"):
            orchestrator.run()


def test_etl_overwrite_guard_blocks_unauthorized_execution():
    """
    Verifies that full ETL halts before transforming or loading data when target
    tables already contain records and --allow-data-replace is not specified.
    """
    config = OrchestratorConfig(mode=OrchestrationMode.ETL, allow_data_replace=False, dry_run=False, quiet=True)
    orchestrator = ETLOrchestrator(config)

    with pytest.raises(OrchestratorDataSafetyError, match="ETL Load Guard: Target database 'rail_signal' already contains"):
        orchestrator.run()


def test_etl_dry_run_skips_database_write():
    """
    Verifies that running ETL in dry_run mode executes transformation but safely
    skips database loading without modifying tables.
    """
    config = OrchestratorConfig(
        mode=OrchestrationMode.ETL,
        dry_run=True,
        allow_data_replace=False,
        quiet=True,
    )
    orchestrator = ETLOrchestrator(config)

    # Mock execute_transformation_pipeline to return synthetic quality report without heavy CSV streaming
    from backend.pipeline.transformation import QualityReport
    mock_report = QualityReport(
        run_timestamp="2026-10-27T12:00:00Z",
        accepted_counts={"stations": 100, "trains": 50, "schedules": 200, "journey_train": 500, "journey_test": 100},
        quarantined_counts={"stations": 0, "trains": 0, "schedules": 0, "journey_train": 0, "journey_test": 0},
    )

    with patch("backend.pipeline.orchestrator.execute_transformation_pipeline", return_value=mock_report):
        with patch.object(orchestrator, "_load_datasets_to_database") as mock_db_load:
            result = orchestrator.run()

            # Ensure database loader was NOT invoked
            mock_db_load.assert_not_called()
            assert result["status"] == "SUCCESS"
            db_stage = [s for s in result["stage_details"] if s["stage_name"] == "04_database_loading"][0]
            assert db_stage["status"] == "SUCCESS"
            assert db_stage["details"].get("dry_run") is True


def test_stage_failure_marks_run_failed():
    """Verifies that an unhandled exception in an early stage halts execution and marks the run FAILED."""
    config = OrchestratorConfig(mode=OrchestrationMode.VALIDATE, quiet=True)
    orchestrator = ETLOrchestrator(config)

    with patch.object(orchestrator, "_check_storage_artifacts", side_effect=RuntimeError("Storage disk offline")):
        with pytest.raises(RuntimeError, match="Storage disk offline"):
            orchestrator.run()


# =============================================================================
# Phase 4A & 4B: Advisory Locking, Dry-Run Isolation & Interruption Tests
# =============================================================================

def test_orchestrator_advisory_lock_contention_raises_and_exits_one(capsys):
    """Verifies that advisory lock contention halts orchestration and returns exit code 1."""
    from backend.pipeline.advisory_lock import AdvisoryLockContentionError

    with patch(
        "backend.pipeline.orchestrator.acquire_pipeline_advisory_lock",
        side_effect=AdvisoryLockContentionError("PostgreSQL advisory lock (key=842091238471) is currently held by another active process."),
    ):
        exit_code = main(["--mode", "etl", "--dry-run", "--quiet"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "ORCHESTRATION FAILURE" in captured.err
        assert "currently held by another active process" in captured.err


def test_orchestrator_dry_run_workspace_isolation():
    """Verifies that dry-run creates an isolated temp directory, routes output there, and cleans it up."""
    from backend.pipeline.transformation import QualityReport
    mock_report = QualityReport(
        run_timestamp="2026-10-27T12:00:00Z",
        accepted_counts={"stations": 10},
        quarantined_counts={"stations": 0},
    )

    passed_processed_dir = None

    def fake_transform(raw_dir, processed_dir, chunk_size, max_journey_chunks):
        nonlocal passed_processed_dir
        passed_processed_dir = Path(processed_dir)
        # Create a mock file in the isolated directory
        (passed_processed_dir / "test_marker.tmp").write_text("dry run isolated")
        return mock_report

    config = OrchestratorConfig(
        mode=OrchestrationMode.ETL,
        dry_run=True,
        keep_dry_run_artifacts=False,
        quiet=True,
    )
    orchestrator = ETLOrchestrator(config)

    with patch("backend.pipeline.orchestrator.execute_transformation_pipeline", side_effect=fake_transform):
        result = orchestrator.run()

    assert result["status"] == "SUCCESS"
    assert passed_processed_dir is not None
    # Must NOT be the production processed directory
    assert passed_processed_dir != config.processed_dir
    assert "rail_signal_dryrun_" in str(passed_processed_dir)
    # Temporary directory must be deleted after execution
    assert not passed_processed_dir.exists()


def test_orchestrator_dry_run_keep_artifacts(tmp_path):
    """Verifies that keep_dry_run_artifacts=True preserves the isolated workspace for inspection."""
    from backend.pipeline.transformation import QualityReport
    mock_report = QualityReport(
        run_timestamp="2026-10-27T12:00:00Z",
        accepted_counts={"stations": 10},
        quarantined_counts={"stations": 0},
    )

    passed_processed_dir = None

    def fake_transform(raw_dir, processed_dir, chunk_size, max_journey_chunks):
        nonlocal passed_processed_dir
        passed_processed_dir = Path(processed_dir)
        (passed_processed_dir / "debug_report.json").write_text("{}")
        return mock_report

    config = OrchestratorConfig(
        mode=OrchestrationMode.ETL,
        dry_run=True,
        keep_dry_run_artifacts=True,
        quiet=True,
    )
    orchestrator = ETLOrchestrator(config)

    with patch("backend.pipeline.orchestrator.execute_transformation_pipeline", side_effect=fake_transform):
        result = orchestrator.run()

    try:
        assert result["status"] == "SUCCESS"
        assert passed_processed_dir.exists()
        assert (passed_processed_dir / "debug_report.json").exists()
    finally:
        # Manual cleanup for test cleanliness
        if passed_processed_dir and passed_processed_dir.exists():
            import shutil
            shutil.rmtree(passed_processed_dir, ignore_errors=True)


def test_orchestrator_interruption_returns_exit_code_130(capsys):
    """Verifies that Ctrl+C / KeyboardInterrupt returns exit code 130 and reports interruption."""
    config = OrchestratorConfig(mode=OrchestrationMode.PREFLIGHT, quiet=True)
    orchestrator = ETLOrchestrator(config)

    with patch.object(orchestrator, "_check_environment_and_config", side_effect=KeyboardInterrupt):
        with patch("backend.pipeline.orchestrator.ETLOrchestrator", return_value=orchestrator):
            exit_code = main(["--mode", "preflight", "--quiet"])
            assert exit_code == 130
            captured = capsys.readouterr()
            assert "[INTERRUPTED]" in captured.err or "cancelled by user" in captured.err


def test_orchestrator_aborts_writes_when_advisory_lock_lost_before_stage_4():
    """Verifies that if the dedicated advisory lock session drops before Stage 4 writes, execution aborts safely."""
    from backend.pipeline.advisory_lock import AdvisoryLockConnectionError
    from backend.pipeline.transformation import QualityReport

    mock_report = QualityReport(
        run_timestamp="2026-10-27T12:00:00Z",
        accepted_counts={"stations": 10, "trains": 5, "schedules": 20, "journey_train": 50, "journey_test": 10},
        quarantined_counts={"stations": 0, "trains": 0, "schedules": 0, "journey_train": 0, "journey_test": 0},
    )

    config = OrchestratorConfig(
        mode=OrchestrationMode.ETL,
        dry_run=False,
        allow_data_replace=True,
        quiet=True,
    )
    orchestrator = ETLOrchestrator(config)

    # Simulate losing the lock right before stage 4 database loading
    with patch("backend.pipeline.orchestrator.execute_transformation_pipeline", return_value=mock_report):
        with patch(
            "backend.pipeline.orchestrator.assert_pipeline_advisory_lock_held",
            side_effect=AdvisoryLockConnectionError("Advisory lock verification failed: dedicated session dropped"),
        ):
            with patch.object(orchestrator, "_load_datasets_to_database") as mock_db_load:
                with pytest.raises(OrchestratorExecutionError, match="dedicated session dropped"):
                    orchestrator.run()

                # Ensure database writes were NEVER invoked
                mock_db_load.assert_not_called()


def test_orchestrator_final_lock_check_failure_triggers_rollback_and_prevents_commit():
    """
    F-02 test: Verifies that if the advisory lock is lost right after loading all datasets
    and before committing the transaction, the final pre-commit check fails, triggering
    a transaction rollback and preventing connection.commit() from executing.
    """
    from backend.pipeline.advisory_lock import AdvisoryLockConnectionError
    import backend.pipeline.orchestrator as orch_mod

    config = OrchestratorConfig(mode=OrchestrationMode.ETL, dry_run=False, allow_data_replace=True, quiet=True)
    orchestrator = ETLOrchestrator(config)

    mock_cursor = MagicMock()
    mock_cursor.fetchone.side_effect = [["rail_signal"], [100], [100], [100], [100], [100]]

    class MockTransactionConnection:
        def __init__(self):
            self.committed = False
            self.rolled_back = False
            self.closed = False

        def cursor(self):
            class CursorContext:
                def __enter__(self):
                    return mock_cursor
                def __exit__(self, *args):
                    pass
            return CursorContext()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is not None:
                self.rolled_back = True
            else:
                self.committed = True

        def close(self):
            self.closed = True

    mock_conn = MockTransactionConnection()

    check_count = 0
    def mock_lock_check():
        nonlocal check_count
        check_count += 1
        # The 7th call is the final pre-commit check:
        if check_count >= 7:
            raise AdvisoryLockConnectionError("Lock dropped immediately before transaction commit")

    with patch("backend.pipeline.database_loader.get_connection", return_value=mock_conn):
        with patch.object(orch_mod, "load_dataset", return_value=100):
            with patch.object(orch_mod, "assert_pipeline_advisory_lock_held", side_effect=mock_lock_check):
                with patch.object(Path, "is_file", return_value=True):
                    with pytest.raises(AdvisoryLockConnectionError, match="before transaction commit"):
                        orchestrator._load_datasets_to_database({"stations": 100})

    # Assert transaction rolled back and was NEVER committed
    assert mock_conn.rolled_back is True
    assert mock_conn.committed is False
    assert mock_conn.closed is True
    assert check_count >= 7
