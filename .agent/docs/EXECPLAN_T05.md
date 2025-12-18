# T-05 PDF Parsing Module

This ExecPlan is a living document. Maintain it in accordance with `.agent/PLANS.md` from the repository root so a newcomer can complete the work using only this file.

## Purpose / Big Picture

Turn uploaded PDF bytes into `(text: str, page_count: int)` reliably for native PDFs. The parser must be a **pure function** (bytes in → result out) to integrate seamlessly with Temporal Activities and enable easy testing/mocking.

**Why this matters:**
- LLM needs plain text; callers shouldn't know how to read PDFs
- Pure functions are deterministic and replay-safe for Temporal
- Deliberately avoiding OCR (MVP) - scanned PDFs handled later (T-XX)

## Progress

- [x] Add PDF parsing config to `app/core/config.py` (limits)
- [x] Create `app/pdf_parser.py` with error hierarchy and parse function
- [x] Add test fixtures to `sample_contracts/` (used existing contract PDFs)
- [x] Create `tests/test_pdf_parser.py` with comprehensive test coverage
- [x] Verify ≥95% coverage for `app/pdf_parser.py` (achieved 100%)

## Surprises & Discoveries

- (2025-12-18) pdfplumber.PDF doesn't have `is_encrypted` attribute - encrypted PDFs fail at open() or extract_text() instead. Removed explicit encryption check.
- (2025-12-18) Used existing contract PDFs in `sample_contracts/` instead of creating synthetic fixtures - more realistic testing.

## Decision Log

- (2025-12-18) **Pure function pattern**: Parser must be `extract_text_and_pages(bytes) → ParseResult` with no disk I/O, no async, no service class - required for Temporal Activity compatibility.
- (2025-12-18) **Two-tier error hierarchy**:
  - `PDFValidationError` - Pre-parse failures (not PDF, too large, too many pages, encrypted, scanned) → final fail, no retry
  - `PDFParseError` - Runtime parse failures (corrupted) → Temporal can retry
- (2025-12-18) **Early validation**: Check header, size, page count BEFORE expensive text extraction to fail fast.
- (2025-12-18) **Scanned PDF detection**: If no text extracted from any page, raise `PDFValidationError(no_text=True)` - OCR is out of scope.
- (2025-12-18) **Memory budget**: 25MB PDF ≈ 75MB RAM during parse. Worker concurrency should be limited accordingly.

## Outcomes & Retrospective

**Shipped:**
- `app/pdf_parser.py` - Pure function PDF parser with:
  - `PDFError`, `PDFValidationError`, `PDFParseError` error hierarchy
  - `ParseResult` frozen dataclass
  - `extract_text_and_pages(data, max_size_mb, max_pages)` function
  - Early validation (header, size, page count)
  - Scanned PDF detection
- `tests/test_pdf_parser.py` - 20 tests with 100% coverage
- Config additions: `PDF_MAX_FILE_SIZE_MB`, `PDF_MAX_PAGES`

**Key Design Decisions:**
- Pure function pattern for Temporal Activity compatibility
- Two-tier error hierarchy: ValidationError (final) vs ParseError (retryable)
- No disk I/O - works entirely on bytes

**Ready for T-07:** Parser integrates with Temporal Activity as shown in the integration preview section.

---

## Context and Orientation

**Repository root:** `/Users/tijanapetrovic/Documents/inner_outer_projs/charmelio_clean`

**Integration points:**
- `worker/activities.py` - Will have `parse_pdf` activity that fetches bytes from MinIO and calls this parser
- `app/storage/` - MinIO abstraction provides `get_bytes()` to fetch PDF bytes
- `app/core/config.py` - Settings for limits (max file size, max pages)

**Dependency:** `pdfplumber` (already in requirements.txt or add if missing)

---

## Interfaces and Dependencies

### Error Hierarchy

```python
class PDFError(Exception):
    """Base class for PDF-related errors."""
    pass

class PDFValidationError(PDFError):
    """Pre-parse validation failures - final, no retry."""
    pass

class PDFParseError(PDFError):
    """Runtime parse failures - may be retried."""
    pass
```

### Data Model

```python
@dataclass(frozen=True, slots=True)
class ParseResult:
    """Immutable result of PDF text extraction."""
    text: str           # Pages separated by \n\n
    page_count: int
    metadata: dict[str, Any] = field(default_factory=dict)  # Optional: author, title
```

### Main Function

```python
def extract_text_and_pages(
    data: bytes,
    *,
    max_size_mb: int = 25,
    max_pages: int = 100,
) -> ParseResult:
    """
    Extract text content and page count from PDF bytes.

    Args:
        data: Raw PDF file bytes
        max_size_mb: Maximum allowed file size in MB
        max_pages: Maximum allowed page count

    Returns:
        ParseResult with concatenated text and page count

    Raises:
        PDFValidationError: Not a PDF, too large, too many pages, encrypted, or scanned
        PDFParseError: Corrupted or unparseable PDF
    """
```

### Config Additions

Add to `app/core/config.py`:
```python
# PDF Parsing
PDF_MAX_FILE_SIZE_MB: int = 25
PDF_MAX_PAGES: int = 100
PDF_PARSE_TIMEOUT_SEC: int = 60
```

---

## Plan of Work

### 1. Update Configuration
Add PDF parsing limits to `app/core/config.py`:
- `PDF_MAX_FILE_SIZE_MB` (default: 25)
- `PDF_MAX_PAGES` (default: 100)

### 2. Implement Parser Module
Create `app/pdf_parser.py` with:

