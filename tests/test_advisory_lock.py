"""
Unit and Integration Tests for PostgreSQL Advisory Locking (backend/pipeline/advisory_lock.py).
Tests non-blocking acquisition, contention detection, automatic unlock on exit/exception,
and dedicated connection cleanup.
"""

from unittest.mock import MagicMock, PropertyMock, patch

import psycopg2
import pytest

from backend.pipeline.advisory_lock import (
    RAIL_SIGNAL_ORCHESTRATOR_ADVISORY_LOCK_KEY,
    AdvisoryLockConnectionError,
    AdvisoryLockContentionError,
    acquire_pipeline_advisory_lock,
    assert_pipeline_advisory_lock_held,
    get_active_advisory_lock_connection,
    get_active_advisory_lock_key,
    is_pipeline_advisory_lock_held,
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
        assert mock_conn.autocommit is True

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


def test_is_pipeline_advisory_lock_held_when_held():
    """Verifies that is_pipeline_advisory_lock_held returns True when the session owns the lock."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (1,)
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_conn.closed = 0

    assert is_pipeline_advisory_lock_held(conn=mock_conn) is True
    call_sql = mock_cur.execute.call_args[0][0]
    assert "FROM pg_locks" in call_sql
    assert "locktype = 'advisory'" in call_sql
    assert "pid = pg_backend_pid()" in call_sql
    assert "granted = true" in call_sql
    # Ensure unlock shared was NOT called as a liveness probe
    for call in mock_cur.execute.call_args_list:
        assert "pg_advisory_unlock_shared" not in str(call)


def test_is_pipeline_advisory_lock_held_when_not_held():
    """Verifies that is_pipeline_advisory_lock_held returns False when lock is absent from pg_locks."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_conn.closed = 0

    assert is_pipeline_advisory_lock_held(conn=mock_conn) is False


def test_is_pipeline_advisory_lock_held_when_connection_closed():
    """Verifies that a closed connection returns False without crashing."""
    mock_conn = MagicMock()
    mock_conn.closed = 1

    assert is_pipeline_advisory_lock_held(conn=mock_conn) is False


def test_is_pipeline_advisory_lock_held_when_connection_raises_error():
    """Verifies that operational errors during lock probe return False gracefully."""
    mock_conn = MagicMock()
    mock_conn.closed = 0
    mock_conn.cursor.side_effect = psycopg2.OperationalError("server terminated connection unexpectedly")

    assert is_pipeline_advisory_lock_held(conn=mock_conn) is False


def test_assert_pipeline_advisory_lock_held_success():
    """Verifies that assert_pipeline_advisory_lock_held passes without error when lock is held."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (1,)
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_conn.closed = 0

    # Should not raise
    assert_pipeline_advisory_lock_held(conn=mock_conn)


def test_assert_pipeline_advisory_lock_held_raises_when_no_active_session():
    """Verifies that assert_pipeline_advisory_lock_held raises AdvisoryLockConnectionError if no session exists."""
    with pytest.raises(AdvisoryLockConnectionError, match="no active lock connection exists"):
        assert_pipeline_advisory_lock_held(conn=None)


def test_assert_pipeline_advisory_lock_held_raises_when_lock_not_in_pg_locks():
    """Verifies that assert_pipeline_advisory_lock_held raises AdvisoryLockConnectionError if lock is missing."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_conn.closed = 0

    with pytest.raises(AdvisoryLockConnectionError, match="not holding exclusive lock"):
        assert_pipeline_advisory_lock_held(conn=mock_conn)


def test_advisory_lock_lifecycle_thread_local_management():
    """Verifies that acquire_pipeline_advisory_lock tracks and cleans up thread-local state."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    # First fetchone: pg_try_advisory_lock returns True
    # Second fetchone: pg_locks check returns (1,)
    mock_cur.fetchone.side_effect = [(True,), (1,)]
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_conn.closed = 0

    assert get_active_advisory_lock_connection() is None
    assert get_active_advisory_lock_key() is None

    with acquire_pipeline_advisory_lock(connection_factory=lambda: mock_conn) as acquired:
        assert acquired is True
        assert get_active_advisory_lock_connection() is mock_conn
        assert get_active_advisory_lock_key() == RAIL_SIGNAL_ORCHESTRATOR_ADVISORY_LOCK_KEY
        # Assertion on the active session should succeed
        assert_pipeline_advisory_lock_held()

    # After exit, thread-local state is cleared
    assert get_active_advisory_lock_connection() is None
    assert get_active_advisory_lock_key() is None
    with pytest.raises(AdvisoryLockConnectionError):
        assert_pipeline_advisory_lock_held()


def test_advisory_lock_autocommit_enabled():
    """
    F-04 test: Verifies that acquire_pipeline_advisory_lock sets conn.autocommit = True
    on the dedicated connection, ensuring session-level locks do not remain idle in a transaction block.
    """
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (True,)
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_conn.closed = False
    mock_conn.autocommit = False

    with acquire_pipeline_advisory_lock(connection_factory=lambda: mock_conn):
        assert mock_conn.autocommit is True


def test_advisory_lock_autocommit_failure_fails_safely_and_closes_connection():
    """
    F-04 safety test: Verifies that if enabling autocommit on the dedicated connection fails:
    1. Advisory-lock acquisition (SELECT pg_try_advisory_lock) is NOT attempted.
    2. The dedicated connection is closed cleanly without leaking.
    3. AdvisoryLockConnectionError is raised, preserving the cause.
    4. No advisory unlock is executed (since lock was not acquired).
    5. Inner block is never entered (no database writes or commits occur).
    """
    class FailingAutocommitConnection(MagicMock):
        pass

    mock_conn = FailingAutocommitConnection()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_conn.closed = False

    # Simulate autocommit property setter raising an OperationalError
    type(mock_conn).autocommit = PropertyMock(side_effect=psycopg2.OperationalError("Cannot toggle autocommit"))

    inner_executed = False
    with pytest.raises(AdvisoryLockConnectionError, match="Could not configure autocommit") as exc_info:
        with acquire_pipeline_advisory_lock(connection_factory=lambda: mock_conn):
            inner_executed = True

    # 1. Inner protected block was never entered
    assert inner_executed is False
    # 2. Original cause is preserved
    assert isinstance(exc_info.value.__cause__, psycopg2.OperationalError)
    # 3. Lock acquisition was NEVER attempted
    mock_cur.execute.assert_not_called()
    # 4. Dedicated connection was closed safely
    mock_conn.close.assert_called_once()
    # 5. No unlock was attempted
    for call in mock_cur.execute.call_args_list:
        assert "pg_advisory_unlock" not in str(call)
