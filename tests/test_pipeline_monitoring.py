"""
Automated unit and integration tests for Pipeline Execution Monitoring & History.

Tests:
1. Idempotent pipeline_runs schema verification.
2. PipelineExecutionTracker success lifecycle with stage outcomes and duration.
3. PipelineExecutionTracker failure lifecycle (ensures RUNNING is never left behind).
4. Error message credential sanitization.
5. GET /api/pipeline/history pagination, ordering, and status filters.
6. GET /api/pipeline/history/{run_id} full detail retrieval and HTTP 404 for unknown run.
7. POST /api/pipeline/run validation-only trigger execution.
8. POST /api/pipeline/run rejection of destructive full-etl mode in Phase 1.
9. Database logging error resilience (failsafe handling).
10. Preservation of existing railway table row counts.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.db import get_db_cursor
from backend.app.main import app
from backend.pipeline.monitoring import (
    PipelineExecutionTracker,
    ensure_pipeline_runs_table,
    execute_validation_pipeline,
    generate_run_id,
    get_pipeline_run_by_id,
    get_pipeline_runs,
    sanitize_error_message,
)

client = TestClient(app)


# ==============================================================================
# 1. Schema & Tracker Lifecycle Tests
# ==============================================================================

def test_ensure_pipeline_runs_table_is_idempotent():
    """Verifies that ensure_pipeline_runs_table can be called multiple times safely."""
    ensure_pipeline_runs_table()
    ensure_pipeline_runs_table()

    with get_db_cursor() as cur:
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'pipeline_runs';
        """)
        row = cur.fetchone()
        assert row is not None
        assert row["table_name"] == "pipeline_runs"


def test_tracker_success_lifecycle():
    """Tests normal successful lifecycle with stages and duration."""
    run_id = generate_run_id("test_success")
    tracker = PipelineExecutionTracker(
        pipeline_name="Unit Test Pipeline",
        run_type="TEST",
        trigger_type="TEST_TRIGGER",
        run_id=run_id,
        metadata={"environment": "pytest"},
    )

    with tracker:
        tracker.start_stage("stage_a", details={"param": 1})
        tracker.finish_stage("stage_a", status="SUCCESS", records_processed=100, records_accepted=98, records_quarantined=2)
        
        tracker.start_stage("stage_b")
        tracker.finish_stage("stage_b", status="SUCCESS", records_processed=200, records_accepted=200)

    # Verify persisted record
    persisted = get_pipeline_run_by_id(run_id)
    assert persisted is not None
    assert persisted["run_id"] == run_id
    assert persisted["status"] == "SUCCESS"
    assert persisted["run_type"] == "TEST"
    assert persisted["trigger_type"] == "TEST_TRIGGER"
    assert persisted["duration_seconds"] is not None
    assert persisted["duration_seconds"] >= 0.0
    assert persisted["records_processed"] == 300
    assert persisted["records_accepted"] == 298
    assert persisted["records_quarantined"] == 2
    assert persisted["current_stage"] is None
    assert persisted["failed_stage"] is None
    assert persisted["error_summary"] is None

    # Verify stages JSONB
    stages = persisted["stage_details"]
    assert len(stages) == 2
    assert stages[0]["stage_name"] == "stage_a"
    assert stages[0]["status"] == "SUCCESS"
    assert stages[0]["records_processed"] == 100
    assert stages[1]["stage_name"] == "stage_b"
    assert stages[1]["status"] == "SUCCESS"


def test_tracker_failure_lifecycle_never_leaves_running():
    """Verifies that an unhandled exception marks the run as FAILED and never leaves RUNNING."""
    run_id = generate_run_id("test_failure")
    tracker = PipelineExecutionTracker(
        pipeline_name="Unit Test Failure Pipeline",
        run_type="TEST",
        trigger_type="TEST_TRIGGER",
        run_id=run_id,
    )

    with pytest.raises(ZeroDivisionError):
        with tracker:
            tracker.start_stage("stage_alpha")
            tracker.finish_stage("stage_alpha", status="SUCCESS")

            tracker.start_stage("stage_error")
            # Trigger intentional exception
            _ = 1 / 0

    # Verify persisted record
    persisted = get_pipeline_run_by_id(run_id)
    assert persisted is not None
    assert persisted["status"] == "FAILED"
    assert persisted["failed_stage"] == "stage_error"
    assert "division by zero" in persisted["error_summary"].lower()
    assert persisted["duration_seconds"] is not None

    stages = persisted["stage_details"]
    assert len(stages) == 2
    assert stages[0]["status"] == "SUCCESS"
    assert stages[1]["status"] == "FAILED"
    assert "division by zero" in stages[1]["error"].lower()


