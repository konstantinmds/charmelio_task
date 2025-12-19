"""Tests for Temporal workflows (ExtractionWorkflow)."""

from __future__ import annotations

import re
from datetime import timedelta
from uuid import uuid4

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from worker.workflows import ExtractionWorkflow

# UUID v4 pattern for validation
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


# Mock activities for testing
@activity.defn(name="parse_pdf")
async def mock_parse_pdf(document_id: str) -> dict:
    """Mock parse_pdf activity."""
    return {
        "text": "This is a sample contract between Party A and Party B.",
        "page_count": 3,
    }


@activity.defn(name="llm_extract")
async def mock_llm_extract(document_id: str, text: str) -> dict:
    """Mock llm_extract activity."""
    return {
        "parties": {
            "party_one": "Party A",
            "party_two": "Party B",
            "additional_parties": [],
        },
        "dates": {
            "effective_date": "2024-01-01",
            "termination_date": "2025-01-01",
            "term_length": "1 year",
        },
        "clauses": {
            "governing_law": "State of Delaware",
            "termination": "30 days notice",
            "confidentiality": None,
            "indemnification": None,
            "limitation_of_liability": None,
            "dispute_resolution": None,
            "payment_terms": None,
            "intellectual_property": None,
        },
        "confidence": 0.85,
        "summary": "Sample contract agreement.",
    }


@activity.defn(name="store_results")
async def mock_store_results(
    extraction_id: str, document_id: str, extraction_data: dict
) -> None:
    """Mock store_results activity."""
    # Verify extraction_id is a valid UUID
    assert UUID_PATTERN.match(extraction_id), f"Invalid extraction_id: {extraction_id}"
    # Activity completes successfully
    pass


# Track activity calls for verification
activity_calls: list[tuple[str, tuple]] = []


@activity.defn(name="parse_pdf")
async def tracking_parse_pdf(document_id: str) -> dict:
    """Mock parse_pdf that tracks calls."""
    activity_calls.append(("parse_pdf", (document_id,)))
    return {"text": "Contract text", "page_count": 2}


@activity.defn(name="llm_extract")
async def tracking_llm_extract(document_id: str, text: str) -> dict:
    """Mock llm_extract that tracks calls."""
    activity_calls.append(("llm_extract", (document_id, text)))
    return {"confidence": 0.9, "parties": {}, "clauses": {}, "dates": {}, "summary": ""}


@activity.defn(name="store_results")
async def tracking_store_results(
    extraction_id: str, document_id: str, extraction_data: dict
) -> None:
    """Mock store_results that tracks calls."""
    activity_calls.append(("store_results", (extraction_id, document_id, extraction_data)))


