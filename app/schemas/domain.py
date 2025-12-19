"""Domain models for contract clause extraction."""

from typing import Optional

from pydantic import BaseModel, Field


class PartiesInfo(BaseModel):
    """Information about contract parties."""

    party_one: Optional[str] = None
    party_two: Optional[str] = None
    additional_parties: list[str] = Field(default_factory=list)


class DatesInfo(BaseModel):
    """Contract date information."""

    effective_date: Optional[str] = None  # ISO format YYYY-MM-DD
    termination_date: Optional[str] = None
    term_length: Optional[str] = None


class ClausesInfo(BaseModel):
    """Extracted contract clauses."""

    governing_law: Optional[str] = None
    termination: Optional[str] = None
    confidentiality: Optional[str] = None
    indemnification: Optional[str] = None
    limitation_of_liability: Optional[str] = None
    dispute_resolution: Optional[str] = None
    payment_terms: Optional[str] = None
    intellectual_property: Optional[str] = None


class ExtractionResult(BaseModel):
    """Complete extraction result from contract analysis."""

    parties: PartiesInfo
    dates: DatesInfo
    clauses: ClausesInfo
    confidence: float = Field(ge=0.0, le=1.0)
    summary: Optional[str] = None
