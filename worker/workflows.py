"""Temporal Workflows for contract extraction.

This module contains the ExtractionWorkflow that orchestrates
the PDF clause extraction process through three activities:
parse_pdf -> llm_extract -> store_results
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from worker.activities import llm_extract, parse_pdf, store_results


@workflow.defn
class ExtractionWorkflow:
    """Workflow that orchestrates contract clause extraction.

    This workflow:
    1. Parses a PDF document to extract text
    2. Runs LLM extraction to identify contract clauses
    3. Stores results to MinIO and database

    The workflow generates a stable extraction_id at start for idempotency,
    ensuring retries don't create duplicate extractions.
    """

    @workflow.run
    async def run(self, document_id: str) -> dict:
        """Execute the extraction workflow.

        Args:
            document_id: UUID of the document to process.

        Returns:
            Dict with status, document_id, and extraction_id.
        """
        # Generate stable extraction_id for idempotency
        # Use workflow.uuid4() for deterministic UUID generation (safe for replay)
        extraction_id = str(workflow.uuid4())

        workflow.logger.info(
            f"Starting extraction workflow for document {document_id}, "
            f"extraction_id={extraction_id}"
        )

        # Step 1: Parse PDF
        # Non-retryable on PDFParseError/PDFValidationError (document is invalid)
        # Light retries for transient storage errors
        parsed = await workflow.execute_activity(
            parse_pdf,
            document_id,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=2,
                non_retryable_error_types=["PDFParseError", "PDFValidationError"],
            ),
        )

        workflow.logger.info(
            f"PDF parsed: {parsed['page_count']} pages, "
            f"{len(parsed['text'])} chars"
        )

        # Step 2: LLM extraction
        # Exponential backoff for rate limits and provider hiccups
        extracted = await workflow.execute_activity(
            llm_extract,
            args=[document_id, parsed["text"]],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=2),
                backoff_coefficient=2.0,
                maximum_interval=timedelta(seconds=30),
            ),
        )

        workflow.logger.info(
            f"LLM extraction complete, confidence={extracted.get('confidence', 'N/A')}"
        )

        # Step 3: Store results
        # Idempotent - safe to retry on transient DB/storage errors
        await workflow.execute_activity(
            store_results,
            args=[extraction_id, document_id, extracted],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        workflow.logger.info(
            f"Extraction workflow completed for document {document_id}"
        )

        return {
            "status": "completed",
            "document_id": document_id,
            "extraction_id": extraction_id,
        }


__all__ = ["ExtractionWorkflow"]
