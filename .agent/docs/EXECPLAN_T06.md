# T-06 OpenAI LLM Adapter (Structured Outputs)

This ExecPlan is a living document. Maintain it in accordance with `.agent/PLANS.md` from the repository root so a newcomer can complete the work using only this file.

## Purpose / Big Picture

Build a small, deterministic adapter that turns raw contract text into a validated `ExtractionResult` using OpenAI Chat Completions API with JSON Schema (Structured Outputs). This isolates SDK details from FastAPI/Temporal callers, guarantees schema-conformant outputs, and centralizes prompt, truncation, and retry policy in one place.

**Why this matters:**
- Downstream code never parses prose; it consumes a Pydantic `ExtractionResult`.
- One module owns prompt/model/backoff/safety knobs to avoid configuration drift.
- Deterministic, replay-safe behavior for Temporal activities.

## Progress

- [ ] Create `app/schemas/domain.py` with `ExtractionResult` Pydantic model
- [ ] Add `tenacity` to dependencies for retry logic
- [ ] Implement adapter in `worker/llm_extractor.py`
- [ ] Add custom error `LLMExtractError`
- [ ] Wire env-configurable model/limits/temperature
- [ ] Add unit tests with mocks covering happy path, schema errors, retries, truncation
- [ ] Achieve ≥95% coverage for `worker/llm_extractor.py`

## Surprises & Discoveries

- None yet; document SDK quirks as discovered.

## Decision Log

- (2025-12-18) **Use chat.completions.create, NOT responses.create**: The OpenAI SDK uses `client.chat.completions.create()` with `response_format` for structured outputs.
- (2025-12-18) **Sync function, not async**: For Temporal activities, sync functions are simpler. Use `OpenAI` (sync), not `AsyncOpenAI`.
- (2025-12-18) **Specific retryable errors**: Only retry on `RateLimitError`, `APIConnectionError`, `APITimeoutError`, `InternalServerError`. Non-retryable errors (auth, bad request) fail immediately.
- (2025-12-18) **Lazy client initialization**: Don't create client at import time (breaks testing). Use `_get_client()` pattern.
- (2025-12-18) **Dependency injection for testing**: Accept optional `client` parameter to inject mock clients.
- (2025-12-18) **Use tenacity for retries**: Clean declarative retry logic with exponential backoff.

## Outcomes & Retrospective

**Target deliverables (post-implementation checklist):**
- `app/schemas/domain.py` with `ExtractionResult` Pydantic model
- `worker/llm_extractor.py` exposing `extract_clauses(text: str, client: OpenAI | None = None) -> ExtractionResult` and `LLMExtractError`
- Uses OpenAI Chat Completions API with `response_format` for Structured Outputs
- Validates and returns `ExtractionResult`; never returns `None`
- Unit tests (mocked SDK) cover all paths; ≥95% coverage

---

## Context and Orientation

- **Repository root:** `/Users/tijanapetrovic/Documents/inner_outer_projs/charmelio_clean`
- **Files to create:**
  - `app/schemas/__init__.py`
  - `app/schemas/domain.py` - ExtractionResult model
  - `worker/llm_extractor.py` - LLM adapter
  - `tests/test_llm_extractor.py` - Unit tests
- **Settings:** Environment variables for configuration
- **SDK:** `openai` client using `chat.completions.create` with `response_format`

---

## Interfaces and Dependencies

### ExtractionResult Schema

```python
# app/schemas/domain.py
from pydantic import BaseModel, Field
from typing import Optional

class PartiesInfo(BaseModel):
    party_one: Optional[str] = None
    party_two: Optional[str] = None
    additional_parties: list[str] = Field(default_factory=list)

class DatesInfo(BaseModel):
    effective_date: Optional[str] = None  # ISO format YYYY-MM-DD
    termination_date: Optional[str] = None
    term_length: Optional[str] = None

class ClausesInfo(BaseModel):
    governing_law: Optional[str] = None
    termination: Optional[str] = None
    confidentiality: Optional[str] = None
    indemnification: Optional[str] = None
    limitation_of_liability: Optional[str] = None
    dispute_resolution: Optional[str] = None
    payment_terms: Optional[str] = None
    intellectual_property: Optional[str] = None

class ExtractionResult(BaseModel):
    parties: PartiesInfo
    dates: DatesInfo
    clauses: ClausesInfo
    confidence: float = Field(ge=0.0, le=1.0)
    summary: Optional[str] = None
```

