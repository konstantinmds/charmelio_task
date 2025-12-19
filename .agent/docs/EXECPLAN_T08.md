# T-08 Temporal Workflow

This ExecPlan is a living document. Maintain it in accordance with `.agent/PLANS.md` from the repository root so a newcomer can complete the work using only this file.

## Purpose / Big Picture

Orchestrate the three durable activities (`parse_pdf`, `llm_extract`, `store_results`) in a Temporal workflow that generates a stable `extraction_id`, enforces idempotency, and applies sensible retry policies. After this change, starting the workflow with a `document_id` will parse the PDF, extract structured clauses, persist artifacts and DB rows, and return a completion payload without duplicating side effects on retries.

## Progress

- [ ] Draft workflow design and retry policies
- [ ] Implement `ExtractionWorkflow` in `worker/workflows.py`
- [ ] Update worker bootstrap (`worker/run.py`) to register workflow and activities
- [ ] Add unit tests with mocked activities and coverage ≥95% for workflow file
- [ ] (Optional) Add integration test marker for Temporal stack

## Surprises & Discoveries

- None yet; capture Temporal retry semantics, sandbox import constraints, or testing quirks as discovered.

## Decision Log

- Planned: Generate a single stable `extraction_id` at workflow start using `uuid4()` and reuse it for all retries to keep `store_results` idempotent.
- Planned: Workflow is `async def` but activities are synchronous (`def`); use `activity_executor="default"` which handles sync activities.
- Planned: Treat `PDFParseError` and `PDFValidationError` as non-retryable in `parse_pdf` activity policy; allow limited retries for storage/network errors.
- Planned: Allow limited retries for `llm_extract` with exponential backoff to tolerate provider rate limits and hiccups.
- Planned: `store_results` remains idempotent; retry lightly for transient DB/storage errors.
- Planned: Keep the workflow pure (deterministic, no side effects); all mutations happen inside activities only.
- Planned: Use `workflow.unsafe.imports_passed_through()` context manager to import activity references inside the workflow sandbox.
- Planned: Use `timedelta` for activity timeouts (e.g., `start_to_close_timeout=timedelta(minutes=5)`).

## Outcomes & Retrospective

Target end state:
- `worker/workflows.py` defines `ExtractionWorkflow` class with `run(document_id: str) -> dict` method.
- Workflow generates a stable `extraction_id`, passes it to `store_results`, and returns `{"status": "completed", "document_id": ..., "extraction_id": ...}`.
- Retry policies:
  - `parse_pdf`: `maximum_attempts=2`, non-retryable on `PDFParseError`, `PDFValidationError`
  - `llm_extract`: `maximum_attempts=3`, initial_interval=2s, backoff=2.0, max_interval=30s
  - `store_results`: `maximum_attempts=3` (idempotent, safe to retry)
- `worker/run.py` registers `ExtractionWorkflow` and activities `[parse_pdf, llm_extract, store_results]`.
- Unit tests cover ID generation, activity call ordering/arguments, and policy wiring with ≥95% coverage.

## Context and Orientation

Repository root: `/Users/tijanapetrovic/Documents/inner_outer_projs/charmelio_clean`

Relevant files and modules:
- `worker/workflows.py` - Currently placeholder; will host `ExtractionWorkflow`.
- `worker/activities.py` - Exposes `parse_pdf`, `llm_extract`, `store_results` (implemented in T-07). All are **synchronous** (`def`, not `async def`).
- `worker/run.py` - Worker bootstrap; currently has empty `workflows=[]` and `activities=[]`. Must register the workflow and activities.
- `worker/config.py` - `WorkerSettings` with `WORKER_TASK_QUEUE = "extraction-queue"`.
- `app/pdf_parser.py` - Defines `PDFParseError` and `PDFValidationError` exception classes.
- `worker/llm_extractor.py` - Defines `LLMExtractError` exception class.

Activity signatures (from T-07):
```python
@activity.defn
def parse_pdf(document_id: str) -> dict[str, Any]:
    """Returns {"text": str, "page_count": int}"""

@activity.defn
def llm_extract(document_id: str, text: str) -> dict[str, Any]:
    """Returns ExtractionResult.model_dump() dict"""

@activity.defn
def store_results(extraction_id: str, document_id: str, extraction_data: dict[str, Any]) -> None:
    """Stores to MinIO and DB, returns None"""
```

## Plan of Work

1. **Review existing setup**: Check `worker/run.py` and `worker/workflows.py` to understand registration pattern.

2. **Implement `ExtractionWorkflow`** in `worker/workflows.py`:
   ```python
   from datetime import timedelta
   from uuid import uuid4

   from temporalio import workflow

   with workflow.unsafe.imports_passed_through():
       from app.pdf_parser import PDFParseError, PDFValidationError
       from worker.activities import llm_extract, parse_pdf, store_results

   @workflow.defn
   class ExtractionWorkflow:
       @workflow.run
       async def run(self, document_id: str) -> dict:
           # Generate stable extraction_id for idempotency
           extraction_id = str(uuid4())

           # Step 1: Parse PDF
           parsed = await workflow.execute_activity(
               parse_pdf,
               document_id,
               start_to_close_timeout=timedelta(minutes=5),
               retry_policy=workflow.RetryPolicy(
                   maximum_attempts=2,
                   non_retryable_error_types=[PDFParseError, PDFValidationError],
               ),
           )

           # Step 2: LLM extraction
           extracted = await workflow.execute_activity(
               llm_extract,
               args=[document_id, parsed["text"]],
               start_to_close_timeout=timedelta(minutes=2),
               retry_policy=workflow.RetryPolicy(
                   maximum_attempts=3,
                   initial_interval=timedelta(seconds=2),
                   backoff_coefficient=2.0,
                   maximum_interval=timedelta(seconds=30),
               ),
           )

           # Step 3: Store results
           await workflow.execute_activity(
               store_results,
               args=[extraction_id, document_id, extracted],
               start_to_close_timeout=timedelta(minutes=1),
               retry_policy=workflow.RetryPolicy(maximum_attempts=3),
           )

           return {
               "status": "completed",
               "document_id": document_id,
               "extraction_id": extraction_id,
           }
   ```

