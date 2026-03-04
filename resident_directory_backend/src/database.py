"""
Database connection and utilities for PostgreSQL.
Uses psycopg2 for direct database access.
"""
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager
from typing import Generator, Optional
import logging

from src.config import settings

logger = logging.getLogger(__name__)

# Connection pool for better performance
connection_pool: Optional[SimpleConnectionPool] = None


def init_db_pool(minconn: int = 1, maxconn: int = 10):
    """
    Initialize the database connection pool.
    
    Args:
        minconn: Minimum number of connections in the pool
        maxconn: Maximum number of connections in the pool
    """
    global connection_pool  # noqa: F824
    try:
        connection_pool = SimpleConnectionPool(
            minconn,
            maxconn,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            host="localhost",
            port=settings.POSTGRES_PORT,
            database=settings.POSTGRES_DB
        )
        logger.info("Database connection pool initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database pool: {e}")
        raise


def close_db_pool():
    """Close all connections in the pool."""
    global connection_pool
    if connection_pool:
        connection_pool.closeall()
        connection_pool = None
        logger.info("Database connection pool closed")


@contextmanager
def get_db_connection():
    """
    Get a database connection from the pool.
    Automatically returns the connection to the pool after use.
    
    Yields:
        psycopg2 connection with RealDictCursor
    """
    if connection_pool is None:
        init_db_pool()
    
    conn = connection_pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        connection_pool.putconn(conn)


@contextmanager
def get_db_cursor(conn=None) -> Generator:
    """
    Get a database cursor that returns results as dictionaries.
    
    Args:
        conn: Optional existing connection. If None, gets from pool.
        
    Yields:
        psycopg2 cursor with RealDictCursor
    """
    if conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
        finally:
            cursor.close()
    else:
        with get_db_connection() as connection:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            try:
                yield cursor
            finally:
                cursor.close()


def test_db_connection() -> bool:
    """
    Test the database connection.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                logger.info("Database connection test successful")
                return result is not None
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False
