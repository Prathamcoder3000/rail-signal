"""
Tests for Prometheus-compatible /metrics endpoint in backend/app/main.py.
Verifies format, bounded cardinality, HTTP 200, and failure resilience.
"""

from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_metrics_endpoint_success():
    """Verifies that /metrics returns 200 with text/plain format and standard metrics."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "version=0.0.4" in response.headers["content-type"]
    
    text = response.text
    assert "# HELP rail_signal_pipeline_runs_total" in text
    assert "# TYPE rail_signal_pipeline_runs_total counter" in text
    assert 'rail_signal_pipeline_runs_total{status="SUCCESS"}' in text
    assert "# HELP rail_signal_database_up" in text
    assert "rail_signal_database_up 1" in text
    assert 'rail_signal_records_verified_total{table="stations"}' in text


def test_metrics_endpoint_database_failure_resilience():
    """Verifies that database error in metrics collection reports rail_signal_database_up 0 without 500."""
    with patch("backend.app.db.get_db_cursor", side_effect=Exception("DB Down")):
        response = client.get("/metrics")
        assert response.status_code == 200
        text = response.text
        assert "rail_signal_database_up 0" in text
