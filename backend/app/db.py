"""
Database connection management, connection pooling, and resilient query execution.
Provides connection pool hygiene, transaction rollback guarantees, broken-connection
disposal, and bounded retries for transient connection errors.
"""

from __future__ import annotations

import logging
import random
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, TypeVar

import psycopg2
from psycopg2 import extensions, pool, sql
import psycopg2.extras

from backend.app.config import settings

logger = logging.getLogger("rail_signal.db")

_connection_pool: Optional[pool.SimpleConnectionPool] = None

T = TypeVar("T")

# Non-transient error substrings (should never be retried)
_NON_TRANSIENT_PATTERNS = (
    "password authentication failed",
    "does not exist",
    "permission denied",
    "syntax error",
    "unique violation",
    "foreign key violation",
    "check constraint",
    "not null violation",
)


def is_transient_db_error(exc: Exception) -> bool:
    """
    Determines whether an exception represents a genuinely transient connection failure
    (e.g., temporary network reset, backend starting up) versus a permanent error.
    """
    if isinstance(exc, psycopg2.OperationalError):
        msg = str(exc).lower()
        for pattern in _NON_TRANSIENT_PATTERNS:
            if pattern in msg:
                return False
        return True
    return False


def retry_transient_db_operation(
    operation: Callable[[], T],
    max_retries: int = 3,
    initial_delay: float = 0.1,
    backoff_factor: float = 2.0,
    max_delay: float = 2.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> T:
    """
    Executes an operation with bounded retries and exponential backoff with jitter
    for transient database connection failures. Never retries permanent errors.
    """
    attempt = 0
    delay = initial_delay

    while True:
        try:
            return operation()
        except Exception as exc:
            attempt += 1
            if attempt > max_retries or not is_transient_db_error(exc):
                raise exc

            # Calculate jittered exponential backoff
            jitter = random.uniform(0.8, 1.2)
            sleep_duration = min(delay * jitter, max_delay)
            logger.warning(
                "Transient database error on attempt %d/%d: %s. Retrying in %.3fs...",
                attempt,
                max_retries,
                str(exc).splitlines()[0],
                sleep_duration,
            )
            sleep_fn(sleep_duration)
            delay *= backoff_factor


def get_db_pool() -> pool.SimpleConnectionPool:
    """Initializes or returns the thread-safe connection pool with transient retry support."""
    global _connection_pool
    if _connection_pool is None or _connection_pool.closed:
        def _create_pool():
            return pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                host=settings.postgres_host,
                port=settings.postgres_port,
                dbname=settings.postgres_db,
                user=settings.postgres_user,
                password=settings.postgres_password,
                connect_timeout=5,
            )

        try:
            _connection_pool = retry_transient_db_operation(
                _create_pool,
                max_retries=3,
                initial_delay=0.1,
            )
            logger.info("PostgreSQL connection pool initialized.")
        except Exception as exc:
            logger.error("Failed to initialize PostgreSQL pool: %s", exc)
            raise exc
    return _connection_pool


def close_db_pool() -> None:
    """Closes all pooled connections and resets pool reference."""
    global _connection_pool
    if _connection_pool is not None and not _connection_pool.closed:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("PostgreSQL connection pool closed.")


@contextmanager
def get_db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Yields a connection from the pool and automatically returns it.

    Guarantees:
    1. Failed or unfinished transactions are rolled back before returning to pool.
    2. Original exceptions are preserved and propagated without masking.
    3. If rollback fails or connection is closed/broken, it is discarded via putconn(conn, close=True).
    4. Cursors are closed reliably.
    5. Double-returning connections is prevented via returned flag.
    6. Acquisition failures do not attempt to return an unacquired connection.
    """
    db_pool = get_db_pool()
    conn: Optional[psycopg2.extensions.connection] = None
    conn_returned = False
    is_broken = False

    try:
        conn = db_pool.getconn()
    except Exception as acq_exc:
        logger.error("Failed to acquire connection from pool: %s", acq_exc)
        raise acq_exc

    try:
        yield conn
    except Exception as exc:
        # Transaction cleanup on exception
        if conn and not getattr(conn, "closed", True):
            try:
                tx_status = conn.get_transaction_status()
                if tx_status != extensions.TRANSACTION_STATUS_IDLE:
                    conn.rollback()
            except Exception as rb_exc:
                logger.warning("Rollback failed on broken connection: %s", rb_exc)
                is_broken = True
        raise exc
    finally:
        if not conn_returned and conn is not None:
            try:
                is_closed = getattr(conn, "closed", True)
                if is_broken or is_closed:
                    # Broken or closed connection: eliminate from pool
                    db_pool.putconn(conn, close=True)
                else:
                    # Verify transaction state before returning
                    tx_status = conn.get_transaction_status()
                    if tx_status != extensions.TRANSACTION_STATUS_IDLE:
                        try:
                            conn.rollback()
                            db_pool.putconn(conn, close=False)
                        except Exception as rb_err:
                            logger.warning("Final transaction rollback failed; closing connection: %s", rb_err)
                            db_pool.putconn(conn, close=True)
                    else:
                        db_pool.putconn(conn, close=False)
            except Exception as put_err:
                logger.error("Failed to return connection to pool: %s", put_err)
            finally:
                conn_returned = True


@contextmanager
def get_db_cursor(commit: bool = False) -> Generator[psycopg2.extras.RealDictCursor, None, None]:
    """
    Yields a RealDictCursor with automatic connection recycling and error handling.
    Commits on clean exit if commit=True. Automatically triggers connection rollback on error.
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            try:
                yield cur
                if commit:
                    conn.commit()
            except Exception:
                # Exception propagates to get_db_connection which performs rollback
                raise


def check_db_health() -> Dict[str, Any]:
    """Performs a lightweight ping check to verify database readiness."""
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT 1 AS ready, current_database() AS db_name;")
            res = cur.fetchone()
            return {
                "connected": True,
                "database": res["db_name"],
                "status": "ready",
            }
    except Exception as exc:
        logger.warning("Database health check failed: %s", exc)
        return {
            "connected": False,
            "database": settings.postgres_db,
            "status": "unreachable",
            "error": str(exc),
        }
