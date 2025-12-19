"""OpenAI LLM adapter for contract clause extraction.

Uses OpenAI Chat Completions API with Structured Outputs to extract
contract information into a validated ExtractionResult.
"""

import os
from typing import Optional

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.schemas.domain import ExtractionResult

# Environment configuration with defaults
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
LLM_MAX_CHARS = int(os.environ.get("LLM_MAX_CHARS", "200000"))
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.1"))
LLM_TIMEOUT_S = int(os.environ.get("LLM_TIMEOUT_S", "60"))
LLM_MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES", "3"))

# Errors that are safe to retry (transient)
RETRYABLE_ERRORS = (
    RateLimitError,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
)

# System prompt for contract extraction
SYSTEM_PROMPT = """You are a legal document analyzer specializing in contract clause extraction.

Analyze the provided contract text and extract the following information:

1. **Parties**: Identify the contracting parties (party_one, party_two, and any additional parties)
2. **Dates**: Extract effective date, termination date, and term length (use ISO format YYYY-MM-DD for dates)
3. **Clauses**: Extract key clauses including:
   - Governing law (jurisdiction)
   - Termination provisions
   - Confidentiality terms
   - Indemnification clauses
   - Limitation of liability
   - Dispute resolution mechanism
   - Payment terms
   - Intellectual property provisions

4. **Confidence**: Rate your confidence in the extraction from 0.0 to 1.0
5. **Summary**: Provide a brief summary of the contract's purpose

If a field cannot be determined from the text, leave it as null.
Be precise and extract actual text snippets or paraphrased content, not placeholders."""


class LLMExtractError(RuntimeError):
    """Raised when LLM extraction fails."""

    pass


# Lazy client initialization
_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    """Get or create OpenAI client (lazy initialization)."""
    global _client
    if _client is None:
        _client = OpenAI(timeout=LLM_TIMEOUT_S)
    return _client


def _truncate_text(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, preserving complete sentences where possible."""
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]
    # Try to end at a sentence boundary
    last_period = truncated.rfind(".")
    if last_period > max_chars * 0.8:  # Only if we keep at least 80%
        truncated = truncated[: last_period + 1]

    return truncated


def _make_retry_decorator():
    """Create tenacity retry decorator with configured settings."""
    return retry(
        retry=retry_if_exception_type(RETRYABLE_ERRORS),
        stop=stop_after_attempt(LLM_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        reraise=True,
    )


def _call_openai(client: OpenAI, text: str) -> ExtractionResult:
    """Make OpenAI API call with structured output.

    Args:
        client: OpenAI client instance.
        text: Contract text to analyze.

    Returns:
        Validated ExtractionResult.

    Raises:
        Various OpenAI errors (handled by retry decorator or caller).
    """
    import json

    # Generate schema from Pydantic model (keeps schema and model in sync)
    schema = ExtractionResult.model_json_schema()

    response = client.chat.completions.create(
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this contract:\n\n{text}"},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "extraction_result",
                "strict": True,
                "schema": schema,
            },
        },
    )

    # Extract content from response
    content = response.choices[0].message.content
    if not content:
        raise LLMExtractError("Empty response from LLM")

    # Parse and validate with Pydantic
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise LLMExtractError(f"Invalid JSON response: {e}")

    return ExtractionResult.model_validate(data)


def extract_clauses(text: str, client: Optional[OpenAI] = None) -> ExtractionResult:
    """Extract contract clauses using OpenAI structured outputs.

    Args:
        text: Plain text extracted from contract PDF.
        client: Optional OpenAI client (for testing). If None, uses default client.

    Returns:
        Validated ExtractionResult.

    Raises:
        LLMExtractError: On any failure (API, validation, exhausted retries).
    """
    # Validate input
    if not text or not text.strip():
        raise LLMExtractError("Empty text provided")

    # Use provided client or get default
    actual_client = client if client is not None else _get_client()

    # Truncate if necessary
    truncated_text = _truncate_text(text, LLM_MAX_CHARS)

    # Create retry-wrapped function
    retry_decorator = _make_retry_decorator()
    retryable_call = retry_decorator(_call_openai)

    try:
        return retryable_call(actual_client, truncated_text)
    except RETRYABLE_ERRORS as e:
        # Retries exhausted (reraise=True means original exception is re-raised)
        raise LLMExtractError(f"API error after {LLM_MAX_RETRIES} retries: {e}")
    except (AuthenticationError, BadRequestError) as e:
        # Non-retryable errors - fail immediately
        raise LLMExtractError(f"Non-retryable API error: {e}")
    except Exception as e:
        # Catch-all for unexpected errors
        raise LLMExtractError(f"Unexpected error: {e}")
