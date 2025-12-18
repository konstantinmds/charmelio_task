"""Temporal Activities.

This module will contain the activities executed by the worker:
- parse_pdf: Extract text from PDF using pdfplumber
- llm_extract: Extract clauses using OpenAI API
- store_results: Save results to MinIO and database

To be implemented in T-07: Temporal Activities
"""

# Placeholder - will be implemented in T-07
# from temporalio import activity
#
# @activity.defn
# async def parse_pdf(document_id: str) -> dict:
#     """Parse PDF and extract text."""
#     pass
#
# @activity.defn
# async def llm_extract(document_id: str, text: str) -> dict:
#     """Extract clauses using OpenAI."""
#     pass
#
# @activity.defn
# async def store_results(document_id: str, data: dict) -> None:
#     """Store extraction results."""
#     pass