def test_error_message_sanitization():
    """Verifies that sensitive credentials and passwords are stripped from logs."""
    raw_error = "psycopg2.OperationalError: password=super_secret_password host=localhost"
    sanitized = sanitize_error_message(raw_error)
    assert "super_secret_password" not in sanitized
    assert "password=***" in sanitized

    uri_error = "FATAL: connect failed postgresql://rail_user:my_secret_pass@localhost:5432/rail_signal"
    sanitized_uri = sanitize_error_message(uri_error)
    assert "my_secret_pass" not in sanitized_uri
    assert "***" in sanitized_uri


# ==============================================================================
# 2. History API Endpoints Tests
# ==============================================================================

def test_get_pipeline_history_endpoint():
    """Tests GET /api/pipeline/history pagination and ordering."""
    response = client.get("/api/pipeline/history?page=1&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "stats" in data
    assert data["stats"]["total_runs"] >= 1
    assert data["stats"]["successful_runs"] >= 0
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert data["total"] >= 1

    if data["items"]:
        item = data["items"][0]
        assert "run_id" in item
        assert "status" in item
        assert "run_type" in item
        assert "trigger_type" in item
        assert "stage_count" in item
        assert item["status"] in ("SUCCESS", "FAILED", "RUNNING", "PENDING")


def test_get_pipeline_history_status_filter():
    """Tests GET /api/pipeline/history filtering by status."""
    response = client.get("/api/pipeline/history?status=SUCCESS&page_size=5")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["status"] == "SUCCESS"


def test_get_pipeline_run_detail_endpoint():
    """Tests GET /api/pipeline/history/{run_id} returns full stage details."""
    # First get a known run_id
    hist_resp = client.get("/api/pipeline/history?page=1&page_size=1")
    assert hist_resp.status_code == 200
    runs = hist_resp.json()["items"]
    assert len(runs) > 0
    target_run_id = runs[0]["run_id"]

    detail_resp = client.get(f"/api/pipeline/history/{target_run_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["run_id"] == target_run_id
    assert "stage_details" in detail
    assert isinstance(detail["stage_details"], list)
    assert "metadata" in detail


def test_get_pipeline_run_detail_not_found():
    """Tests GET /api/pipeline/history/{run_id} returns 404 for unknown run."""
    response = client.get("/api/pipeline/history/run_NON_EXISTENT_ID_9999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ==============================================================================
# 3. Pipeline Trigger Tests (Safe Validation-Only)
# ==============================================================================

def test_post_pipeline_run_validation_trigger():
    """Tests POST /api/pipeline/run default validation mode."""
    response = client.post("/api/pipeline/run", json={"mode": "validation"})
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert data["run_type"] == "VALIDATION"
    assert data["status"] == "SUCCESS"
    assert "validation pipeline executed" in data["message"].lower()
    assert data["duration_seconds"] is not None
    assert data["summary"]["stage_count"] == 4

    # Verify run detail lookup
    detail_resp = client.get(f"/api/pipeline/history/{data['run_id']}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["status"] == "SUCCESS"
    stage_names = [s["stage_name"] for s in detail["stage_details"]]
    assert "01_environment_and_config" in stage_names
    assert "02_raw_datasets_verification" in stage_names
    assert "03_database_connectivity_and_integrity" in stage_names
    assert "04_storage_artifacts_verification" in stage_names


def test_post_pipeline_run_rejects_full_etl_in_phase_1():
    """Verifies that full_etl trigger is blocked to protect existing database records."""
    response = client.post("/api/pipeline/run", json={"mode": "full_etl"})
    assert response.status_code == 400
    assert "not permitted in phase 1" in response.json()["detail"].lower()
    assert "safeguard existing 2,283,664 postgresql records" in response.json()["detail"].lower()


def test_database_logging_failure_resilience():
    """Verifies that tracker handles database update errors gracefully without crashing."""
    run_id = generate_run_id("test_resilience")
    tracker = PipelineExecutionTracker(
        pipeline_name="Resilience Test",
        run_type="TEST",
        run_id=run_id,
    )

    # Patch get_db_cursor to simulate a temporary database glitch during update
    with patch("backend.pipeline.monitoring.get_db_cursor", side_effect=Exception("Simulated connection dropped")):
        # Must not raise an unhandled crash
        tracker._update_db()


# ==============================================================================
# 4. Data Preservation Verification
# ==============================================================================

def test_railway_database_row_counts_unmodified():
    """Strictly guarantees that all 5 existing railway tables retained their exact row counts."""
    expected_counts = {
        "stations": 8988,
        "trains": 5207,
        "schedules": 394469,
        "journey_train": 1500000,
        "journey_test": 375000,
    }

    with get_db_cursor() as cur:
        for table, expected in expected_counts.items():
            cur.execute(f"SELECT COUNT(*) AS cnt FROM {table};")
            actual = int(cur.fetchone()["cnt"])
            assert actual == expected, f"Table '{table}' expected {expected} rows, found {actual}"
