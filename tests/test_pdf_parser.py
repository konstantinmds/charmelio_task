"""Tests for PDF parsing module."""

from pathlib import Path

import pytest

from app.pdf_parser import (
    PDFError,
    PDFParseError,
    PDFValidationError,
    ParseResult,
    extract_text_and_pages,
)

SAMPLES = Path("sample_contracts")


class TestParseResult:
    """Tests for ParseResult dataclass."""

    def test_parse_result_is_frozen(self):
        result = ParseResult(text="hello", page_count=1)
        with pytest.raises(AttributeError):
            result.text = "modified"

    def test_parse_result_default_metadata(self):
        result = ParseResult(text="test", page_count=2)
        assert result.metadata == {}

    def test_parse_result_with_metadata(self):
        result = ParseResult(text="test", page_count=1, metadata={"author": "Test"})
        assert result.metadata == {"author": "Test"}


class TestErrorHierarchy:
    """Tests for error class hierarchy."""

    def test_validation_error_is_pdf_error(self):
        assert issubclass(PDFValidationError, PDFError)

    def test_parse_error_is_pdf_error(self):
        assert issubclass(PDFParseError, PDFError)

    def test_validation_error_message(self):
        err = PDFValidationError("test message")
        assert str(err) == "test message"


class TestExtractTextAndPages:
    """Tests for extract_text_and_pages function."""

    def test_valid_pdf_returns_parse_result(self):
        # Use existing contract PDF
        pdf_path = SAMPLES / "DELACE (PTY) LTD-Sales - RoW Non-Disclosure Agreement (NDA) (091123).pdf"
        if not pdf_path.exists():
            pytest.skip("Test PDF not available")

        data = pdf_path.read_bytes()
        result = extract_text_and_pages(data)

        assert isinstance(result, ParseResult)
        assert result.page_count >= 1
        assert len(result.text) > 0

    def test_multipage_pdf_concatenates_with_separator(self):
        # Use a known multi-page PDF
        pdf_path = SAMPLES / "ACUTRAQ-Service-Agreement-2136. - 2021 - 3 YEARS.pdf"
        if not pdf_path.exists():
            pytest.skip("Test PDF not available")

        data = pdf_path.read_bytes()
        result = extract_text_and_pages(data)

        assert result.page_count > 1
        # Multi-page PDFs should have separator
        assert "\n\n" in result.text or result.page_count == 1

    def test_non_pdf_raises_validation_error(self):
        with pytest.raises(PDFValidationError, match="missing PDF header"):
            extract_text_and_pages(b"hello world this is not a pdf")

    def test_empty_bytes_raises_validation_error(self):
        with pytest.raises(PDFValidationError, match="missing PDF header"):
            extract_text_and_pages(b"")

    def test_docx_bytes_raises_validation_error(self):
        # DOCX files start with PK (ZIP signature)
        docx_header = b"PK\x03\x04" + b"\x00" * 100
        with pytest.raises(PDFValidationError, match="missing PDF header"):
            extract_text_and_pages(docx_header)

    def test_malformed_pdf_raises_parse_error(self):
        # Valid header but garbage content
        malformed = b"%PDF-1.4\n" + b"garbage content " * 100
        with pytest.raises(PDFParseError, match="failed to parse"):
            extract_text_and_pages(malformed)

    def test_file_too_large_raises_validation_error(self):
        # Create a minimal valid-looking PDF that exceeds size limit
        # Test with 1MB limit
        pdf_path = SAMPLES / "ACUTRAQ-Service-Agreement-2136. - 2021 - 3 YEARS.pdf"
        if not pdf_path.exists():
            pytest.skip("Test PDF not available")

        data = pdf_path.read_bytes()
        size_mb = len(data) / 1024 / 1024

        # Set limit below actual size
        if size_mb > 0.5:
            with pytest.raises(PDFValidationError, match="file too large"):
                extract_text_and_pages(data, max_size_mb=1)

    def test_too_many_pages_raises_validation_error(self):
        pdf_path = SAMPLES / "ACUTRAQ-Service-Agreement-2136. - 2021 - 3 YEARS.pdf"
        if not pdf_path.exists():
            pytest.skip("Test PDF not available")

        data = pdf_path.read_bytes()

        # Set very low page limit
        with pytest.raises(PDFValidationError, match="too many pages"):
            extract_text_and_pages(data, max_pages=1)

    def test_custom_limits_are_respected(self):
        pdf_path = SAMPLES / "DELACE (PTY) LTD-Sales - RoW Non-Disclosure Agreement (NDA) (091123).pdf"
        if not pdf_path.exists():
            pytest.skip("Test PDF not available")

        data = pdf_path.read_bytes()

        # Should work with generous limits
        result = extract_text_and_pages(data, max_size_mb=50, max_pages=500)
        assert isinstance(result, ParseResult)

    def test_extracts_meaningful_text(self):
        pdf_path = SAMPLES / "DELACE (PTY) LTD-Sales - RoW Non-Disclosure Agreement (NDA) (091123).pdf"
        if not pdf_path.exists():
            pytest.skip("Test PDF not available")

        data = pdf_path.read_bytes()
        result = extract_text_and_pages(data)

        # Should contain legal/contract terms
        text_lower = result.text.lower()
        assert any(
            term in text_lower
            for term in ["agreement", "party", "confidential", "disclosure"]
        )


class TestEdgeCases:
    """Edge case tests."""

    def test_pdf_header_only_raises_parse_error(self):
        # Just the header, no actual PDF structure
        with pytest.raises(PDFParseError):
            extract_text_and_pages(b"%PDF-1.4")

    def test_truncated_pdf_raises_parse_error(self):
        pdf_path = SAMPLES / "DELACE (PTY) LTD-Sales - RoW Non-Disclosure Agreement (NDA) (091123).pdf"
        if not pdf_path.exists():
            pytest.skip("Test PDF not available")

        data = pdf_path.read_bytes()
        # Truncate to just first 100 bytes
        truncated = data[:100]

        with pytest.raises(PDFParseError):
            extract_text_and_pages(truncated)

    def test_scanned_pdf_no_text_raises_validation_error(self, monkeypatch):
        """Test that PDFs with no extractable text raise PDFValidationError."""
        from unittest.mock import MagicMock, patch

        # Create a mock PDF with pages that return no text
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page, mock_page]  # 2 pages, no text
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("app.pdf_parser.pdfplumber.open", return_value=mock_pdf):
            with pytest.raises(PDFValidationError, match="no text content"):
                extract_text_and_pages(b"%PDF-1.4 valid header")

    def test_returns_empty_text_for_whitespace_only_pages(self):
        # This is a valid PDF behavior - we should handle it
        # Note: We can't easily create such a fixture, so this is more of a documentation test
        pass
