"""Database helper module.

Centralizes SQLAlchemy engine creation and provides small helpers
used by the Flask app for runtime DB checks. Keeps code minimal and
avoids introducing ORM models or migrations at this stage.

SECURITY & RELIABILITY:
- Thread-safe singleton pattern with double-checked locking
- Explicit connection pool configuration
- Connection timeouts to prevent hanging
- Proper exception handling
"""
import threading
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError, OperationalError

from config import (
    SQLALCHEMY_DATABASE_URI,
    DB_POOL_SIZE,
    DB_MAX_OVERFLOW,
    DB_POOL_TIMEOUT,
    DB_POOL_RECYCLE,
    DB_CONNECT_TIMEOUT,
    DB_NAME,
)


_engine: Optional[Engine] = None
_engine_lock = threading.Lock()


def get_engine() -> Engine:
    """Return a singleton SQLAlchemy Engine configured for the app.

    Thread-safe implementation with double-checked locking pattern.
    Configured with explicit connection pool limits and timeouts.

    Connection Pool Settings:
    - pool_pre_ping: Test connections before using (handle stale connections)
    - pool_size: Base number of connections in the pool
    - max_overflow: Additional connections allowed beyond pool_size
    - pool_timeout: Max seconds to wait for a connection from the pool
    - pool_recycle: Recycle connections after N seconds (prevent stale connections)
    - connect_timeout: MySQL connection timeout in seconds

    Returns:
        Engine: SQLAlchemy Engine instance

    Raises:
        SQLAlchemyError: If engine creation fails
    """
    global _engine
    if _engine is None:
        with _engine_lock:
            # Double-check after acquiring lock (another thread might have created it)
            if _engine is None:
                _engine = create_engine(
                    SQLALCHEMY_DATABASE_URI,
                    pool_pre_ping=True,  # Test connections before use
                    pool_size=DB_POOL_SIZE,  # Base pool size
                    max_overflow=DB_MAX_OVERFLOW,  # Max additional connections
                    pool_timeout=DB_POOL_TIMEOUT,  # Wait timeout for connection
                    pool_recycle=DB_POOL_RECYCLE,  # Recycle after 1 hour
                    connect_args={
                        "connect_timeout": DB_CONNECT_TIMEOUT,  # MySQL connect timeout
                    },
                )
    return _engine


def validate_database() -> None:
    """Validate database connection and schema on application startup.

    Performs critical checks:
    1. Connection is successful
    2. Connected to the correct database
    3. Required tables exist (users table)

    Raises:
        OperationalError: If database connection fails
        ValueError: If connected to wrong database or schema is invalid
    """
    engine = get_engine()
    try:
        with engine.connect() as conn:
            # Verify we're connected to the correct database
            current_db = conn.execute(text("SELECT DATABASE()")).scalar()
            if current_db != DB_NAME:
                raise ValueError(
                    f"Connected to wrong database: '{current_db}', expected '{DB_NAME}'"
                )

            # Verify users table exists
            result = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = :db AND table_name = 'users'"
                ),
                {"db": DB_NAME},
            ).scalar()

            if result == 0:
                raise ValueError(
                    f"Database schema not initialized: 'users' table missing in '{DB_NAME}'. "
                    "Please run schema_init.sql first."
                )
    except OperationalError as exc:
        raise OperationalError(
            f"Database connection failed: {exc}",
            params=None,
            orig=exc,
        ) from exc


def check_connection() -> int:
    """Run a lightweight SELECT 1 to verify DB connectivity.

    Returns the integer result (1) on success.

    Returns:
        int: 1 if connection is successful

    Raises:
        OperationalError: If database connection fails
        SQLAlchemyError: For other database errors
    """
    engine = get_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            return int(result)
    except OperationalError:
        # Re-raise operational errors (connection issues) as-is
        raise
    except SQLAlchemyError:
        # Re-raise other SQLAlchemy errors
        raise


def count_users() -> int:
    """Return the number of rows in the `users` table.

    This is intentionally simple: it executes `SELECT COUNT(*)` and
    returns an integer. The function will raise an exception if the
    table doesn't exist or there is a DB error.

    Returns:
        int: Number of users in the database

    Raises:
        OperationalError: If database connection fails
        SQLAlchemyError: For other database errors
    """
    engine = get_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM users"))
            return int(result.scalar() or 0)
    except OperationalError:
        raise
    except SQLAlchemyError:
        raise


def get_or_create_user(
    auth0_sub: str,
    email: str,
    display_name: Optional[str] = None,
) -> Optional[int]:
    """Get existing user by auth0_sub or create new user if not exists.

    This is the core user synchronization function called after Auth0 login.
    It ensures every authenticated user has a corresponding row in the users table.

    ROLE MANAGEMENT: Roles are managed locally in the database:
    - Existing users: Preserve their current role
    - New users: Default to 'user' role

    ACTIVE STATUS: Deactivated users (is_active=False) cannot log in.

    Args:
        auth0_sub: Auth0 subject ID (unique identifier from Auth0)
        email: User's email address
        display_name: User's display name (optional)

    Returns:
        int | None: User ID from database, or None if user is deactivated

    Raises:
        SQLAlchemyError: If database operation fails
    """
    engine = get_engine()
    try:
        with engine.begin() as conn:
            # Check if user already exists
            existing = conn.execute(
                text("SELECT id, is_active FROM users WHERE auth0_sub = :sub"),
                {"sub": auth0_sub},
            ).fetchone()

            if existing:
                user_id, is_active = existing
                if not is_active:
                    # User is deactivated - deny login
                    return None

                # User exists and is active - update email/display_name and last_login
                conn.execute(
                    text(
                        "UPDATE users SET "
                        "email = :email, "
                        "display_name = :display_name, "
                        "last_login_at = CURRENT_TIMESTAMP "
                        "WHERE auth0_sub = :sub"
                    ),
                    {
                        "sub": auth0_sub,
                        "email": email,
                        "display_name": display_name,
                    },
                )
                return user_id
            else:
                # New user - create with default role 'user' and is_active=True
                result = conn.execute(
                    text(
                        "INSERT INTO users "
                        "(auth0_sub, email, display_name, role, is_active, last_login_at) "
                        "VALUES (:sub, :email, :display_name, 'user', TRUE, CURRENT_TIMESTAMP)"
                    ),
                    {
                        "sub": auth0_sub,
                        "email": email,
                        "display_name": display_name,
                    },
                )
                return result.lastrowid
    except SQLAlchemyError:
        raise


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Get user by ID and return as dictionary.

    Args:
        user_id: User ID

    Returns:
        dict | None: User data or None if not found
    """
    engine = get_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT id, auth0_sub, email, display_name, role, is_active "
                    "FROM users WHERE id = :user_id"
                ),
                {"user_id": user_id},
            ).fetchone()

            if result:
                return {
                    "id": result[0],
                    "auth0_sub": result[1],
                    "email": result[2],
                    "display_name": result[3],
                    "role": result[4],
                    "is_active": bool(result[5]),
                }
            return None
    except SQLAlchemyError:
        raise
