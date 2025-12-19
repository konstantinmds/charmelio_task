"""Tests for LLM extractor module."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)

from app.schemas.domain import ExtractionResult
from worker.llm_extractor import (
    LLM_MAX_CHARS,
    LLM_MAX_RETRIES,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_TIMEOUT_S,
    LLMExtractError,
    _get_client,
    _truncate_text,
    extract_clauses,
)


def make_valid_response_data():
    """Create a valid extraction response data structure."""
    return {
        "parties": {
            "party_one": "Acme Corp",
            "party_two": "Widget Inc",
            "additional_parties": [],
        },
        "dates": {
            "effective_date": "2024-01-01",
            "termination_date": "2025-01-01",
            "term_length": "1 year",
        },
        "clauses": {
            "governing_law": "State of Delaware",
            "termination": "30 days written notice",
            "confidentiality": "Standard NDA terms apply",
            "indemnification": "Mutual indemnification",
            "limitation_of_liability": "Limited to contract value",
            "dispute_resolution": "Arbitration in Delaware",
            "payment_terms": "Net 30",
            "intellectual_property": "Each party retains own IP",
        },
        "confidence": 0.85,
        "summary": "Service agreement between Acme Corp and Widget Inc",
    }


def create_mock_response(data):
    """Create a mock OpenAI chat completion response."""
    mock_message = Mock()
    mock_message.content = json.dumps(data)

    mock_choice = Mock()
    mock_choice.message = mock_message

    mock_response = Mock()
    mock_response.choices = [mock_choice]

    return mock_response


def create_mock_client(response_data=None, side_effect=None):
    """Create a mock OpenAI client."""
    mock_client = MagicMock()

    if side_effect:
        mock_client.chat.completions.create.side_effect = side_effect
    elif response_data is not None:
        mock_client.chat.completions.create.return_value = create_mock_response(response_data)
    else:
        mock_client.chat.completions.create.return_value = create_mock_response(make_valid_response_data())

    return mock_client


class TestConfiguration:
    """Tests for configuration values."""

    def test_default_model(self):
        assert LLM_MODEL == "gpt-4o-mini"

    def test_default_max_chars(self):
        assert LLM_MAX_CHARS == 200000

    def test_default_temperature(self):
        assert LLM_TEMPERATURE == 0.1

    def test_default_timeout(self):
        assert LLM_TIMEOUT_S == 60

    def test_default_max_retries(self):
        assert LLM_MAX_RETRIES == 3


class TestTruncateText:
    """Tests for text truncation."""

    def test_short_text_unchanged(self):
        text = "Short text"
        result = _truncate_text(text, 100)
        assert result == text

    def test_exact_length_unchanged(self):
        text = "x" * 100
        result = _truncate_text(text, 100)
        assert result == text

    def test_long_text_truncated(self):
        text = "x" * 200
        result = _truncate_text(text, 100)
        assert len(result) <= 100

    def test_truncate_preserves_sentence_boundary(self):
        text = "First sentence. Second sentence. Third sentence."
        # Truncate at 35 chars, should end at "Second sentence."
        result = _truncate_text(text, 35)
        assert result.endswith(".")

    def test_truncate_no_period_in_range(self):
        text = "x" * 100 + "."
        # Period is at the end, beyond 80% threshold
        result = _truncate_text(text, 50)
        assert len(result) == 50  # No sentence boundary found


class TestExtractClausesHappyPath:
    """Tests for successful extraction."""

    def test_returns_extraction_result(self):
        mock_client = create_mock_client()
        result = extract_clauses("Sample contract text", client=mock_client)
        assert isinstance(result, ExtractionResult)

    def test_extracts_parties(self):
        mock_client = create_mock_client()
        result = extract_clauses("Sample contract text", client=mock_client)
        assert result.parties.party_one == "Acme Corp"
        assert result.parties.party_two == "Widget Inc"

    def test_extracts_dates(self):
        mock_client = create_mock_client()
        result = extract_clauses("Sample contract text", client=mock_client)
        assert result.dates.effective_date == "2024-01-01"
        assert result.dates.termination_date == "2025-01-01"

    def test_extracts_clauses(self):
        mock_client = create_mock_client()
        result = extract_clauses("Sample contract text", client=mock_client)
        assert result.clauses.governing_law == "State of Delaware"
        assert result.clauses.payment_terms == "Net 30"

    def test_extracts_confidence(self):
        mock_client = create_mock_client()
        result = extract_clauses("Sample contract text", client=mock_client)
        assert result.confidence == 0.85

    def test_extracts_summary(self):
        mock_client = create_mock_client()
        result = extract_clauses("Sample contract text", client=mock_client)
        assert "Service agreement" in result.summary


class TestExtractClausesValidation:
    """Tests for input validation."""

    def test_empty_string_raises_error(self):
        with pytest.raises(LLMExtractError, match="Empty text provided"):
            extract_clauses("")

    def test_whitespace_only_raises_error(self):
        with pytest.raises(LLMExtractError, match="Empty text provided"):
            extract_clauses("   \n\t  ")

    def test_none_text_raises_error(self):
        with pytest.raises(LLMExtractError, match="Empty text provided"):
            extract_clauses(None)


class TestExtractClausesAPIErrors:
    """Tests for API error handling."""

    def test_authentication_error_not_retried(self):
        mock_client = create_mock_client(
            side_effect=AuthenticationError(
                message="Invalid API key",
                response=Mock(status_code=401),
                body=None,
            )
        )
        with pytest.raises(LLMExtractError, match="Non-retryable API error"):
            extract_clauses("Test text", client=mock_client)

        # Should only be called once (not retried)
        assert mock_client.chat.completions.create.call_count == 1

    def test_bad_request_error_not_retried(self):
        mock_client = create_mock_client(
            side_effect=BadRequestError(
                message="Bad request",
                response=Mock(status_code=400),
                body=None,
            )
        )
        with pytest.raises(LLMExtractError, match="Non-retryable API error"):
            extract_clauses("Test text", client=mock_client)

        assert mock_client.chat.completions.create.call_count == 1

    def test_rate_limit_error_retried(self):
        mock_client = create_mock_client(
            side_effect=RateLimitError(
                message="Rate limited",
                response=Mock(status_code=429),
                body=None,
            )
        )

        with pytest.raises(LLMExtractError, match="API error after"):
            extract_clauses("Test text", client=mock_client)

        # Should be retried LLM_MAX_RETRIES times
        assert mock_client.chat.completions.create.call_count == LLM_MAX_RETRIES

    def test_connection_error_retried(self):
        mock_client = create_mock_client(
            side_effect=APIConnectionError(message="Connection failed", request=Mock())
        )

        with pytest.raises(LLMExtractError, match="API error after"):
            extract_clauses("Test text", client=mock_client)

        assert mock_client.chat.completions.create.call_count == LLM_MAX_RETRIES

    def test_timeout_error_retried(self):
        mock_client = create_mock_client(
            side_effect=APITimeoutError(request=Mock())
        )

        with pytest.raises(LLMExtractError, match="API error after"):
            extract_clauses("Test text", client=mock_client)

        assert mock_client.chat.completions.create.call_count == LLM_MAX_RETRIES

    def test_internal_server_error_retried(self):
        mock_client = create_mock_client(
            side_effect=InternalServerError(
                message="Server error",
                response=Mock(status_code=500),
                body=None,
            )
        )

        with pytest.raises(LLMExtractError, match="API error after"):
            extract_clauses("Test text", client=mock_client)

        assert mock_client.chat.completions.create.call_count == LLM_MAX_RETRIES

    def test_retry_succeeds_on_second_attempt(self):
        # First call fails, second succeeds
        mock_client = create_mock_client()
        mock_client.chat.completions.create.side_effect = [
            RateLimitError(
                message="Rate limited",
                response=Mock(status_code=429),
                body=None,
            ),
            create_mock_response(make_valid_response_data()),
        ]

        result = extract_clauses("Test text", client=mock_client)
        assert isinstance(result, ExtractionResult)
        assert mock_client.chat.completions.create.call_count == 2


class TestExtractClausesResponseErrors:
    """Tests for response handling errors."""

    def test_empty_response_raises_error(self):
        mock_message = Mock()
        mock_message.content = None

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMExtractError, match="Empty response"):
            extract_clauses("Test text", client=mock_client)

    def test_empty_string_response_raises_error(self):
        mock_message = Mock()
        mock_message.content = ""

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMExtractError, match="Empty response"):
            extract_clauses("Test text", client=mock_client)

    def test_invalid_json_raises_error(self):
        mock_message = Mock()
        mock_message.content = "not valid json {{"

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMExtractError, match="Invalid JSON"):
            extract_clauses("Test text", client=mock_client)

    def test_missing_required_field_raises_error(self):
        incomplete_data = {"parties": {}}  # Missing required fields

        mock_client = create_mock_client(response_data=incomplete_data)

        with pytest.raises(LLMExtractError):
            extract_clauses("Test text", client=mock_client)


class TestExtractClausesTruncation:
    """Tests for text truncation behavior."""

    def test_long_text_is_truncated(self):
        mock_client = create_mock_client()
        long_text = "x" * (LLM_MAX_CHARS + 10000)

        result = extract_clauses(long_text, client=mock_client)

        # Verify the call was made with truncated text
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        user_content = messages[1]["content"]

        # The text in the message should be truncated
        assert len(user_content) <= LLM_MAX_CHARS + 100  # Some buffer for prompt


class TestClientInjection:
    """Tests for dependency injection."""

    def test_uses_provided_client(self):
        mock_client = create_mock_client()
        extract_clauses("Test text", client=mock_client)
        mock_client.chat.completions.create.assert_called_once()

    @patch("worker.llm_extractor._get_client")
    def test_uses_default_client_when_none_provided(self, mock_get_client):
        mock_client = create_mock_client()
        mock_get_client.return_value = mock_client

        extract_clauses("Test text")

        mock_get_client.assert_called_once()
        mock_client.chat.completions.create.assert_called_once()


class TestGetClient:
    """Tests for lazy client initialization."""

    @patch("worker.llm_extractor._client", None)
    @patch("worker.llm_extractor.OpenAI")
    def test_creates_client_on_first_call(self, mock_openai_class):
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        result = _get_client()

        mock_openai_class.assert_called_once_with(timeout=LLM_TIMEOUT_S)
        assert result == mock_client


class TestAPICallParameters:
    """Tests for correct API call parameters."""

    def test_uses_correct_model(self):
        mock_client = create_mock_client()
        extract_clauses("Test text", client=mock_client)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == LLM_MODEL

    def test_uses_correct_temperature(self):
        mock_client = create_mock_client()
        extract_clauses("Test text", client=mock_client)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == LLM_TEMPERATURE

    def test_includes_system_prompt(self):
        mock_client = create_mock_client()
        extract_clauses("Test text", client=mock_client)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert "legal document analyzer" in messages[0]["content"]

    def test_includes_user_message_with_text(self):
        mock_client = create_mock_client()
        extract_clauses("My contract text", client=mock_client)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        assert messages[1]["role"] == "user"
        assert "My contract text" in messages[1]["content"]

    def test_uses_json_schema_response_format(self):
        mock_client = create_mock_client()
        extract_clauses("Test text", client=mock_client)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "response_format" in call_kwargs
        assert call_kwargs["response_format"]["type"] == "json_schema"


class TestNullHandling:
    """Tests for handling null values in response."""

    def test_handles_null_parties(self):
        data = make_valid_response_data()
        data["parties"]["party_one"] = None
        data["parties"]["party_two"] = None

        mock_client = create_mock_client(response_data=data)
        result = extract_clauses("Test text", client=mock_client)

        assert result.parties.party_one is None
        assert result.parties.party_two is None

    def test_handles_null_dates(self):
        data = make_valid_response_data()
        data["dates"]["effective_date"] = None
        data["dates"]["termination_date"] = None

        mock_client = create_mock_client(response_data=data)
        result = extract_clauses("Test text", client=mock_client)

        assert result.dates.effective_date is None
        assert result.dates.termination_date is None

    def test_handles_null_clauses(self):
        data = make_valid_response_data()
        data["clauses"]["governing_law"] = None
        data["clauses"]["payment_terms"] = None

        mock_client = create_mock_client(response_data=data)
        result = extract_clauses("Test text", client=mock_client)

        assert result.clauses.governing_law is None
        assert result.clauses.payment_terms is None

    def test_handles_null_summary(self):
        data = make_valid_response_data()
        data["summary"] = None

        mock_client = create_mock_client(response_data=data)
        result = extract_clauses("Test text", client=mock_client)

        assert result.summary is None
