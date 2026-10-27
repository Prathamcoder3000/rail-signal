"""
PostgreSQL Session-Level Advisory Locking for RAIL / SIGNAL Pipeline Concurrency.

Provides distributed mutual exclusion across concurrent CLI and background orchestrator
processes using dedicated PostgreSQL advisory lock sessions.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

import psycopg2
from psycopg2 import sql

from backend.app.config import settings

logger = logging.getLogger("rail_signal.advisory_lock")

# Documented 64-bit integer key for RAIL / SIGNAL orchestrator operations
RAIL_SIGNAL_ORCHESTRATOR_ADVISORY_LOCK_KEY: int = 842091238471


class AdvisoryLockContentionError(Exception):
    """Raised when another pipeline orchestrator process holds the advisory lock."""
    pass


class AdvisoryLockConnectionError(Exception):
    """Raised when the dedicated advisory lock database connection fails."""
    pass


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
    4. Releases lock in finally block via `SELECT pg_advisory_unlock(%s)`.
    5. Closes dedicated connection on all exit paths.
    """
    conn: Optional[psycopg2.extensions.connection] = None
    lock_acquired = False

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
        logger.error("Failed to establish dedicated connection for advisory lock: %s", exc)
        raise AdvisoryLockConnectionError(f"Could not connect to database for advisory lock: {exc}") from exc

    try:
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
        yield True

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
