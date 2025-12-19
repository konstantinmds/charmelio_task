"""Tests for Temporal activities (parse_pdf, llm_extract, store_results)."""

from __future__ import annotations

import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.db.models import Document, DocumentStatus, Extraction
from app.services import PDFParseError, ParseResult
from app.schemas.domain import ClausesInfo, DatesInfo, ExtractionResult, PartiesInfo
from worker.activities import llm_extract, parse_pdf, store_results
from worker.llm_extractor import LLMExtractError


@pytest.fixture
def document_id():
    """Generate a unique document ID for each test."""
    return str(uuid4())


@pytest.fixture
def extraction_id():
    """Generate a unique extraction ID for each test."""
    return str(uuid4())


@pytest.fixture
def sample_document(sqlite_sessionmaker, document_id):
    """Create a sample document in the test database."""
    SessionLocal = sqlite_sessionmaker
    with SessionLocal() as session:
        doc = Document(
            id=document_id,
            filename="test.pdf",
            content_type="application/pdf",
            file_size=1024,
            bucket="uploads",
            object_key=f"{document_id}.pdf",
            status=DocumentStatus.pending,
        )
        session.add(doc)
        session.commit()
    return document_id


@pytest.fixture
def sample_extraction_result():
    """Create a sample ExtractionResult for testing."""
    return ExtractionResult(
        parties=PartiesInfo(
            party_one="Acme Corp",
            party_two="Widget Inc",
            additional_parties=[],
        ),
        dates=DatesInfo(
            effective_date="2024-01-01",
            termination_date="2025-01-01",
            term_length="1 year",
        ),
        clauses=ClausesInfo(
            governing_law="State of Delaware",
            termination="30 days notice",
            confidentiality="Standard NDA terms",
            indemnification="Mutual indemnification",
            limitation_of_liability="Cap at contract value",
            dispute_resolution="Arbitration",
            payment_terms="Net 30",
            intellectual_property="Work for hire",
        ),
        confidence=0.85,
        summary="Sample service agreement between Acme Corp and Widget Inc.",
    )


@pytest.fixture
def mock_storage():
    """Create a mock storage object."""
    storage = MagicMock()
    storage.get_bytes.return_value = (b"%PDF-1.4 fake pdf content", {})
    storage.put_bytes.return_value = "extractions/test.json"
    return storage


@pytest.fixture
def mock_parse_result():
    """Create a sample ParseResult."""
    return ParseResult(
        text="This is the extracted contract text with important clauses.",
        page_count=5,
    )


@contextmanager
def patch_db_session(sessionmaker):
    """Patch get_db to use our test session."""
    @contextmanager
    def test_get_db():
        session = sessionmaker()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    with patch("worker.activities.get_sync_db", test_get_db):
        yield


