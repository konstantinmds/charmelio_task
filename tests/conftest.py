import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.migrations import run_migrations


@pytest.fixture(scope="function")
def sqlite_url():
    fd, path = tempfile.mkstemp(prefix="dbtest_", suffix=".sqlite")
    os.close(fd)
    url = f"sqlite:///{path}"
    try:
        yield url
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


@pytest.fixture(scope="function")
def sqlite_sessionmaker(sqlite_url):
    run_migrations(sqlite_url)
    engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    try:
        yield SessionLocal
    finally:
        engine.dispose()
