"""API response models for extraction endpoints."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.domain import ExtractionResult


class ExtractionResponse(BaseModel):
    """Single extraction response."""

    extraction_id: str
    document_id: str
    filename: str
    status: str
    model_used: str
    extraction_result: ExtractionResult
    created_at: datetime

    model_config = {"from_attributes": True}


class ExtractionListResponse(BaseModel):
    """Paginated extraction list response."""

    items: list[ExtractionResponse]
    total: int
    page: int
    page_size: int
