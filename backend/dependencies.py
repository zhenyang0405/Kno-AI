from auth import get_current_user as _get_current_user
from setup import bucket
import config
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager


# Re-export auth dependency
get_current_user = _get_current_user


# PostgreSQL connection pool
_db_pool = None


def get_db_pool():
    """Get or create PostgreSQL connection pool."""
    global _db_pool
    if _db_pool is None:
        _db_pool = pool.SimpleConnectionPool(
            1,  # minconn
            10,  # maxconn
            host=config.DB_HOST,
            database=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASS,
            port=config.DB_PORT
        )
    return _db_pool


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    Usage:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(...)
    """
    pool = get_db_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def get_db_cursor():
    """
    Dependency for FastAPI routes to get a database cursor.
    Note: This returns a connection that must be properly closed.
    """
    pool = get_db_pool()
    conn = pool.getconn()
    return conn


def close_db_connection(conn):
    """Close and return connection to the pool."""
    pool = get_db_pool()
    pool.putconn(conn)


def get_storage_bucket():
    """Get Cloud Storage bucket instance."""
    return bucket
