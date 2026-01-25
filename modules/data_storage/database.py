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
            
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


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
