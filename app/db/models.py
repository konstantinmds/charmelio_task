from __future__ import annotations

"""SQLAlchemy models for documents and extractions (typed, portable)."""

import enum
from datetime import datetime
from uuid import uuid4
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

class DocumentStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., application/pdf
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus), nullable=False, default=DocumentStatus.pending
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    bucket: Mapped[str] = mapped_column(String(63), nullable=False, default="uploads")
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)  # e.g., "uploads/<uuid>.pdf"

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    extractions: Mapped[list["Extraction"]] = relationship(
        "Extraction",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="Extraction.created_at",
    )


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    model_used: Mapped[str] = mapped_column(String(80), nullable=False)  # e.g., "gpt-4o-mini"
    clauses: Mapped[dict] = mapped_column(JSON, nullable=False)  # full ExtractionResult JSON
    confidence: Mapped[Optional[float]] = mapped_column(Float)

    artifact_bucket: Mapped[str] = mapped_column(String(63), nullable=False, default="extractions")
    artifact_key: Mapped[str] = mapped_column(String(512), nullable=False)  # e.g., "extractions/<uuid>.json"

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    document: Mapped["Document"] = relationship("Document", back_populates="extractions")

    __table_args__ = (
        Index("idx_extractions_document_created", "document_id", "created_at"),
    )
