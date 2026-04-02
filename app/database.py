"""Database helper module.

Centralizes SQLAlchemy engine creation and provides small helpers
used by the Flask app for runtime DB checks. Keeps code minimal and
avoids introducing ORM models or migrations at this stage.
"""
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from config import SQLALCHEMY_DATABASE_URI


_engine: Optional[Engine] = None


def get_engine() -> Engine:
    """Return a singleton SQLAlchemy Engine configured for the app.

    Uses `pool_pre_ping=True` to avoid stale connections when the DB
    is temporarily unavailable (common in containerized environments).
    """
    global _engine
    if _engine is None:
        _engine = create_engine(SQLALCHEMY_DATABASE_URI, pool_pre_ping=True)
    return _engine


def check_connection() -> int:
    """Run a lightweight SELECT 1 to verify DB connectivity.

    Returns the integer result (1) on success or raises the underlying
    SQLAlchemyError on failure.
    """
    engine = get_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            return int(result)
    except SQLAlchemyError:
        # Re-raise to let the caller decide how to surface the error
        raise


def count_users() -> int:
    """Return the number of rows in the `users` table.

    This is intentionally simple: it executes `SELECT COUNT(*)` and
    returns an integer. The function will raise an exception if the
    table doesn't exist or there is a DB error.
    """
    engine = get_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM users;"))
            return int(result.scalar() or 0)
    except SQLAlchemyError:
        raise
