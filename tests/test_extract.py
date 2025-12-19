"""Tests for POST /api/extract endpoint."""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.models import Document, DocumentStatus
from app.db.session import get_db
from app.main import app


class TestExtractEndpoint:
    """Tests for POST /api/extract."""

    def test_extract_happy_path(self):
        """Valid PDF upload returns 200 with document_id and pending status."""
        mock_db = MagicMock()
        mock_db.commit = AsyncMock()
        mock_temporal = AsyncMock()
        mock_storage = MagicMock()

        async def mock_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = mock_get_db

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                app.state.temporal = mock_temporal

                with patch("app.routes.documents.get_storage", return_value=mock_storage):
                    pdf_content = b"%PDF-1.4 fake pdf content"
                    files = {"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}

                    response = client.post("/api/extract", files=files)

                assert response.status_code == 200
                data = response.json()
                assert "document_id" in data
                assert data["filename"] == "test.pdf"
                assert data["status"] == "pending"

                mock_db.add.assert_called_once()
                mock_storage.put_bytes.assert_called_once()
                mock_temporal.start_workflow.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    def test_extract_non_pdf_returns_400(self):
        """Non-PDF content type returns 400 error."""
        with TestClient(app, raise_server_exceptions=False) as client:
            app.state.temporal = AsyncMock()

            files = {"file": ("test.txt", io.BytesIO(b"plain text"), "text/plain")}
            response = client.post("/api/extract", files=files)

            assert response.status_code == 400
            assert "Only PDF files supported" in response.json()["detail"]

    def test_extract_oversize_file_returns_413(self):
        """File exceeding size limit returns 413 error."""
        with TestClient(app, raise_server_exceptions=False) as client:
            app.state.temporal = AsyncMock()

            with patch("app.routes.documents.settings") as mock_settings:
                mock_settings.MAX_FILE_SIZE_MB = 1  # 1 MB limit

                large_content = b"X" * (2 * 1024 * 1024)  # 2 MB
                files = {"file": ("large.pdf", io.BytesIO(large_content), "application/pdf")}

                response = client.post("/api/extract", files=files)

            assert response.status_code == 413
            assert "exceeds" in response.json()["detail"]

    def test_extract_temporal_unavailable_returns_503(self):
        """Returns 503 when Temporal client is not available."""
        with TestClient(app, raise_server_exceptions=False) as client:
            app.state.temporal = None

            pdf_content = b"%PDF-1.4 fake pdf content"
            files = {"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}

            response = client.post("/api/extract", files=files)

            assert response.status_code == 503
            assert "Extraction service unavailable" in response.json()["detail"]

    def test_extract_creates_document_with_correct_fields(self):
        """Verify Document is created with correct field values."""
        mock_db = MagicMock()
        mock_db.commit = AsyncMock()
        mock_temporal = AsyncMock()
        mock_storage = MagicMock()

        captured_doc = None

        def capture_add(doc):
            nonlocal captured_doc
            captured_doc = doc

        mock_db.add.side_effect = capture_add

        async def mock_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = mock_get_db

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                app.state.temporal = mock_temporal

                with patch("app.routes.documents.get_storage", return_value=mock_storage):
                    pdf_content = b"%PDF-1.4 test content here"
                    files = {"file": ("contract.pdf", io.BytesIO(pdf_content), "application/pdf")}

                    response = client.post("/api/extract", files=files)

                assert response.status_code == 200
                assert captured_doc is not None
                assert captured_doc.filename == "contract.pdf"
                assert captured_doc.content_type == "application/pdf"
                assert captured_doc.file_size == len(pdf_content)
                assert captured_doc.status == DocumentStatus.pending
                assert captured_doc.object_key.endswith(".pdf")
        finally:
            app.dependency_overrides.clear()

    def test_extract_starts_workflow_with_correct_params(self):
        """Verify workflow is started with correct parameters."""
        mock_db = MagicMock()
        mock_db.commit = AsyncMock()
        mock_temporal = AsyncMock()
        mock_storage = MagicMock()

        async def mock_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = mock_get_db

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                app.state.temporal = mock_temporal

                with patch("app.routes.documents.get_storage", return_value=mock_storage):
                    pdf_content = b"%PDF-1.4 content"
                    files = {"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}

                    response = client.post("/api/extract", files=files)

                assert response.status_code == 200
                document_id = response.json()["document_id"]

                call_kwargs = mock_temporal.start_workflow.call_args
                assert call_kwargs.kwargs["id"] == f"extraction-{document_id}"
                assert call_kwargs.kwargs["task_queue"] == "extraction-queue"
        finally:
            app.dependency_overrides.clear()
