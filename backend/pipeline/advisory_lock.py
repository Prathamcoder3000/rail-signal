"""
PostgreSQL Session-Level Advisory Locking for RAIL / SIGNAL Pipeline Concurrency.

Provides distributed mutual exclusion across concurrent CLI and background orchestrator
processes using dedicated PostgreSQL advisory lock sessions.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Tuple

import psycopg2
from psycopg2 import sql

from backend.app.config import settings
from backend.pipeline.monitoring import sanitize_error_message

logger = logging.getLogger("rail_signal.advisory_lock")

# Documented 64-bit integer key for RAIL / SIGNAL orchestrator operations
RAIL_SIGNAL_ORCHESTRATOR_ADVISORY_LOCK_KEY: int = 842091238471

_LOCK_STATE = threading.local()


class AdvisoryLockContentionError(Exception):
    """Raised when another pipeline orchestrator process holds the advisory lock."""
    pass


class AdvisoryLockConnectionError(Exception):
    """Raised when the dedicated advisory lock database connection fails or is lost."""
    pass


def get_active_advisory_lock_connection() -> Optional[Any]:
    """Returns the dedicated database connection holding the active advisory lock on this thread."""
    stack: Optional[List[Tuple[Any, int]]] = getattr(_LOCK_STATE, "stack", None)
    if stack:
        return stack[-1][0]
    return None


def get_active_advisory_lock_key() -> Optional[int]:
    """Returns the lock key of the active advisory lock on this thread."""
    stack: Optional[List[Tuple[Any, int]]] = getattr(_LOCK_STATE, "stack", None)
    if stack:
        return stack[-1][1]
    return None


def is_pipeline_advisory_lock_held(
    lock_key: int = RAIL_SIGNAL_ORCHESTRATOR_ADVISORY_LOCK_KEY,
    conn: Optional[Any] = None,
) -> bool:
    """
    Verifies that the dedicated PostgreSQL connection is alive and actively holds
    the exclusive advisory lock for `lock_key` in `pg_locks`.

    Guarantees:
    1. Uses the original lock-owning connection directly.
    2. Does NOT execute `pg_advisory_unlock_shared()` or mutate lock state.
    3. Checks `pg_locks` for `locktype = 'advisory'`, matching the session backend PID
       (`pid = pg_backend_pid()`), the 64-bit lock key formula, and `granted = true`.
    4. Detects closed, terminated, or broken connections without throwing unhandled driver errors.
    """
    target_conn = conn if conn is not None else get_active_advisory_lock_connection()
    if target_conn is None:
        return False

    if getattr(target_conn, "closed", 1) != 0:
        return False

    try:
        with target_conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM pg_locks
                WHERE locktype = 'advisory'
                  AND pid = pg_backend_pid()
                  AND ((classid::bigint << 32) | (objid::bigint & 4294967295)) = %s
                  AND objsubid = 1
                  AND mode = 'ExclusiveLock'
                  AND granted = true;
                """,
                (lock_key,),
            )
            row = cur.fetchone()
            if not row:
                return False
            val = row[0] if isinstance(row, (tuple, list)) else (list(row.values())[0] if isinstance(row, dict) else row)
            return bool(val)
    except Exception as exc:
        sanitized = sanitize_error_message(exc)
        logger.warning(
            "Advisory lock liveness probe failed on session connection (lock_key=%d): %s",
            lock_key,
            sanitized,
        )
        return False