1. **Error classes**: `PDFError`, `PDFValidationError`, `PDFParseError`
2. **Result dataclass**: `ParseResult(text, page_count, metadata)`
3. **Main function**: `extract_text_and_pages(data, max_size_mb, max_pages)`

**Validation order (fail fast):**
1. Check `%PDF` header (cheap)
2. Check `len(data) <= max_size_mb * 1024 * 1024` (cheap)
3. Open with pdfplumber, check `len(pdf.pages) <= max_pages`
4. Check `pdf.is_encrypted` → reject
5. Extract text from all pages
6. Check if any text extracted → reject scanned PDFs

### 3. Create Test Fixtures
Add to `sample_contracts/`:
- `simple.pdf` - Normal contract with text
- `empty.pdf` - PDF with blank page(s)
- `multipage.pdf` - 3-page document

Or create `tools/gen_pdfs.py` using reportlab to generate fixtures programmatically.

### 4. Write Tests
Create `tests/test_pdf_parser.py`:

| Test Case | Input | Expected |
|-----------|-------|----------|
| Happy path | simple.pdf | ParseResult with text, pages ≥ 1 |
| Empty page | empty.pdf | ParseResult with empty/whitespace text |
| Multi-page | multipage.pdf | `\n\n` separators, page_count = 3 |
| Non-PDF | `b"hello world"` | PDFValidationError (missing header) |
| DOCX bytes | `b"PK\x03\x04..."` | PDFValidationError (not PDF) |
| Malformed | `b"%PDF-1.4\n" + garbage` | PDFParseError |
| Empty bytes | `b""` | PDFValidationError |
| Too large | 30MB bytes | PDFValidationError (size) |
| Too many pages | 150-page PDF | PDFValidationError (pages) |

---

## Concrete Steps

Work in `/Users/tijanapetrovic/Documents/inner_outer_projs/charmelio_clean`.

1. **Check pdfplumber dependency:**
   ```bash
   grep pdfplumber requirements.txt || echo "pdfplumber" >> requirements.txt
   ```

2. **Update config** - Edit `app/core/config.py`:
   - Add `PDF_MAX_FILE_SIZE_MB: int = 25`
   - Add `PDF_MAX_PAGES: int = 100`

3. **Create parser module** - Write `app/pdf_parser.py` with:
   - Error classes
   - ParseResult dataclass
   - extract_text_and_pages function
   - Validation logic

4. **Create/verify fixtures** - Ensure `sample_contracts/` has test PDFs

5. **Write tests** - Create `tests/test_pdf_parser.py`

6. **Run tests with coverage:**
   ```bash
   pytest tests/test_pdf_parser.py --cov=app/pdf_parser --cov-report=term-missing --cov-fail-under=95
   ```

---

## Validation and Acceptance

- [x] `app/pdf_parser.py` exists with `PDFValidationError`, `PDFParseError`, `ParseResult`, `extract_text_and_pages`
- [x] Config has `PDF_MAX_FILE_SIZE_MB` and `PDF_MAX_PAGES`
- [x] Unit tests cover: happy path, empty page, multi-page, non-PDF, malformed, size limit, page limit
- [x] Module has ≥95% coverage (achieved 100%)
- [x] No disk I/O in parser (works purely on bytes)
- [x] Scanned PDFs rejected with clear error

**Import check:**
```bash
python -c "from app.pdf_parser import extract_text_and_pages, ParseResult, PDFValidationError, PDFParseError; print('OK')"
```

---

## Idempotence and Recovery

- File creation and tests are safe to rerun
- Parser is a pure function with no side effects
- If tests fail, fix implementation and rerun pytest
- No external state or migrations touched

---

## Artifacts and Notes

**New files:**
- `app/pdf_parser.py`
- `tests/test_pdf_parser.py`
- `sample_contracts/simple.pdf` (if not exists)
- `sample_contracts/empty.pdf` (if not exists)
- `sample_contracts/multipage.pdf` (if not exists)

**Modified files:**
- `app/core/config.py` (add PDF limits)
- `requirements.txt` (add pdfplumber if missing)

**Environment variables (optional override):**
- `PDF_MAX_FILE_SIZE_MB`
- `PDF_MAX_PAGES`

---

## Temporal Activity Integration (T-07 Preview)

The parser will be called from `worker/activities.py`:

```python
@activity.defn
async def parse_pdf(document_id: str) -> dict:
    """Parse PDF and extract text."""
    from app.deps import get_storage
    from app.pdf_parser import extract_text_and_pages, PDFValidationError, PDFParseError
    from app.core.config import settings

    storage = get_storage()
    data, _ = storage.get_bytes("uploads", f"{document_id}.pdf")

    try:
        result = extract_text_and_pages(
            data,
            max_size_mb=settings.PDF_MAX_FILE_SIZE_MB,
            max_pages=settings.PDF_MAX_PAGES,
        )
        return {"text": result.text, "page_count": result.page_count}
    except PDFValidationError as e:
        # Final failure - update document status, no retry
        update_document_status(document_id, "invalid", str(e))
        raise ApplicationError(str(e), non_retryable=True)
    except PDFParseError as e:
        # Retryable - let Temporal retry policy handle it
        raise
```

---

## Security Considerations

- **Timeout**: Set Temporal Activity `start_to_close_timeout` to prevent DoS from malicious PDFs
- **Memory**: Limit worker concurrency based on `(container_mem_mb / (max_pdf_mb * 3))`
- **pdfminer quirks**: Use `strict=False` in pdfplumber to avoid hanging on benign xref issues

---

Initial version created 2025-12-18.
