"""
Unit and Integration Tests for PostgreSQL Connection Pool Hygiene and Transient Retries.
Verifies rollback on failure, broken connection disposal, connection reuse without
contamination, exception preservation, and transient retry mechanics.
"""

from unittest.mock import MagicMock, call, patch

import psycopg2
from psycopg2 import extensions
import pytest

from backend.app.db import (
    get_db_connection,
    get_db_cursor,
    is_transient_db_error,
    retry_transient_db_operation,
)


def test_get_db_connection_success():
    """Verifies that a healthy connection is returned cleanly to the pool with close=False."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_conn.get_transaction_status.return_value = extensions.TRANSACTION_STATUS_IDLE
    mock_pool.getconn.return_value = mock_conn

    with patch("backend.app.db.get_db_pool", return_value=mock_pool):
        with get_db_connection() as conn:
            assert conn is mock_conn

    mock_pool.getconn.assert_called_once()
    mock_pool.putconn.assert_called_once_with(mock_conn, close=False)


def test_get_db_connection_rollback_on_exception():
    """Verifies that an exception causes conn.rollback() before returning to pool."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_conn.closed = False
    # Transaction was active or in error
    mock_conn.get_transaction_status.side_effect = [
        extensions.TRANSACTION_STATUS_INERROR,
        extensions.TRANSACTION_STATUS_IDLE,
    ]
    mock_pool.getconn.return_value = mock_conn

    class CustomQueryError(Exception):
        pass

    with patch("backend.app.db.get_db_pool", return_value=mock_pool):
        with pytest.raises(CustomQueryError, match="Query execution failed"):
            with get_db_connection() as conn:
                raise CustomQueryError("Query execution failed")

    mock_conn.rollback.assert_called_once()
    mock_pool.putconn.assert_called_once_with(mock_conn, close=False)


def test_get_db_connection_broken_disposal_on_rollback_failure():
    """Verifies that if rollback fails, the connection is closed and discarded from the pool."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_conn.get_transaction_status.return_value = extensions.TRANSACTION_STATUS_INERROR
    mock_conn.rollback.side_effect = psycopg2.OperationalError("Connection lost during rollback")
    mock_pool.getconn.return_value = mock_conn

    with patch("backend.app.db.get_db_pool", return_value=mock_pool):
        with pytest.raises(RuntimeError, match="DB operation error"):
            with get_db_connection() as conn:
                raise RuntimeError("DB operation error")

    # Because rollback failed, putconn MUST be called with close=True
    mock_pool.putconn.assert_called_once_with(mock_conn, close=True)


def test_get_db_connection_closed_connection_discarded():
    """Verifies that if a connection is closed while in use, it is discarded from pool with close=True."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_conn.closed = True
    mock_pool.getconn.return_value = mock_conn

    with patch("backend.app.db.get_db_pool", return_value=mock_pool):
        with get_db_connection() as conn:
            pass

    mock_pool.putconn.assert_called_once_with(mock_conn, close=True)


def test_get_db_connection_acquisition_failure():
    """Verifies that if getconn() fails, putconn() is not called on an unacquired connection."""
    mock_pool = MagicMock()
    mock_pool.getconn.side_effect = psycopg2.pool.PoolError("The connection pool is exhausted")

    with patch("backend.app.db.get_db_pool", return_value=mock_pool):
        with pytest.raises(psycopg2.pool.PoolError, match="exhausted"):
            with get_db_connection():
                pass

    mock_pool.putconn.assert_not_called()


