import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base


@pytest.fixture(scope="function")
def sqlite_sessionmaker():
    fd, path = tempfile.mkstemp(prefix="dbtest_", suffix=".sqlite")
    os.close(fd)
    url = f"sqlite:///{path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    try:
        yield SessionLocal
    finally:
        SessionLocal.close_all()
        Base.metadata.drop_all(engine)
        engine.dispose()
        try:
            os.remove(path)
        except OSError:
            pass
