"""Database connection management and query execution."""

from contextlib import contextmanager
import logging
from typing import Any, Dict, Generator, List, Optional
import psycopg2
from psycopg2 import pool, sql
import psycopg2.extras

from backend.app.config import settings

logger = logging.getLogger("rail_signal.db")

_connection_pool: Optional[pool.SimpleConnectionPool] = None


def get_db_pool() -> pool.SimpleConnectionPool:
    global _connection_pool
    if _connection_pool is None or _connection_pool.closed:
        try:
            _connection_pool = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                host=settings.postgres_host,
                port=settings.postgres_port,
                dbname=settings.postgres_db,
                user=settings.postgres_user,
                password=settings.postgres_password,
                connect_timeout=5,
            )
            logger.info("PostgreSQL connection pool initialized.")
        except Exception as exc:
            logger.error("Failed to initialize PostgreSQL pool: %s", exc)
            raise exc
    return _connection_pool


def close_db_pool() -> None:
    global _connection_pool
    if _connection_pool is not None and not _connection_pool.closed:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("PostgreSQL connection pool closed.")


@contextmanager
def get_db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """Yields a connection from the pool and automatically returns it."""
    db_pool = get_db_pool()
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)


@contextmanager
def get_db_cursor(commit: bool = False) -> Generator[psycopg2.extras.RealDictCursor, None, None]:
    """Yields a RealDictCursor with automatic connection recycling and error handling."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
            if commit:
                conn.commit()


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
