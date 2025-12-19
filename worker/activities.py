"""Temporal Activities for contract extraction workflow.

This module contains the activities executed by the worker:
- parse_pdf: Extract text from PDF using pdfplumber
- llm_extract: Extract clauses using OpenAI API
- store_results: Save results to MinIO and database
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.exc import IntegrityError
from temporalio import activity

from app.core.config import settings
from app.db.models import Document, DocumentStatus, Extraction
from app.db.session import get_sync_db
from app.deps import get_storage
from app.services import PDFParseError, extract_text_and_pages
from worker.llm_extractor import extract_clauses

logger = logging.getLogger(__name__)


@activity.defn
def parse_pdf(document_id: str) -> dict[str, Any]:
    """Parse PDF and extract text from MinIO storage.

    Reads the PDF from MinIO, extracts text using pdfplumber, updates
    the document status to processing, and returns the extracted text.

    Args:
        document_id: UUID of the document to parse.

    Returns:
        Dict with 'text' (str) and 'page_count' (int).

    Raises:
        PDFParseError: If PDF parsing fails (document marked as failed).
        StorageError: If MinIO read fails.
    """
    storage = get_storage()

    # Read PDF bytes from MinIO
    pdf_bytes, _ = storage.get_bytes(settings.S3_BUCKET_UPLOADS, f"{document_id}.pdf")

    with get_sync_db() as db:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc is None:
            raise ValueError(f"Document {document_id} not found")

        try:
            result = extract_text_and_pages(pdf_bytes)

            # Update document with parsed data
            doc.raw_text = result.text
            doc.page_count = result.page_count
            doc.status = DocumentStatus.processing
            doc.error_message = None

            logger.info(
                "Parsed PDF for document %s: %d pages, %d chars",
                document_id,
                result.page_count,
                len(result.text),
            )

            return {"text": result.text, "page_count": result.page_count}

        except PDFParseError as e:
            # Mark document as failed on parse error
            doc.status = DocumentStatus.failed
            doc.error_message = str(e)
            db.commit()  # Commit the failed status before re-raising
            logger.warning("PDF parse failed for document %s: %s", document_id, e)
            raise


@activity.defn
def llm_extract(document_id: str, text: str) -> dict[str, Any]:
    """Extract contract clauses using OpenAI LLM.

    Calls the OpenAI API to extract structured clause information
    from the provided text. Does not modify the database.

    Args:
        document_id: UUID of the document (for logging/context).
        text: Plain text extracted from the PDF.

    Returns:
        Dict representation of ExtractionResult (via model_dump()).

    Raises:
        LLMExtractError: If LLM extraction fails (let workflow handle retry).
    """
    logger.info("Running LLM extraction for document %s (%d chars)", document_id, len(text))

    # Call LLM adapter - let LLMExtractError propagate for workflow retry
    result = extract_clauses(text)

    logger.info(
        "LLM extraction complete for document %s: confidence=%.2f",
        document_id,
        result.confidence,
    )

    return result.model_dump()


@activity.defn
def store_results(
    extraction_id: str,
    document_id: str,
    extraction_data: dict[str, Any],
) -> None:
    """Store extraction results to MinIO and database.

    Writes the extraction JSON to MinIO and inserts an Extraction record.
    Uses stable extraction_id for idempotency - IntegrityError on duplicate
    insert is treated as success (retry safety).

    Args:
        extraction_id: Stable UUID for the extraction (from workflow).
        document_id: UUID of the source document.
        extraction_data: Dict from llm_extract (ExtractionResult.model_dump()).

    Raises:
        StorageError: If MinIO write fails.
    """
    storage = get_storage()
    artifact_key = f"{document_id}.json"

    # Write JSON artifact to MinIO (overwrite allowed for idempotency)
    json_bytes = json.dumps(extraction_data, indent=2).encode("utf-8")
    storage.put_bytes(
        settings.S3_BUCKET_EXTRACTIONS,
        artifact_key,
        json_bytes,
        content_type="application/json",
    )

    logger.info("Stored extraction artifact: %s/%s", settings.S3_BUCKET_EXTRACTIONS, artifact_key)

    with get_sync_db() as db:
        try:
            # Insert Extraction with stable extraction_id
            extraction = Extraction(
                id=extraction_id,
                document_id=document_id,
                model_used=settings.MODEL_NAME,
                clauses=extraction_data,
                confidence=extraction_data.get("confidence"),
                artifact_bucket=settings.S3_BUCKET_EXTRACTIONS,
                artifact_key=artifact_key,
            )
            db.add(extraction)
            db.flush()  # Trigger IntegrityError if duplicate

            logger.info("Created Extraction record %s for document %s", extraction_id, document_id)

        except IntegrityError:
            # Duplicate insertion - treat as success (idempotent retry)
            db.rollback()
            logger.info(
                "Extraction %s already exists (idempotent retry), skipping insert",
                extraction_id,
            )

        # Update document status to completed
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc is not None:
            doc.status = DocumentStatus.completed
            doc.error_message = None
            logger.info("Document %s marked as completed", document_id)


__all__ = ["parse_pdf", "llm_extract", "store_results"]
