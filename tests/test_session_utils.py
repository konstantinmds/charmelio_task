"""Tests for session utilities (sync) using SQLite temp file."""

from __future__ import annotations

import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Document
import app.db.session as session_module
from app.db.session import get_db, get_db_dependency


@pytest.fixture(scope="function")
def configure_session(monkeypatch):
    fd, path = tempfile.mkstemp(prefix="session_", suffix=".sqlite")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    test_session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(session_module, "SessionLocal", test_session_local)
    try:
        yield
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
        try:
            os.remove(path)
        except OSError:
            pass


def test_get_db_commit_and_rollback(configure_session):
    # commit on success
    with get_db() as db:
        db.add(Document(id="1", filename="a.pdf", content_type="application/pdf", file_size=10, object_key="uploads/1.pdf"))
    with get_db() as db:
        assert db.query(Document).count() == 1

    # rollback on exception
    with pytest.raises(RuntimeError):
        with get_db() as db:
            db.add(Document(id="2", filename="b.pdf", content_type="application/pdf", file_size=10, object_key="uploads/2.pdf"))
            raise RuntimeError("boom")
    with get_db() as db:
        assert db.query(Document).filter_by(id="2").first() is None


def test_get_db_dependency_closes(configure_session):
    gen = get_db_dependency()
    db = next(gen)
    db.add(Document(id="3", filename="c.pdf", content_type="application/pdf", file_size=5, object_key="uploads/3.pdf"))
    db.commit()
    try:
        next(gen)
    except StopIteration:
        pass
    # session should be closed; opening a new one should see persisted row
    with get_db() as fresh:
        assert fresh.query(Document).filter_by(id="3").count() == 1
