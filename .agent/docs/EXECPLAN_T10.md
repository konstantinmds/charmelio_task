# T-10 API — `POST /api/extract`

## Purpose

Expose `POST /api/extract` endpoint that accepts a PDF upload, persists a `Document` record, uploads the PDF to MinIO, and starts the Temporal extraction workflow. Returns a pending response so clients know the job was accepted.

## Progress

- [x] Implement `/api/extract` route in `app/main.py`
- [x] Validate content-type and file size
- [x] Create Document record with pending status
- [x] Upload PDF to MinIO storage
- [x] Start Temporal ExtractionWorkflow
- [x] Add unit tests (happy path + error branches)

## Decision Log

| Decision | Rationale |
|----------|-----------|
| No HMAC auth for MVP | Internal service, add auth when exposing externally |
| Validate `application/pdf` content-type | Prevent non-PDF uploads early |
| Enforce `MAX_FILE_SIZE_MB` limit | Protect storage and processing capacity |
| Return 503 when Temporal unavailable | Fail-fast, don't create orphan records |
| Document status starts as `pending` | Workflow updates to `processing`/`completed`/`failed` |
| Storage key: `{document_id}.pdf` | Deterministic, easy to correlate |
| Workflow ID: `extraction-{document_id}` | Enables lookup and prevents duplicates |

## Implementation

### Endpoint: `POST /api/extract`

**Location**: `app/main.py:108-171`

**Request**:
- Multipart form with `file` field (PDF)

**Response** (200):
```json
{
  "document_id": "uuid",
  "filename": "contract.pdf",
  "status": "pending"
}
```

**Errors**:
| Code | Condition |
|------|-----------|
| 400 | Non-PDF content-type |
| 413 | File exceeds `MAX_FILE_SIZE_MB` |
| 503 | Temporal client not connected |

### Flow

```
1. Validate content_type == "application/pdf"
2. Read file, check size <= MAX_FILE_SIZE_MB
3. Check Temporal client available (fail-fast)
4. Create Document record (status=pending)
5. Commit to database
6. Upload to MinIO: {bucket}/{document_id}.pdf
7. Start ExtractionWorkflow with document_id
8. Return {document_id, filename, status: "pending"}
```

## Tests

**Location**: `tests/test_extract.py`

| Test Case | Validates |
|-----------|-----------|
| `test_extract_happy_path` | 200 response, document_id returned |
| `test_extract_non_pdf_returns_400` | Content-type validation |
| `test_extract_oversize_file_returns_413` | Size limit enforcement |
| `test_extract_temporal_unavailable_returns_503` | Fail-fast on missing Temporal |
| `test_extract_creates_document_with_correct_fields` | DB record correctness |
| `test_extract_starts_workflow_with_correct_params` | Workflow ID and task queue |

**Run tests**:
```bash
python -m pytest tests/test_extract.py -v
```

## Dependencies

- `python-multipart` - FastAPI file upload support
- `app/db/models.py` - Document, DocumentStatus
- `app/db/session.py` - get_db (async session)
- `app/deps.py` - get_storage (MinIO wrapper)
- `worker/workflows.py` - ExtractionWorkflow

## Configuration

| Setting | Purpose |
|---------|---------|
| `MAX_FILE_SIZE_MB` | Upload size limit (default: 10) |
| `S3_BUCKET_UPLOADS` | MinIO bucket for PDFs |
| `WORKER_TASK_QUEUE` | Temporal task queue name |

## Future Enhancements (Post-MVP)

- [ ] HMAC authentication when exposing externally
- [ ] Idempotency key header for client retries
- [ ] Rate limiting per client
- [ ] Async storage upload with `asyncio.to_thread`

## Status: ✅ Complete

All acceptance criteria met. Tests pass (6/6).