class TestExtractionWorkflow:
    """Tests for ExtractionWorkflow."""

    @pytest.fixture(autouse=True)
    def reset_activity_calls(self):
        """Reset activity call tracking before each test."""
        activity_calls.clear()

    @pytest.mark.asyncio
    async def test_workflow_happy_path(self):
        """Workflow should execute all activities and return completed status."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[ExtractionWorkflow],
                activities=[mock_parse_pdf, mock_llm_extract, mock_store_results],
            ):
                result = await env.client.execute_workflow(
                    ExtractionWorkflow.run,
                    "doc-123",
                    id=f"test-workflow-{uuid4()}",
                    task_queue="test-queue",
                )

        assert result["status"] == "completed"
        assert result["document_id"] == "doc-123"
        assert UUID_PATTERN.match(result["extraction_id"])

    @pytest.mark.asyncio
    async def test_workflow_returns_valid_uuid_extraction_id(self):
        """Workflow should generate a valid UUID v4 extraction_id."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[ExtractionWorkflow],
                activities=[mock_parse_pdf, mock_llm_extract, mock_store_results],
            ):
                result = await env.client.execute_workflow(
                    ExtractionWorkflow.run,
                    "doc-456",
                    id=f"test-workflow-{uuid4()}",
                    task_queue="test-queue",
                )

        # Verify extraction_id is a valid UUID v4
        extraction_id = result["extraction_id"]
        assert UUID_PATTERN.match(extraction_id), f"Not a valid UUID v4: {extraction_id}"

    @pytest.mark.asyncio
    async def test_workflow_activity_call_sequence(self):
        """Workflow should call activities in correct order with correct arguments."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[ExtractionWorkflow],
                activities=[tracking_parse_pdf, tracking_llm_extract, tracking_store_results],
            ):
                result = await env.client.execute_workflow(
                    ExtractionWorkflow.run,
                    "doc-789",
                    id=f"test-workflow-{uuid4()}",
                    task_queue="test-queue",
                )

        # Verify call sequence
        assert len(activity_calls) == 3

        # First call: parse_pdf(document_id)
        assert activity_calls[0][0] == "parse_pdf"
        assert activity_calls[0][1] == ("doc-789",)

        # Second call: llm_extract(document_id, text)
        assert activity_calls[1][0] == "llm_extract"
        assert activity_calls[1][1][0] == "doc-789"
        assert activity_calls[1][1][1] == "Contract text"

        # Third call: store_results(extraction_id, document_id, extraction_data)
        assert activity_calls[2][0] == "store_results"
        assert UUID_PATTERN.match(activity_calls[2][1][0])  # extraction_id
        assert activity_calls[2][1][1] == "doc-789"  # document_id
        assert isinstance(activity_calls[2][1][2], dict)  # extraction_data

    @pytest.mark.asyncio
    async def test_workflow_passes_extraction_id_to_store_results(self):
        """Workflow should pass the same extraction_id it returns to store_results."""
        captured_extraction_id = None

        @activity.defn(name="store_results")
        async def capture_store_results(
            extraction_id: str, document_id: str, extraction_data: dict
        ) -> None:
            nonlocal captured_extraction_id
            captured_extraction_id = extraction_id

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[ExtractionWorkflow],
                activities=[mock_parse_pdf, mock_llm_extract, capture_store_results],
            ):
                result = await env.client.execute_workflow(
                    ExtractionWorkflow.run,
                    "doc-consistency",
                    id=f"test-workflow-{uuid4()}",
                    task_queue="test-queue",
                )

        # The extraction_id returned should match what was passed to store_results
        assert captured_extraction_id == result["extraction_id"]

    @pytest.mark.asyncio
    async def test_workflow_passes_parsed_text_to_llm_extract(self):
        """Workflow should pass the parsed text from parse_pdf to llm_extract."""
        captured_text = None

        @activity.defn(name="parse_pdf")
        async def custom_parse_pdf(document_id: str) -> dict:
            return {"text": "Unique contract text for testing", "page_count": 5}

        @activity.defn(name="llm_extract")
        async def capture_llm_extract(document_id: str, text: str) -> dict:
            nonlocal captured_text
            captured_text = text
            return {"confidence": 0.8, "parties": {}, "clauses": {}, "dates": {}, "summary": ""}

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[ExtractionWorkflow],
                activities=[custom_parse_pdf, capture_llm_extract, mock_store_results],
            ):
                await env.client.execute_workflow(
                    ExtractionWorkflow.run,
                    "doc-text-pass",
                    id=f"test-workflow-{uuid4()}",
                    task_queue="test-queue",
                )

        assert captured_text == "Unique contract text for testing"

    @pytest.mark.asyncio
    async def test_workflow_passes_extraction_data_to_store_results(self):
        """Workflow should pass LLM extraction results to store_results."""
        captured_data = None

        @activity.defn(name="llm_extract")
        async def custom_llm_extract(document_id: str, text: str) -> dict:
            return {
                "confidence": 0.95,
                "custom_field": "test_value",
                "parties": {},
                "clauses": {},
                "dates": {},
                "summary": "Test summary",
            }

        @activity.defn(name="store_results")
        async def capture_store_results(
            extraction_id: str, document_id: str, extraction_data: dict
        ) -> None:
            nonlocal captured_data
            captured_data = extraction_data

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[ExtractionWorkflow],
                activities=[mock_parse_pdf, custom_llm_extract, capture_store_results],
            ):
                await env.client.execute_workflow(
                    ExtractionWorkflow.run,
                    "doc-data-pass",
                    id=f"test-workflow-{uuid4()}",
                    task_queue="test-queue",
                )

        assert captured_data["confidence"] == 0.95
        assert captured_data["custom_field"] == "test_value"
        assert captured_data["summary"] == "Test summary"


class TestWorkflowDefinition:
    """Tests for workflow definition and decorators."""

    def test_workflow_has_defn_decorator(self):
        """ExtractionWorkflow should be decorated with @workflow.defn."""
        assert hasattr(ExtractionWorkflow, "__temporal_workflow_definition")

    def test_workflow_run_method_exists(self):
        """ExtractionWorkflow should have a run method."""
        assert hasattr(ExtractionWorkflow, "run")
        assert callable(ExtractionWorkflow.run)
