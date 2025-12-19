"""Tests for extractions read API endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import Document, DocumentStatus, Extraction
from app.db.session import get_db
from app.main import app


def make_mock_document(doc_id: str, filename: str = "test.pdf", status: DocumentStatus = DocumentStatus.completed):
    """Create a mock Document object."""
    doc = MagicMock(spec=Document)
    doc.id = doc_id
    doc.filename = filename
    doc.content_type = "application/pdf"
    doc.file_size = 1024
    doc.status = status
    doc.bucket = "uploads"
    doc.object_key = f"{doc_id}.pdf"
    return doc


def make_mock_extraction(ext_id: str, doc_id: str, model: str = "gpt-4o-mini", confidence: float = 0.85):
    """Create a mock Extraction object."""
    ext = MagicMock(spec=Extraction)
    ext.id = ext_id
    ext.document_id = doc_id
    ext.model_used = model
    ext.clauses = {
        "parties": {"party_one": "Acme Corp", "party_two": "Widget Inc", "additional_parties": []},
        "dates": {"effective_date": "2024-01-01", "termination_date": "2025-01-01", "term_length": "1 year"},
        "clauses": {"governing_law": "Delaware"},
        "confidence": confidence,
        "summary": "Test contract summary",
    }
    ext.confidence = confidence
    ext.created_at = datetime.utcnow()
    return ext


class TestGetLatestExtraction:
    """Tests for GET /api/extractions/{document_id}."""

    def test_get_latest_extraction_happy_path(self):
        """Returns the latest extraction for a document."""
        doc_id = str(uuid4())
        ext_id = str(uuid4())

        mock_doc = make_mock_document(doc_id)
        mock_ext = make_mock_extraction(ext_id, doc_id)

        mock_db = MagicMock()
        mock_result_doc = MagicMock()
        mock_result_doc.scalar_one_or_none.return_value = mock_doc

        mock_result_ext = MagicMock()
        mock_result_ext.scalar_one_or_none.return_value = mock_ext

        mock_db.execute = AsyncMock(side_effect=[mock_result_doc, mock_result_ext])

        async def mock_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = mock_get_db

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get(f"/api/extractions/{doc_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["document_id"] == doc_id
            assert data["extraction_id"] == ext_id
            assert data["filename"] == "test.pdf"
            assert data["status"] == "completed"
            assert data["model_used"] == "gpt-4o-mini"
            assert data["extraction_result"]["confidence"] == 0.85
            assert data["extraction_result"]["parties"]["party_one"] == "Acme Corp"
        finally:
            app.dependency_overrides.clear()

    def test_get_extraction_document_not_found(self):
        """Returns 404 when document doesn't exist."""
        nonexistent_id = str(uuid4())

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = mock_get_db

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get(f"/api/extractions/{nonexistent_id}")

            assert response.status_code == 404
            assert "Document not found" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_get_extraction_no_extraction_for_document(self):
        """Returns 404 when document exists but has no extractions."""
        doc_id = str(uuid4())
        mock_doc = make_mock_document(doc_id, status=DocumentStatus.pending)

        mock_db = MagicMock()
        mock_result_doc = MagicMock()
        mock_result_doc.scalar_one_or_none.return_value = mock_doc

        mock_result_ext = MagicMock()
        mock_result_ext.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(side_effect=[mock_result_doc, mock_result_ext])

        async def mock_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = mock_get_db

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get(f"/api/extractions/{doc_id}")

            assert response.status_code == 404
            assert "No extraction found" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()


class TestListExtractions:
    """Tests for GET /api/extractions."""

    def test_list_extractions_empty(self):
        """Returns empty list when no extractions exist."""
        mock_db = MagicMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_db.execute = AsyncMock(return_value=mock_count_result)

        async def mock_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = mock_get_db

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/api/extractions")

            assert response.status_code == 200
            data = response.json()
            assert data["items"] == []
            assert data["total"] == 0
            assert data["page"] == 1
            assert data["page_size"] == 10
        finally:
            app.dependency_overrides.clear()

    def test_list_extractions_with_items(self):
        """Returns paginated results with items."""
        doc1_id = str(uuid4())
        doc2_id = str(uuid4())
        ext1_id = str(uuid4())
        ext2_id = str(uuid4())

        mock_doc1 = make_mock_document(doc1_id, "doc1.pdf")
        mock_doc2 = make_mock_document(doc2_id, "doc2.pdf")
        mock_ext1 = make_mock_extraction(ext1_id, doc1_id)
        mock_ext2 = make_mock_extraction(ext2_id, doc2_id)

        mock_db = MagicMock()

        # First call: count
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        # Second call: fetch rows
        mock_rows_result = MagicMock()
        mock_rows_result.all.return_value = [
            (mock_ext1, mock_doc1),
            (mock_ext2, mock_doc2),
        ]

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_rows_result])

        async def mock_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = mock_get_db

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/api/extractions?page=1&page_size=10")

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 2
            assert data["total"] == 2
            assert data["page"] == 1
            assert data["page_size"] == 10
            assert data["items"][0]["document_id"] == doc1_id
            assert data["items"][1]["document_id"] == doc2_id
        finally:
            app.dependency_overrides.clear()

    def test_list_extractions_page_beyond_total(self):
        """Returns empty items when page exceeds total pages."""
        mock_db = MagicMock()

        # Count returns 2, but page 10 requested
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        mock_rows_result = MagicMock()
        mock_rows_result.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_rows_result])

        async def mock_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = mock_get_db

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/api/extractions?page=10&page_size=10")

            assert response.status_code == 200
            data = response.json()
            assert data["items"] == []
            assert data["total"] == 2
            assert data["page"] == 10
            assert data["page_size"] == 10
        finally:
            app.dependency_overrides.clear()

    def test_list_extractions_default_pagination(self):
        """Uses default pagination values (page=1, page_size=10)."""
        mock_db = MagicMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_db.execute = AsyncMock(return_value=mock_count_result)

        async def mock_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = mock_get_db

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/api/extractions")

            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 1
            assert data["page_size"] == 10
        finally:
            app.dependency_overrides.clear()

    def test_list_extractions_max_page_size_enforced(self):
        """Enforces maximum page_size of 100."""
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/extractions?page_size=500")

        # Should return 422 validation error
        assert response.status_code == 422

    def test_list_extractions_custom_pagination(self):
        """Accepts custom page and page_size parameters."""
        mock_db = MagicMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 50

        mock_rows_result = MagicMock()
        mock_rows_result.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_rows_result])

        async def mock_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = mock_get_db

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/api/extractions?page=3&page_size=5")

            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 3
            assert data["page_size"] == 5
            assert data["total"] == 50
        finally:
            app.dependency_overrides.clear()