class TestParsePdfActivity:
    """Tests for the parse_pdf activity."""

    def test_parse_pdf_happy_path(
        self,
        sqlite_sessionmaker,
        sample_document,
        mock_storage,
        mock_parse_result,
    ):
        """parse_pdf should extract text, update doc status, and return result."""
        document_id = sample_document

        with (
            patch("worker.activities.get_storage", return_value=mock_storage),
            patch("worker.activities.extract_text_and_pages", return_value=mock_parse_result),
            patch_db_session(sqlite_sessionmaker),
        ):
            result = parse_pdf(document_id)

        # Verify return value
        assert result["text"] == mock_parse_result.text
        assert result["page_count"] == mock_parse_result.page_count

        # Verify storage was called correctly
        mock_storage.get_bytes.assert_called_once_with("uploads", f"{document_id}.pdf")

        # Verify document was updated
        with sqlite_sessionmaker() as session:
            doc = session.query(Document).filter(Document.id == document_id).first()
            assert doc.status == DocumentStatus.processing
            assert doc.raw_text == mock_parse_result.text
            assert doc.page_count == mock_parse_result.page_count
            assert doc.error_message is None

    def test_parse_pdf_parse_error_marks_document_failed(
        self,
        sqlite_sessionmaker,
        sample_document,
        mock_storage,
    ):
        """parse_pdf should mark doc as failed on PDFParseError and re-raise."""
        document_id = sample_document
        error_message = "failed to parse PDF: CorruptedPDF"

        with (
            patch("worker.activities.get_storage", return_value=mock_storage),
            patch(
                "worker.activities.extract_text_and_pages",
                side_effect=PDFParseError(error_message),
            ),
            patch_db_session(sqlite_sessionmaker),
        ):
            with pytest.raises(PDFParseError, match=error_message):
                parse_pdf(document_id)

        # Verify document was marked as failed
        with sqlite_sessionmaker() as session:
            doc = session.query(Document).filter(Document.id == document_id).first()
            assert doc.status == DocumentStatus.failed
            assert doc.error_message == error_message

    def test_parse_pdf_document_not_found(
        self,
        sqlite_sessionmaker,
        mock_storage,
    ):
        """parse_pdf should raise ValueError when document doesn't exist."""
        nonexistent_id = str(uuid4())

        with (
            patch("worker.activities.get_storage", return_value=mock_storage),
            patch_db_session(sqlite_sessionmaker),
        ):
            with pytest.raises(ValueError, match="not found"):
                parse_pdf(nonexistent_id)


class TestLlmExtractActivity:
    """Tests for the llm_extract activity."""

    def test_llm_extract_happy_path(self, document_id, sample_extraction_result):
        """llm_extract should return model_dump() of ExtractionResult."""
        text = "Sample contract text for extraction"

        with patch(
            "worker.activities.extract_clauses",
            return_value=sample_extraction_result,
        ) as mock_extract:
            result = llm_extract(document_id, text)

        # Verify extract_clauses was called with the text
        mock_extract.assert_called_once_with(text)

        # Verify result matches model_dump
        expected = sample_extraction_result.model_dump()
        assert result == expected
        assert result["confidence"] == 0.85
        assert result["parties"]["party_one"] == "Acme Corp"

    def test_llm_extract_propagates_error(self, document_id):
        """llm_extract should let LLMExtractError propagate for workflow retry."""
        text = "Sample contract text"
        error_message = "API error after 3 retries: rate limited"

        with patch(
            "worker.activities.extract_clauses",
            side_effect=LLMExtractError(error_message),
        ):
            with pytest.raises(LLMExtractError, match=error_message):
                llm_extract(document_id, text)