def assert_pipeline_advisory_lock_held(
    lock_key: int = RAIL_SIGNAL_ORCHESTRATOR_ADVISORY_LOCK_KEY,
    conn: Optional[Any] = None,
) -> None:
    """
    Asserts that the dedicated PostgreSQL session holding the exclusive advisory lock is still alive
    and verified in pg_locks.

    Raises:
        AdvisoryLockConnectionError: If the connection is closed, lost, unreachable, or
                                     if the advisory lock is no longer granted in pg_locks.
    """
    target_conn = conn if conn is not None else get_active_advisory_lock_connection()
    if target_conn is None:
        msg = (
            f"Advisory lock liveness check failed: no active lock connection exists on the current thread "
            f"(expected lock_key={lock_key}). Halting before database write operations."
        )
        logger.error(msg)
        raise AdvisoryLockConnectionError(msg)

    if getattr(target_conn, "closed", 1) != 0:
        msg = (
            f"Advisory lock connection is closed (closed={getattr(target_conn, 'closed', 1)}). "
            f"Advisory lock (key={lock_key}) is no longer held. Halting before database write operations."
        )
        logger.error(msg)
        raise AdvisoryLockConnectionError(msg)

    if not is_pipeline_advisory_lock_held(lock_key=lock_key, conn=target_conn):
        msg = (
            f"Advisory lock verification failed: dedicated session is not holding exclusive lock "
            f"(key={lock_key}) in pg_locks. The connection may have dropped or been reset. "
            f"Halting execution to prevent uncoordinated database writes."
        )
        logger.error(msg)
        raise AdvisoryLockConnectionError(msg)


@contextmanager
def acquire_pipeline_advisory_lock(
    lock_key: int = RAIL_SIGNAL_ORCHESTRATOR_ADVISORY_LOCK_KEY,
    connection_factory: Optional[Any] = None,
) -> Generator[bool, None, None]:
    """
    Context manager acquiring a non-blocking PostgreSQL session-level advisory lock.

    Guarantees:
    1. Uses a dedicated database connection separate from any connection pool.
    2. Non-blocking attempt: `SELECT pg_try_advisory_lock(%s)`.
    3. If held by another process, raises AdvisoryLockContentionError immediately.
    4. Tracks active session in thread-local storage for liveness assertions throughout execution.
    5. Releases lock in finally block via `SELECT pg_advisory_unlock(%s)`.
    6. Closes dedicated connection on all exit paths.
    """
    conn: Optional[psycopg2.extensions.connection] = None
    lock_acquired = False

    try:
        try:
            if connection_factory is not None:
                conn = connection_factory()
            else:
                conn = psycopg2.connect(
                    host=settings.postgres_host,
                    port=settings.postgres_port,
                    dbname=settings.postgres_db,
                    user=settings.postgres_user,
                    password=settings.postgres_password,
                    connect_timeout=5,
                )
        except Exception as exc:
            sanitized = sanitize_error_message(exc)
            logger.error("Failed to establish dedicated connection for advisory lock: %s", sanitized)
            raise AdvisoryLockConnectionError(f"Could not connect to database for advisory lock: {sanitized}") from exc

        try:
            conn.autocommit = True
        except Exception as auto_err:
            sanitized = sanitize_error_message(auto_err)
            logger.error("Failed to enable autocommit on dedicated advisory lock connection: %s", sanitized)
            raise AdvisoryLockConnectionError(f"Could not configure autocommit on advisory lock connection: {sanitized}") from auto_err

        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s);", (lock_key,))
            res = cur.fetchone()
            lock_acquired = bool(res[0] if isinstance(res, (list, tuple)) else res["pg_try_advisory_lock"])

        if not lock_acquired:
            msg = (
                f"Pipeline advisory lock is currently held by another active process "
                f"(lock_key={lock_key}). Aborting execution to prevent concurrent write conflicts."
            )
            logger.warning(msg)
            raise AdvisoryLockContentionError(msg)

        logger.info("Acquired PostgreSQL advisory lock (key=%d).", lock_key)

        if not hasattr(_LOCK_STATE, "stack"):
            _LOCK_STATE.stack = []
        _LOCK_STATE.stack.append((conn, lock_key))

        try:
            yield True
        finally:
            if getattr(_LOCK_STATE, "stack", None):
                try:
                    _LOCK_STATE.stack.pop()
                except IndexError:
                    pass

    finally:
        if conn and not getattr(conn, "closed", True):
            if lock_acquired:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT pg_advisory_unlock(%s);", (lock_key,))
                    logger.info("Released PostgreSQL advisory lock (key=%d).", lock_key)
                except Exception as unlock_err:
                    logger.error("Failed to release advisory lock (key=%d): %s", lock_key, unlock_err)
            try:
                conn.close()
            except Exception as close_err:
                logger.warning("Error closing advisory lock connection: %s", close_err)
