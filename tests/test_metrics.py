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


def test_metrics_table_counts_cache_hit_and_expiration():
    """Verifies that get_cached_table_counts reuses cached counts within TTL and refreshes when expired."""
    import time
    from unittest.mock import MagicMock
    import backend.app.main as main_mod

    # Reset cache state
    with main_mod._METRICS_CACHE_LOCK:
        main_mod._METRICS_CACHE_TIMESTAMP = 0.0
        main_mod._METRICS_TABLE_COUNTS_CACHE = {}

    query_count = 0
    original_get_db_cursor = main_mod.db.get_db_cursor

    def counting_get_db_cursor():
        nonlocal query_count
        query_count += 1
        return original_get_db_cursor()

    with patch.object(main_mod.db, "get_db_cursor", side_effect=counting_get_db_cursor):
        # 1. First fetch (cache miss)
        counts1 = main_mod.get_cached_table_counts(ttl=10.0)
        assert counts1["stations"] == 8988
        assert query_count == 1

        # 2. Second fetch within TTL (cache hit - no DB query)
        counts2 = main_mod.get_cached_table_counts(ttl=10.0)
        assert counts2["stations"] == 8988
        assert query_count == 1  # Query count did not increase

        # 3. Simulate TTL expiration
        main_mod._METRICS_CACHE_TIMESTAMP = time.time() - 20.0
        counts3 = main_mod.get_cached_table_counts(ttl=10.0)
        assert counts3["stations"] == 8988
        assert query_count == 2  # Query count refreshed


def test_metrics_concurrent_cache_access():
    """Verifies that concurrent threads accessing get_cached_table_counts do not race or fail."""
    import concurrent.futures
    import backend.app.main as main_mod

    def worker():
        return main_mod.get_cached_table_counts(ttl=60.0)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker) for _ in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 10
    for r in results:
        assert r["stations"] == 8988
        assert r["trains"] == 5207


def test_metrics_single_database_up_on_table_counts_refresh_failure():
    """
    F-01 regression test: Simulates successful SELECT 1 connectivity probe followed by
    table-count refresh failure. Verifies that exactly one rail_signal_database_up sample
    is emitted with value 0, avoiding duplicate samples or conflicting statuses.
    """
    import backend.app.main as main_mod

    with patch.object(main_mod, "get_cached_table_counts", side_effect=Exception("Count query timeout")):
        response = client.get("/metrics")
        assert response.status_code == 200
        text = response.text

        # Must report database down (0)
        assert "rail_signal_database_up 0" in text
        # Must NOT contain a conflicting sample with value 1
        assert "rail_signal_database_up 1" not in text
        # Count sample occurrences (excluding HELP and TYPE declarations)
        sample_lines = [line for line in text.splitlines() if line.startswith("rail_signal_database_up ")]
        assert len(sample_lines) == 1
        assert sample_lines[0] == "rail_signal_database_up 0"


def test_consolidated_table_counts_query_format():
    """
    F-03 test: Verifies that get_cached_table_counts executes a single parameter-free
    statement containing scalar subqueries for stations, trains, schedules, journey_train, journey_test.
    """
    from unittest.mock import MagicMock
    import backend.app.main as main_mod

    with main_mod._METRICS_CACHE_LOCK:
        main_mod._METRICS_CACHE_TIMESTAMP = 0.0
        main_mod._METRICS_TABLE_COUNTS_CACHE = {}

    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {
        "stations": 8988,
        "trains": 5207,
        "schedules": 394469,
        "journey_train": 1500000,
        "journey_test": 375000,
    }

    class MockContextMgr:
        def __enter__(self):
            return mock_cur
        def __exit__(self, *args):
            pass

    with patch.object(main_mod.db, "get_db_cursor", return_value=MockContextMgr()):
        counts = main_mod.get_cached_table_counts(ttl=60.0)

        # Single SQL execution
        assert mock_cur.execute.call_count == 1
        executed_sql = mock_cur.execute.call_args[0][0]
        assert "SELECT (SELECT COUNT(*) FROM stations) AS stations" in executed_sql
        assert "(SELECT COUNT(*) FROM trains) AS trains" in executed_sql
        assert "(SELECT COUNT(*) FROM schedules) AS schedules" in executed_sql
        assert "(SELECT COUNT(*) FROM journey_train) AS journey_train" in executed_sql
        assert "(SELECT COUNT(*) FROM journey_test) AS journey_test" in executed_sql
        assert counts["stations"] == 8988
        assert counts["journey_train"] == 1500000