class TestStoreResultsActivity:
    """Tests for the store_results activity."""

    def test_store_results_happy_path(
        self,
        sqlite_sessionmaker,
        sample_document,
        extraction_id,
        sample_extraction_result,
        mock_storage,
    ):
        """store_results should write to MinIO, insert Extraction, and mark doc completed."""
        document_id = sample_document
        extraction_data = sample_extraction_result.model_dump()

        with (
            patch("worker.activities.get_storage", return_value=mock_storage),
            patch_db_session(sqlite_sessionmaker),
            patch("worker.activities.settings") as mock_settings,
        ):
            mock_settings.S3_BUCKET_EXTRACTIONS = "extractions"
            mock_settings.MODEL_NAME = "gpt-4o-mini"

            store_results(extraction_id, document_id, extraction_data)

        # Verify MinIO write
        mock_storage.put_bytes.assert_called_once()
        call_args = mock_storage.put_bytes.call_args
        assert call_args[0][0] == "extractions"
        assert call_args[0][1] == f"{document_id}.json"
        assert call_args[1]["content_type"] == "application/json"

        # Verify JSON content
        written_json = json.loads(call_args[0][2].decode("utf-8"))
        assert written_json["confidence"] == 0.85

        # Verify Extraction was created
        with sqlite_sessionmaker() as session:
            extraction = session.query(Extraction).filter(Extraction.id == extraction_id).first()
            assert extraction is not None
            assert extraction.document_id == document_id
            assert extraction.model_used == "gpt-4o-mini"
            assert extraction.confidence == 0.85
            assert extraction.artifact_key == f"{document_id}.json"

            # Verify document was marked completed
            doc = session.query(Document).filter(Document.id == document_id).first()
            assert doc.status == DocumentStatus.completed
            assert doc.error_message is None

    def test_store_results_idempotent_retry(
        self,
        sqlite_sessionmaker,
        sample_document,
        extraction_id,
        sample_extraction_result,
        mock_storage,
    ):
        """store_results should handle duplicate insert gracefully (idempotent)."""
        document_id = sample_document
        extraction_data = sample_extraction_result.model_dump()

        with (
            patch("worker.activities.get_storage", return_value=mock_storage),
            patch_db_session(sqlite_sessionmaker),
            patch("worker.activities.settings") as mock_settings,
        ):
            mock_settings.S3_BUCKET_EXTRACTIONS = "extractions"
            mock_settings.MODEL_NAME = "gpt-4o-mini"

            # First call - creates extraction
            store_results(extraction_id, document_id, extraction_data)

            # Second call - should not fail (idempotent)
            store_results(extraction_id, document_id, extraction_data)

        # Verify only one Extraction exists (second insert was rolled back)
        with sqlite_sessionmaker() as session:
            extractions = session.query(Extraction).filter(
                Extraction.document_id == document_id
            ).all()
            assert len(extractions) == 1
            assert extractions[0].id == extraction_id

            # Document should still be completed
            doc = session.query(Document).filter(Document.id == document_id).first()
            assert doc.status == DocumentStatus.completed

    def test_store_results_document_not_found_still_stores_extraction(
        self,
        sqlite_sessionmaker,
        extraction_id,
        sample_extraction_result,
        mock_storage,
    ):
        """store_results should store extraction even if document is missing."""
        nonexistent_doc_id = str(uuid4())
        extraction_data = sample_extraction_result.model_dump()

        # Create a document for the foreign key constraint
        with sqlite_sessionmaker() as session:
            doc = Document(
                id=nonexistent_doc_id,
                filename="test.pdf",
                content_type="application/pdf",
                file_size=1024,
                bucket="uploads",
                object_key=f"{nonexistent_doc_id}.pdf",
                status=DocumentStatus.processing,
            )
            session.add(doc)
            session.commit()

        with (
            patch("worker.activities.get_storage", return_value=mock_storage),
            patch_db_session(sqlite_sessionmaker),
            patch("worker.activities.settings") as mock_settings,
        ):
            mock_settings.S3_BUCKET_EXTRACTIONS = "extractions"
            mock_settings.MODEL_NAME = "gpt-4o-mini"

            # Should not raise - stores extraction and updates doc
            store_results(extraction_id, nonexistent_doc_id, extraction_data)

        # Verify extraction was stored
        with sqlite_sessionmaker() as session:
            extraction = session.query(Extraction).filter(Extraction.id == extraction_id).first()
            assert extraction is not None

            # Document should be completed
            doc = session.query(Document).filter(Document.id == nonexistent_doc_id).first()
            assert doc.status == DocumentStatus.completed


class TestActivityDecorators:
    """Tests to verify Temporal activity decorators are applied correctly."""

    def test_parse_pdf_is_activity(self):
        """parse_pdf should be decorated with @activity.defn."""
        # The decorator adds __temporal_activity_definition attribute
        assert hasattr(parse_pdf, "__temporal_activity_definition")

    def test_llm_extract_is_activity(self):
        """llm_extract should be decorated with @activity.defn."""
        assert hasattr(llm_extract, "__temporal_activity_definition")

    def test_store_results_is_activity(self):
        """store_results should be decorated with @activity.defn."""
        assert hasattr(store_results, "__temporal_activity_definition")
