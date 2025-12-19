"""Extractions read API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, Extraction
from app.db.session import get_db
from app.schemas.api import ExtractionListResponse, ExtractionResponse
from app.schemas.domain import ExtractionResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/extractions", tags=["extractions"])


def _build_extraction_response(doc: Document, ext: Extraction) -> ExtractionResponse:
    """Map Document + Extraction to API response model."""
    try:
        extraction_result = ExtractionResult.model_validate(ext.clauses)
    except Exception as e:
        logger.error(f"Invalid extraction data for {ext.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Stored extraction data corrupted for extraction {ext.id}",
        )

    return ExtractionResponse(
        extraction_id=ext.id,
        document_id=doc.id,
        filename=doc.filename,
        status=doc.status.value,
        model_used=ext.model_used,
        extraction_result=extraction_result,
        created_at=ext.created_at,
    )


@router.get("/{document_id}", response_model=ExtractionResponse)
async def get_latest_extraction(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the latest extraction for a document."""
    # Fetch document
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Fetch latest extraction
    result = await db.execute(
        select(Extraction)
        .where(Extraction.document_id == document_id)
        .order_by(Extraction.created_at.desc())
        .limit(1)
    )
    ext = result.scalar_one_or_none()

    if not ext:
        raise HTTPException(status_code=404, detail="No extraction found for document")

    return _build_extraction_response(doc, ext)


@router.get("", response_model=ExtractionListResponse)
async def list_extractions(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all extractions with pagination, newest first."""
    # Count total
    count_result = await db.execute(select(func.count(Extraction.id)))
    total = count_result.scalar() or 0

    if total == 0:
        return ExtractionListResponse(items=[], total=0, page=page, page_size=page_size)

    # Fetch page with join
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Extraction, Document)
        .join(Document, Extraction.document_id == Document.id)
        .order_by(Extraction.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = result.all()

    items = [_build_extraction_response(doc, ext) for ext, doc in rows]

    return ExtractionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
