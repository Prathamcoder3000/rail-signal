"""
Unit and Integration Tests for PostgreSQL Advisory Locking (backend/pipeline/advisory_lock.py).
Tests non-blocking acquisition, contention detection, automatic unlock on exit/exception,
and dedicated connection cleanup.
"""

from unittest.mock import MagicMock, patch

import psycopg2
import pytest

from backend.pipeline.advisory_lock import (
    RAIL_SIGNAL_ORCHESTRATOR_ADVISORY_LOCK_KEY,
    AdvisoryLockConnectionError,
    AdvisoryLockContentionError,
    acquire_pipeline_advisory_lock,
)


def test_advisory_lock_acquisition_success():
    """Verifies that an unheld advisory lock is acquired and released cleanly."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (True,)
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_conn.closed = False

    with acquire_pipeline_advisory_lock(connection_factory=lambda: mock_conn) as acquired:
        assert acquired is True

    # Verifies try lock called
    mock_cur.execute.assert_any_call("SELECT pg_try_advisory_lock(%s);", (RAIL_SIGNAL_ORCHESTRATOR_ADVISORY_LOCK_KEY,))
    # Verifies unlock called
    mock_cur.execute.assert_any_call("SELECT pg_advisory_unlock(%s);", (RAIL_SIGNAL_ORCHESTRATOR_ADVISORY_LOCK_KEY,))
    # Verifies connection closed
    mock_conn.close.assert_called_once()


def test_advisory_lock_contention_raises_error():
    """Verifies that if another process holds the lock, AdvisoryLockContentionError is raised."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (False,)  # Lock held by someone else
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_conn.closed = False

    with pytest.raises(AdvisoryLockContentionError, match="held by another active process"):
        with acquire_pipeline_advisory_lock(connection_factory=lambda: mock_conn):
            pass

    # Unlock should NOT be called since lock was not acquired
    for c in mock_cur.execute.call_args_list:
        assert "pg_advisory_unlock" not in str(c)
    # Connection MUST still be closed
    mock_conn.close.assert_called_once()


def test_advisory_lock_released_on_inner_exception():
    """Verifies that if the protected block fails, the advisory lock is still released."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (True,)
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_conn.closed = False

    with pytest.raises(RuntimeError, match="Task failure inside lock"):
        with acquire_pipeline_advisory_lock(connection_factory=lambda: mock_conn):
            raise RuntimeError("Task failure inside lock")

    # Unlock MUST be called in finally block
    mock_cur.execute.assert_any_call("SELECT pg_advisory_unlock(%s);", (RAIL_SIGNAL_ORCHESTRATOR_ADVISORY_LOCK_KEY,))
    mock_conn.close.assert_called_once()


def test_advisory_lock_connection_failure():
    """Verifies that database connection failures raise AdvisoryLockConnectionError."""
    def failing_factory():
        raise psycopg2.OperationalError("Database host unreachable")

    with pytest.raises(AdvisoryLockConnectionError, match="Could not connect to database"):
        with acquire_pipeline_advisory_lock(connection_factory=failing_factory):
            pass