def test_get_db_cursor_commit_and_cleanup():
    """Verifies that get_db_cursor commits on clean exit when commit=True."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.closed = False
    mock_conn.get_transaction_status.return_value = extensions.TRANSACTION_STATUS_IDLE
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_pool.getconn.return_value = mock_conn

    with patch("backend.app.db.get_db_pool", return_value=mock_pool):
        with get_db_cursor(commit=True) as cur:
            cur.execute("SELECT 1;")

    mock_conn.commit.assert_called_once()
    mock_cur.execute.assert_called_once_with("SELECT 1;")


def test_get_db_cursor_propagates_original_exception():
    """Verifies that query exceptions inside cursor context are preserved exactly."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.closed = False
    mock_conn.get_transaction_status.side_effect = [
        extensions.TRANSACTION_STATUS_INERROR,
        extensions.TRANSACTION_STATUS_IDLE,
    ]
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_pool.getconn.return_value = mock_conn

    with patch("backend.app.db.get_db_pool", return_value=mock_pool):
        with pytest.raises(psycopg2.ProgrammingError, match="syntax error at or near"):
            with get_db_cursor() as cur:
                raise psycopg2.ProgrammingError("syntax error at or near 'SELEKT'")

    mock_conn.rollback.assert_called_once()


def test_is_transient_db_error():
    """Verifies classification of transient vs permanent database errors."""
    transient_err = psycopg2.OperationalError("server closed the connection unexpectedly")
    auth_err = psycopg2.OperationalError("password authentication failed for user 'postgres'")
    missing_db_err = psycopg2.OperationalError('database "nonexistent" does not exist')
    perm_prog_err = psycopg2.ProgrammingError("relation does not exist")
    perm_int_err = psycopg2.IntegrityError("duplicate key value violates unique constraint")

    assert is_transient_db_error(transient_err) is True
    assert is_transient_db_error(auth_err) is False
    assert is_transient_db_error(missing_db_err) is False
    assert is_transient_db_error(perm_prog_err) is False
    assert is_transient_db_error(perm_int_err) is False


def test_retry_transient_db_operation_success_after_retry():
    """Verifies retry of transient failures up to success with backoff."""
    call_count = 0
    slept = []

    def flaky_operation():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise psycopg2.OperationalError("could not connect to server: Connection refused")
        return "SUCCESS"

    result = retry_transient_db_operation(
        flaky_operation,
        max_retries=3,
        initial_delay=0.1,
        sleep_fn=lambda s: slept.append(s),
    )

    assert result == "SUCCESS"
    assert call_count == 3
    assert len(slept) == 2


def test_retry_transient_db_operation_permanent_error_no_retry():
    """Verifies that non-transient errors (e.g. invalid credentials) fail immediately without retries."""
    call_count = 0
    slept = []

    def auth_failing_operation():
        nonlocal call_count
        call_count += 1
        raise psycopg2.OperationalError("password authentication failed for user 'postgres'")

    with pytest.raises(psycopg2.OperationalError, match="password authentication failed"):
        retry_transient_db_operation(
            auth_failing_operation,
            max_retries=3,
            initial_delay=0.1,
            sleep_fn=lambda s: slept.append(s),
        )

    assert call_count == 1
    assert len(slept) == 0


def test_retry_transient_db_operation_exhausted():
    """Verifies that exhausting retries preserves the original exception."""
    call_count = 0
    slept = []

    def permanently_offline():
        nonlocal call_count
        call_count += 1
        raise psycopg2.OperationalError("Connection reset by peer")

    with pytest.raises(psycopg2.OperationalError, match="Connection reset by peer"):
        retry_transient_db_operation(
            permanently_offline,
            max_retries=2,
            initial_delay=0.1,
            sleep_fn=lambda s: slept.append(s),
        )

    assert call_count == 3  # Initial attempt + 2 retries
    assert len(slept) == 2


def test_check_db_health_failure_sanitized():
    """Verifies that check_db_health returns a sanitized generic error message without leaking sensitive credentials."""
    from backend.app.db import check_db_health

    with patch("backend.app.db.get_db_cursor", side_effect=psycopg2.OperationalError("password authentication failed for user 'postgres'")):
        result = check_db_health()
        assert result["connected"] is False
        assert result["status"] == "unreachable"
        assert result["error"] == "Database connectivity check failed"
        assert "password" not in result["error"]