### Public Interface

```python
# worker/llm_extractor.py
from openai import OpenAI
from app.schemas.domain import ExtractionResult

class LLMExtractError(RuntimeError):
    """Raised when LLM extraction fails."""
    pass

def extract_clauses(text: str, client: OpenAI | None = None) -> ExtractionResult:
    """Extract contract clauses using OpenAI structured outputs.

    Args:
        text: Plain text extracted from contract PDF.
        client: Optional OpenAI client (for testing).

    Returns:
        Validated ExtractionResult.

    Raises:
        LLMExtractError: On any failure (API, validation, exhausted retries).
    """
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required) | API key for OpenAI |
| `LLM_MODEL` | `gpt-4o-mini` | Model to use |
| `LLM_MAX_CHARS` | `200000` | Max input characters |
| `LLM_TEMPERATURE` | `0.1` | Low temperature for determinism |
| `LLM_TIMEOUT_S` | `60` | API timeout in seconds |
| `LLM_MAX_RETRIES` | `3` | Max retry attempts |

### Retryable Errors

```python
from openai import RateLimitError, APIConnectionError, APITimeoutError, InternalServerError

RETRYABLE_ERRORS = (
    RateLimitError,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
)
```

---

## Plan of Work

### 1. Create Schema
Create `app/schemas/domain.py` with `ExtractionResult` and nested models.

### 2. Add Dependency
Add `tenacity` to `pyproject.toml` dependencies.

### 3. Implement Adapter
Create `worker/llm_extractor.py` with:
- Lazy client initialization (`_get_client()`)
- Configuration from environment
- System prompt for extraction
- `_call_openai()` with tenacity retry decorator
- `extract_clauses()` main entry point
- Proper error handling (retryable vs non-retryable)

### 4. Write Tests
Create `tests/test_llm_extractor.py`:
- Happy path with mocked response
- Empty text validation
- Invalid JSON response
- Missing required fields
- Truncation for long text
- Retry on rate limit
- Exhausted retries
- Empty response handling
- Config verification

### 5. Run Coverage
```bash
pytest tests/test_llm_extractor.py --cov=worker.llm_extractor --cov-report=term-missing
```

---

## Concrete Steps

1. **Create schemas directory and domain.py**
2. **Add tenacity to pyproject.toml**
3. **Create worker/llm_extractor.py** with corrected implementation
4. **Create tests/test_llm_extractor.py**
5. **Run tests and verify coverage**
6. **Update EXECPLAN with results**

---

## Validation and Acceptance

- [ ] `app/schemas/domain.py` exists with `ExtractionResult`
- [ ] `worker/llm_extractor.py` exists with `extract_clauses` and `LLMExtractError`
- [ ] Uses `chat.completions.create` with `response_format` (NOT `responses.create`)
- [ ] Function is sync (not async) for Temporal compatibility
- [ ] Lazy client initialization with `_get_client()`
- [ ] Client injectable via parameter for testing
- [ ] Only retries on specific retryable errors
- [ ] Raises `LLMExtractError` on any failure; never returns `None`
- [ ] Tests cover all paths with mocked SDK
- [ ] Coverage for `worker/llm_extractor.py` ≥95%

---

## Idempotence and Recovery

- Safe to rerun tests and adapter creation
- Retries use exponential backoff via tenacity
- Adjust `LLM_MAX_RETRIES` and `LLM_TIMEOUT_S` via env without code changes

---

## Artifacts and Notes

**New files:**
- `app/schemas/__init__.py`
- `app/schemas/domain.py`
- `worker/llm_extractor.py`
- `tests/test_llm_extractor.py`

**Modified files:**
- `pyproject.toml` (add tenacity)

**Environment variables:** `OPENAI_API_KEY`, `LLM_MODEL`, `LLM_MAX_CHARS`, `LLM_TIMEOUT_S`, `LLM_MAX_RETRIES`, `LLM_TEMPERATURE`

---

## Temporal Activity Integration (T-07 Preview)

```python
@activity.defn
def llm_extract(document_id: str, text: str) -> dict:
    """Extract clauses using LLM."""
    from worker.llm_extractor import extract_clauses, LLMExtractError

    try:
        result = extract_clauses(text)
        return result.model_dump()
    except LLMExtractError as e:
        # Let Temporal handle retry based on error type
        raise
```

---

Initial version created 2025-12-18.
