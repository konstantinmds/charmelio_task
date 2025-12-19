# T-11 & T-12: Extractions Read APIs

## Purpose

Expose read-only APIs to fetch extraction results:
- `GET /api/extractions/{document_id}` - latest extraction for a document
- `GET /api/extractions` - paginated list of all extractions (newest first)

All data from database only. No MinIO/Temporal calls for these endpoints.

## Progress

- [x] Create response models in `app/schemas/api.py`
- [x] Implement router `app/routes/extractions.py` with two endpoints
- [x] Wire router into `app/main.py`
- [x] Add unit tests (9 tests)

## Decision Log

| Decision | Rationale |
|----------|-----------|
| DB-only reads | No MinIO/Temporal calls - fast and simple |
| GET by `document_id` | Per assignment spec - returns latest extraction for that document (not by extraction_id) |
| Ordering by `created_at DESC` | Uses existing index `(document_id, created_at)` |
| 404 if no extraction | Simpler for MVP. Client gets clear "not found" vs "processing" |
| Pagination returns empty if page exceeds total | No error, just empty `items` array |
| Async SQLAlchemy | Match existing codebase pattern (AsyncSession) |
| Test seeding with explicit timestamps | Deterministic ordering in tests |

## Implementation

### Response Models: `app/schemas/api.py`

```python
class ExtractionResponse(BaseModel):
    extraction_id: str
    document_id: str
    filename: str
    status: str
    model_used: str
    extraction_result: ExtractionResult
    created_at: datetime

class ExtractionListResponse(BaseModel):
    items: list[ExtractionResponse]
    total: int
    page: int
    page_size: int
```

### Router: `app/routes/extractions.py`

**Helper function**: `_build_extraction_response(doc, ext)` - maps DB models to response

**Endpoints**:

| Endpoint | Response | Errors |
|----------|----------|--------|
| `GET /{document_id}` | ExtractionResponse | 404 document not found, 404 no extraction |
| `GET /` | ExtractionListResponse | None (empty list if no data) |

**Pagination**:
- `page` (default=1, min=1)
- `page_size` (default=10, min=1, max=100)
- Offset calculation: `(page - 1) * page_size`

### Flow

**Single extraction**:
```
1. Fetch Document by id → 404 if missing
2. Fetch latest Extraction (ORDER BY created_at DESC LIMIT 1) → 404 if none
3. Return mapped ExtractionResponse
```

**List extractions**:
```
1. Count total extractions
2. If total=0 → return empty list
3. Join Extraction + Document, ORDER BY created_at DESC, OFFSET/LIMIT
4. Return ExtractionListResponse with items, total, page, page_size
```

## Files

| File | Action |
|------|--------|
| `app/schemas/api.py` | NEW - response models |
| `app/routes/__init__.py` | NEW - empty package |
| `app/routes/extractions.py` | NEW - router |
| `app/main.py` | MODIFY - include router |
| `tests/test_api_extractions.py` | NEW - tests |

## Tests

| Test Case | Validates |
|-----------|-----------|
| Happy path - latest extraction | Returns newest extraction for document |
| 404 - document not found | Missing document_id |
| 404 - no extraction | Document exists but no extraction |
| Pagination - correct page/size | Offset and limit work |
| Pagination - page beyond total | Returns empty items, not error |
| Empty list | total=0, items=[] |
| Ordering | Newest first (created_at DESC) |

**Test command**:
```bash
python -m pytest tests/test_api_extractions.py -v
```

## Status: ✅ Complete

All 9 tests pass. Total test suite: 122 tests passing.
