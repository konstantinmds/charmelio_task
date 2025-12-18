"""Repository helpers for documents and extractions (Postgres-focused)."""

from __future__ import annotations

from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models import Document, DocumentStatus, Extraction


def create_document(
    db: Session,
    *,
    filename: str,
    content_type: str,
    file_size: int,
    bucket: str = "uploads",
    object_key: str,
    status: DocumentStatus = DocumentStatus.pending,
    raw_text: Optional[str] = None,
    page_count: Optional[int] = None,
) -> Document:
    doc = Document(
        id=str(uuid4()),
        filename=filename,
        content_type=content_type,
        file_size=file_size,
        bucket=bucket,
        object_key=object_key,
        status=status,
        raw_text=raw_text,
        page_count=page_count,
    )
    db.add(doc)
    db.flush()
    db.refresh(doc)
    return doc


def add_extraction(
    db: Session,
    *,
    document_id: str,
    model_used: str,
    clauses: dict,
    confidence: Optional[float] = None,
    artifact_bucket: str = "extractions",
    artifact_key: Optional[str] = None,
) -> Extraction:
    ext = Extraction(
        id=str(uuid4()),
        document_id=document_id,
        model_used=model_used,
        clauses=clauses,
        confidence=confidence,
        artifact_bucket=artifact_bucket,
        artifact_key=artifact_key or f"{document_id}.json",
    )
    db.add(ext)
    db.flush()
    db.refresh(ext)
    return ext


def latest_extraction(db: Session, document_id: str) -> Optional[Extraction]:
    return (
        db.query(Extraction)
        .filter(Extraction.document_id == document_id)
        .order_by(Extraction.created_at.desc())
        .first()
    )


def delete_document(db: Session, document_id: str) -> None:
    db.query(Extraction).filter(Extraction.document_id == document_id).delete()
    db.query(Document).filter(Document.id == document_id).delete()