3. **Update `worker/run.py`** to register workflow and activities:
   ```python
   from worker.activities import llm_extract, parse_pdf, store_results
   from worker.workflows import ExtractionWorkflow

   worker = Worker(
       client,
       task_queue=settings.WORKER_TASK_QUEUE,
       workflows=[ExtractionWorkflow],
       activities=[parse_pdf, llm_extract, store_results],
   )
   ```

4. **Write unit tests** in `tests/test_workflows.py`:
   - Use `temporalio.testing.WorkflowEnvironment` for isolated testing.
   - Mock activities to return canned values and verify call sequence.
   - Assert `extraction_id` is UUID format.
   - Assert retry policies are configured correctly.

5. **Run tests with coverage**:
   ```bash
   pytest tests/test_workflows.py -o "addopts=" --cov=worker.workflows --cov-report=term-missing
   ```

## Concrete Steps

Work from repository root.

1. **Inspect current state**:
   ```bash
   cat worker/workflows.py
   cat worker/run.py
   ```

2. **Implement workflow** in `worker/workflows.py` per the code example above.

3. **Update worker bootstrap** in `worker/run.py`:
   - Add imports for activities and workflow
   - Update `workflows=[]` to `workflows=[ExtractionWorkflow]`
   - Update `activities=[]` to `activities=[parse_pdf, llm_extract, store_results]`

4. **Create `tests/test_workflows.py`**:
   ```python
   import re
   from datetime import timedelta
   from unittest.mock import AsyncMock, patch

   import pytest
   from temporalio.testing import WorkflowEnvironment
   from temporalio.worker import Worker

   from worker.workflows import ExtractionWorkflow

   UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')


   @pytest.fixture
   async def workflow_env():
       async with await WorkflowEnvironment.start_time_skipping() as env:
           yield env


   @pytest.mark.asyncio
   async def test_extraction_workflow_happy_path(workflow_env):
       # Define mock activities
       async def mock_parse_pdf(document_id: str) -> dict:
           return {"text": "Contract text...", "page_count": 3}

       async def mock_llm_extract(document_id: str, text: str) -> dict:
           return {"confidence": 0.9, "parties": {}, "clauses": {}}

       async def mock_store_results(extraction_id: str, document_id: str, data: dict) -> None:
           pass

       async with Worker(
           workflow_env.client,
           task_queue="test-queue",
           workflows=[ExtractionWorkflow],
           activities=[mock_parse_pdf, mock_llm_extract, mock_store_results],
       ):
           result = await workflow_env.client.execute_workflow(
               ExtractionWorkflow.run,
               "doc-123",
               id="test-workflow-id",
               task_queue="test-queue",
           )

       assert result["status"] == "completed"
       assert result["document_id"] == "doc-123"
       assert UUID_PATTERN.match(result["extraction_id"])
   ```

5. **Run tests**:
   ```bash
   pytest tests/test_workflows.py -o "addopts=" --cov=worker.workflows --cov-report=term-missing -v
   ```

## Validation and Acceptance

Work is accepted when:
- `worker/workflows.py` defines `ExtractionWorkflow.run(document_id)` using the three activities with specified retry policies.
- Stable `extraction_id` is generated once per workflow execution and passed to `store_results`; returned in workflow result.
- `parse_pdf` policy treats `PDFParseError` and `PDFValidationError` as non-retryable.
- `llm_extract` has exponential backoff retry policy.
- `store_results` has light retries (idempotent).
- `worker/run.py` registers the workflow and all three activities.
- Unit tests pass with ≥95% coverage for `worker/workflows.py`.
- No side effects occur in the workflow code; activities own all I/O.

## Idempotence and Recovery

- Workflow can be retried/replayed safely because `extraction_id` is generated deterministically at workflow start and activities are idempotent.
- Activity retries are bounded and respect non-retryable error types.
- Tests are repeatable using `WorkflowEnvironment` for isolation.

## Artifacts and Notes

Expected test command:
```bash
pytest tests/test_workflows.py -o "addopts=" --cov=worker.workflows --cov-report=term-missing
```

Files to create/modify:
- `worker/workflows.py` - Implement ExtractionWorkflow
- `worker/run.py` - Register workflow and activities
- `tests/test_workflows.py` - Unit tests (new file)

## Interfaces and Dependencies

- **Temporal workflow API**: `temporalio.workflow.defn`, `workflow.run`, `workflow.execute_activity`, `workflow.RetryPolicy`, `workflow.unsafe.imports_passed_through`.
- **Activities** (synchronous, from T-07):
  - `parse_pdf(document_id: str) -> dict[str, Any]` - Returns `{"text": str, "page_count": int}`
  - `llm_extract(document_id: str, text: str) -> dict[str, Any]` - Returns extraction dict
  - `store_results(extraction_id: str, document_id: str, extraction_data: dict) -> None`
- **Error types** for retry policy:
  - `app.pdf_parser.PDFParseError` - Parse failures (retryable by workflow decision)
  - `app.pdf_parser.PDFValidationError` - Validation failures (non-retryable)
  - `worker.llm_extractor.LLMExtractError` - LLM failures (let retry policy handle)
- **UUID generation**: `uuid.uuid4()` for stable `extraction_id`.
- **Testing**: `temporalio.testing.WorkflowEnvironment` for isolated workflow tests.

Initial version created 2025-01-09.
