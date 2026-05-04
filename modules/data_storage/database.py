"""
Database Connection Management

Handles SQLAlchemy engine creation, session management, and database initialization.
Supports both SQLite (local development) and PostgreSQL (production).
"""

import os
from typing import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, scoped_session, Session
from sqlalchemy.pool import StaticPool
from loguru import logger

# Load database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./economic_data.db')

# Handle Render.com PostgreSQL URL format (postgres:// -> postgresql://)
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Determine if we're using SQLite
IS_SQLITE = DATABASE_URL.startswith('sqlite')

# Configure engine based on database type
if IS_SQLITE:
    # SQLite configuration for local development
    engine = create_engine(
        DATABASE_URL,
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
        echo=os.getenv('DEBUG', 'false').lower() == 'true'
    )
    
    # Enable foreign key support for SQLite
    @event.listens_for(engine, 'connect')
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()
else:
    # PostgreSQL configuration for production
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Verify connections before use
        pool_recycle=300,    # Recycle connections every 5 minutes
        echo=os.getenv('DEBUG', 'false').lower() == 'true'
    )

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Scoped session for thread safety
ScopedSession = scoped_session(SessionLocal)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection for FastAPI endpoints.
    
    Usage:
        @app.get('/endpoint')
        def my_endpoint(db: Session = Depends(get_db)):
            ...
    
    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database operations outside FastAPI.
    
    Usage:
        with get_db_context() as db:
            db.query(FXRate).all()
    
    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database tables.

    Creates all tables defined in schema.py if they don't exist.
    Safe to call multiple times - won't destroy existing data.
    """
    from .schema import Base

    logger.info(f"Initializing database: {DATABASE_URL[:50]}...")

    try:
        Base.metadata.create_all(bind=engine)
        logger.success("Database tables created successfully!")

        # Log created tables
        for table_name in Base.metadata.tables.keys():
            logger.info(f"  ✓ Table: {table_name}")

        # Idempotent column additions for in-place migrations. Safe to call
        # repeatedly — each helper checks for the column and skips if present.
        _ensure_column(
            table="ai_market_journal",
            column="pillar_scores_snapshot",
            sqlite_type="JSON",
            postgres_type="JSON",
        )
        # Promote the existing alert_hash index to UNIQUE (third-pass debug
        # review). Closes the race window in alerts._emit between dedup
        # check and insert: concurrent writers can no longer commit two
        # rows with the same alert_hash; the second writer's IntegrityError
        # is caught as "dedup-resolved by the constraint" in _emit.
        _ensure_unique_index(
            table="risk_alerts",
            column="alert_hash",
            index_name="ux_risk_alerts_alert_hash",
        )

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def _ensure_column(
    table: str,
    column: str,
    sqlite_type: str,
    postgres_type: str,
) -> None:
    """
    Add a column to `table` if it doesn't already exist.

    SQLite: PRAGMA table_info to detect, then ALTER TABLE ADD COLUMN.
    PostgreSQL: information_schema.columns to detect, then ALTER TABLE ADD COLUMN.

    Both branches are no-ops if the column is already present, so this can run
    on every startup without side effects.
    """
    try:
        with engine.begin() as conn:
            if IS_SQLITE:
                rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
                existing = {row[1] for row in rows}  # row[1] = column name
                if column in existing:
                    return
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sqlite_type}"))
                logger.info(f"  + Added column {table}.{column} ({sqlite_type})")
            else:
                # Filter on table_schema='public' so a same-named column
                # in another schema (multi-tenant Render/Neon setups)
                # doesn't short-circuit the add on the public table.
                check = text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = 'public' "
                    "AND table_name = :t AND column_name = :c"
                )
                if conn.execute(check, {"t": table, "c": column}).fetchone():
                    return
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {postgres_type}"))
                logger.info(f"  + Added column {table}.{column} ({postgres_type})")
    except Exception as e:
        # Don't crash startup on a migration that can't run — log and continue.
        logger.warning(f"  Could not ensure column {table}.{column}: {e}")


def _ensure_unique_index(
    table: str,
    column: str,
    index_name: str,
) -> None:
    """Promote an indexed column to a UNIQUE index in-place.

    SQLite: ALTER TABLE doesn't support adding UNIQUE constraints to
    existing columns, so we use CREATE UNIQUE INDEX. Both engines treat
    a unique index as semantically equivalent to a unique constraint
    for IntegrityError dedup behavior.

    Postgres: uses CREATE UNIQUE INDEX CONCURRENTLY so a hot deploy on a
    busy table (e.g. `risk_alerts` written every 5 min by the scorecard)
    doesn't block reads/writes for the duration of the build. CONCURRENTLY
    cannot run inside a transaction, so the Postgres branch uses
    `engine.connect()` in autocommit mode rather than `engine.begin()`.

    Idempotent: skips when an index of `index_name` already exists.
    Will fail with a clear log if pre-existing duplicate values block
    the index creation; in that case clean up duplicates manually first.
    """
    try:
        if IS_SQLITE:
            with engine.begin() as conn:
                rows = conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='index' AND name=:n"),
                    {"n": index_name},
                ).fetchall()
                if rows:
                    return
                conn.execute(
                    text(f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table}({column})")
                )
                logger.info(f"  + Added unique index {index_name} on {table}.{column}")
        else:
            # Postgres: idempotency check + autocommit-mode CONCURRENTLY build.
            with engine.connect() as conn:
                check = text(
                    "SELECT 1 FROM pg_indexes "
                    "WHERE schemaname = 'public' "
                    "AND tablename = :t AND indexname = :n"
                )
                if conn.execute(check, {"t": table, "n": index_name}).fetchone():
                    return
                # Switch to autocommit isolation so CONCURRENTLY can run
                # outside a transaction (Postgres requirement).
                conn = conn.execution_options(isolation_level="AUTOCOMMIT")
                conn.execute(
                    text(
                        f"CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "
                        f"{index_name} ON {table}({column})"
                    )
                )
                logger.info(
                    f"  + Added unique index {index_name} on {table}.{column} "
                    f"(CONCURRENTLY)"
                )
    except Exception as e:
        logger.warning(
            f"  Could not ensure unique index {index_name} on {table}.{column}: {e}"
        )


def drop_all_tables() -> None:
    """
    Drop all tables. USE WITH CAUTION - destroys all data!
    
    Only use for development/testing.
    """
    from .schema import Base
    
    if not os.getenv('ALLOW_DROP_TABLES', 'false').lower() == 'true':
        raise RuntimeError(
            "Table dropping disabled. Set ALLOW_DROP_TABLES=true to enable."
        )
    
    logger.warning("Dropping all database tables!")
    Base.metadata.drop_all(bind=engine)
    logger.info("All tables dropped.")


def check_connection() -> bool:
    """
    Check if database connection is working.

    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def get_database_info() -> dict:
    """
    Get information about the current database configuration.
    
    Returns:
        dict: Database configuration details
    """
    return {
        'url': DATABASE_URL[:50] + '...' if len(DATABASE_URL) > 50 else DATABASE_URL,
        'is_sqlite': IS_SQLITE,
        'pool_size': engine.pool.size() if hasattr(engine.pool, 'size') else 'N/A',
        'connected': check_connection()
    }
