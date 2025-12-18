"""Tests for repository helpers using SQLite in-memory (unit-level)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Document, DocumentStatus, Extraction
from app.db.repository import add_extraction, create_document, delete_document, latest_extraction


@pytest.fixture(scope="function")
def db_session(sqlite_sessionmaker):
    session = sqlite_sessionmaker()
    try:
        yield session
    finally:
        session.close()


def test_create_and_latest_extraction(db_session):
    doc = create_document(
        db_session,
        filename="a.pdf",
        content_type="application/pdf",
        file_size=10,
        object_key="uploads/a.pdf",
    )
    add_extraction(
        db_session,
        document_id=doc.id,
        model_used="gpt-4o-mini",
        clauses={"clauses": {"governing_law": "CA"}},
    )
    add_extraction(
        db_session,
        document_id=doc.id,
        model_used="gpt-4o-mini",
        clauses={"clauses": {"governing_law": "NY"}},
        artifact_key="extractions/a2.json",
    )
    db_session.commit()

    latest = latest_extraction(db_session, doc.id)
    assert latest is not None
    assert latest.clauses["clauses"]["governing_law"] == "NY"


def test_cascade_delete_document(db_session):
    doc = create_document(
        db_session,
        filename="b.pdf",
        content_type="application/pdf",
        file_size=20,
        object_key="uploads/b.pdf",
    )
    add_extraction(
        db_session,
        document_id=doc.id,
        model_used="gpt-4o-mini",
        clauses={"k": "v"},
        artifact_key="extractions/b.json",
    )
    db_session.commit()

    delete_document(db_session, doc.id)
    db_session.commit()

    assert db_session.query(Document).filter_by(id=doc.id).first() is None
    assert db_session.query(Extraction).filter_by(document_id=doc.id).count() == 0


def test_required_fields_enforced(db_session):
    with pytest.raises(Exception):
        create_document(
            db_session,
            filename="no_size.pdf",
            content_type="application/pdf",
            file_size=None,  # type: ignore[arg-type]
            object_key="uploads/no.pdf",
        )


def test_status_enum_and_confidence(db_session):
    doc = create_document(
        db_session,
        filename="c.pdf",
        content_type="application/pdf",
        file_size=30,
        object_key="uploads/c.pdf",
        status=DocumentStatus.processing,
    )
    ext = add_extraction(
        db_session,
        document_id=doc.id,
        model_used="gpt-4o-mini",
        clauses={"clauses": {"termination": "Either party may terminate..."}},
        confidence=0.9,
        artifact_key="extractions/c.json",
    )
    db_session.commit()
    db_session.refresh(doc)
    db_session.refresh(ext)

    assert doc.status == DocumentStatus.processing
    assert isinstance(ext.confidence, float)
