"""Shared test fixtures."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from modules.data_storage.schema import Base
from modules.data_storage.database import get_db
from backend.main import app


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def disable_scheduler(monkeypatch):
    """Prevent APScheduler from starting during tests."""
    monkeypatch.setattr("backend.scheduler.start_scheduler", lambda: None)
    monkeypatch.setattr("backend.scheduler.stop_scheduler", lambda: None)


@pytest.fixture
def db_session(db_engine):
    """Create a DB session for testing."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def client(db_session):
    """FastAPI test client with DB override."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
