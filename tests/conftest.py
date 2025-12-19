"""Pytest configuration and fixtures."""

import os

# Set test database URL BEFORE any app imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base


@pytest.fixture(scope="function")
def sqlite_sessionmaker(tmp_path):
    """Create a SQLite database with schema for testing."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    yield SessionLocal
    engine.dispose()


@pytest.fixture
def mock_db_session():
    """Create a mock async database session."""
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.execute = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    return mock_session


@pytest.fixture
def mock_temporal():
    """Create a mock Temporal client."""
    return AsyncMock()


@pytest.fixture
def mock_storage():
    """Create a mock storage client."""
    storage = MagicMock()
    storage.put_bytes = MagicMock()
    storage.get_bytes = MagicMock(return_value=(b"test", {}))
    return storage
