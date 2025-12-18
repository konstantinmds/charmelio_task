"""Tests for database layer and models (SQLite file for unit scope)."""

import os
import tempfile
from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.db.models import Document, DocumentStatus, Extraction


@pytest.fixture(scope="function")
def test_db(sqlite_sessionmaker):
    """Session factory backed by SQLite file with migrations applied."""
    return sqlite_sessionmaker


def test_create_document(test_db):
    """Test creating a document."""
    session = test_db()
    try:
        doc = Document(
            filename="contract.pdf",
            content_type="application/pdf",
            file_size=12345,
            bucket="uploads",
            object_key="uploads/contract.pdf",
            status=DocumentStatus.pending,
        )
        session.add(doc)
        session.commit()

        # Verify document was created
        assert doc.id is not None
        assert isinstance(doc.id, UUID) or isinstance(doc.id, str)
        assert doc.filename == "contract.pdf"
        assert doc.object_key == "uploads/contract.pdf"
        assert doc.file_size == 12345
        assert doc.content_type == "application/pdf"
        assert doc.status == DocumentStatus.pending
        assert doc.created_at is not None
        assert doc.updated_at is not None
    finally:
        session.close()


def test_read_document(test_db):
    """Test reading a document."""
    session = test_db()
    try:
        # Create document
        doc = Document(
            filename="test.pdf",
            content_type="application/pdf",
            file_size=1000,
            bucket="uploads",
            object_key="uploads/test.pdf",
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id

        # Read document
        retrieved_doc = session.query(Document).filter_by(id=doc_id).first()
        assert retrieved_doc is not None
        assert retrieved_doc.filename == "test.pdf"
        assert retrieved_doc.object_key == "uploads/test.pdf"
    finally:
        session.close()


def test_update_document(test_db):
    """Test updating a document."""
    session = test_db()
    try:
        # Create document
        doc = Document(
            filename="original.pdf",
            content_type="application/pdf",
            file_size=2000,
            bucket="uploads",
            object_key="uploads/original.pdf",
            status=DocumentStatus.pending,
        )
        session.add(doc)
        session.commit()

        # Update document
        doc.status = DocumentStatus.processing
        doc.raw_text = "hello"
        doc.page_count = 5
        session.commit()

        # Verify update
        session.refresh(doc)
        assert doc.status == DocumentStatus.processing
        assert doc.raw_text == "hello"
        assert doc.page_count == 5
    finally:
        session.close()


def test_delete_document(test_db):
    """Test deleting a document."""
    session = test_db()
    try:
        # Create document
        doc = Document(
            filename="delete.pdf",
            content_type="application/pdf",
            file_size=3000,
            bucket="uploads",
            object_key="uploads/delete.pdf",
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id

        # Delete document
        session.delete(doc)
        session.commit()

        # Verify deletion
        deleted_doc = session.query(Document).filter_by(id=doc_id).first()
        assert deleted_doc is None
    finally:
        session.close()


def test_create_extraction(test_db):
    """Test creating an extraction."""
    session = test_db()
    try:
        # Create parent document
        doc = Document(
            filename="contract.pdf",
            content_type="application/pdf",
            file_size=5000,
            bucket="uploads",
            object_key="uploads/contract.pdf",
        )
        session.add(doc)
        session.commit()

        # Create extraction
        extraction = Extraction(
            document_id=doc.id,
            model_used="gpt-4o-mini",
            clauses={"clauses": {"termination": "This agreement may be terminated with 30 days notice."}},
            confidence=0.95,
            artifact_key="extractions/contract.json",
        )
        session.add(extraction)
        session.commit()

        # Verify extraction
        assert extraction.id is not None
        assert extraction.document_id == doc.id
        assert extraction.clauses["clauses"]["termination"] == "This agreement may be terminated with 30 days notice."
        assert extraction.confidence == 0.95
        assert extraction.created_at is not None
    finally:
        session.close()


def test_document_extraction_relationship(test_db):
    """Test relationship between documents and extractions."""
    session = test_db()
    try:
        # Create document
        doc = Document(
            filename="contract.pdf",
            content_type="application/pdf",
            file_size=10000,
            bucket="uploads",
            object_key="uploads/contract.pdf",
        )
        session.add(doc)
        session.commit()

        # Create multiple extractions
        ext1 = Extraction(
            document_id=doc.id,
            model_used="gpt-4o-mini",
            clauses={"clauses": {"payment": "Payment due within 30 days."}},
            artifact_key="extractions/ext1.json",
        )
        ext2 = Extraction(
            document_id=doc.id,
            model_used="gpt-4o-mini",
            clauses={"clauses": {"termination": "Termination clause text."}},
            artifact_key="extractions/ext2.json",
        )
        session.add_all([ext1, ext2])
        session.commit()

        # Verify relationship
        session.refresh(doc)
        assert len(doc.extractions) == 2
        assert ext1.document.id == doc.id
        assert ext2.document.id == doc.id
    finally:
        session.close()


def test_cascade_delete(test_db):
    """Test that deleting a document cascades to extractions."""
    session = test_db()
    try:
        # Create document with extractions
        doc = Document(
            filename="cascade.pdf",
            content_type="application/pdf",
            file_size=7000,
            bucket="uploads",
            object_key="uploads/cascade.pdf",
        )
        session.add(doc)
        session.commit()

        ext = Extraction(
            document_id=doc.id,
            model_used="gpt-4o-mini",
            clauses={"clauses": {"warranty": "Warranty clause."}},
            artifact_key="extractions/cascade.json",
        )
        session.add(ext)
        session.commit()
        ext_id = ext.id

        # Delete document
        session.delete(doc)
        session.commit()

        # Verify extraction was also deleted
        deleted_ext = session.query(Extraction).filter_by(id=ext_id).first()
        assert deleted_ext is None
    finally:
        session.close()


def test_get_db_context_manager_success(test_db):
    """Test get_db context manager with successful transaction."""
    # Temporarily override SessionLocal for testing
    from app.db import session
    original_session_local = session.SessionLocal
    session.SessionLocal = test_db

    try:
        with get_db() as db:
            doc = Document(
                filename="context.pdf",
                content_type="application/pdf",
                file_size=8000,
                bucket="uploads",
                object_key="uploads/context.pdf",
            )
            db.add(doc)
        # Transaction should be committed

        # Verify document was committed
        session = test_db()
        try:
            retrieved = session.query(Document).filter_by(filename="context.pdf").first()
            assert retrieved is not None
        finally:
            session.close()
    finally:
        session.SessionLocal = original_session_local


def test_get_db_context_manager_rollback(test_db):
    """Test get_db context manager rolls back on exception."""
    from app.db import session
    original_session_local = session.SessionLocal
    session.SessionLocal = test_db

    try:
        with pytest.raises(ValueError):
            with get_db() as db:
                doc = Document(
                    filename="rollback.pdf",
                    content_type="application/pdf",
                    file_size=9000,
                    bucket="uploads",
                    object_key="uploads/rollback.pdf",
                )
                db.add(doc)
                # Raise exception before commit
                raise ValueError("Test rollback")

        # Verify document was NOT committed
        session = test_db()
        try:
            retrieved = session.query(Document).filter_by(filename="rollback.pdf").first()
            assert retrieved is None
        finally:
            session.close()
    finally:
        session.SessionLocal = original_session_local


def test_extraction_metadata_jsonb(test_db):
    """Test JSONB metadata field on Extraction."""
    session = test_db()
    try:
        doc = Document(
            filename="metadata.pdf",
            content_type="application/pdf",
            file_size=4000,
            bucket="uploads",
            object_key="uploads/metadata.pdf",
        )
        session.add(doc)
        session.commit()

        # Create extraction with complex metadata
        metadata = {
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "tokens_used": 1500,
            "context": {"section": "5.3", "subsection": "a"},
            "extracted_at": datetime.utcnow().isoformat(),
        }
        extraction = Extraction(
            document_id=doc.id,
            model_used="gpt-4o-mini",
            clauses={"metadata": metadata, "clause_text": "Liability clause."},
            artifact_key="extractions/meta.json",
        )
        session.add(extraction)
        session.commit()

        # Verify metadata
        session.refresh(extraction)
        assert extraction.clauses["metadata"]["model"] == "gpt-4o-mini"
        assert extraction.clauses["metadata"]["temperature"] == 0.7
        assert extraction.clauses["metadata"]["tokens_used"] == 1500
        assert extraction.clauses["metadata"]["context"]["section"] == "5.3"
    finally:
        session.close()
