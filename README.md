# Contract Clause Extractor

A FastAPI service that extracts and structures key clauses from legal contracts using LLM APIs. Built with Temporal for durable workflow orchestration and MinIO for object storage.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Docker Compose Stack                              │
│                                                                              │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│  │   Client    │────▶│   FastAPI   │────▶│  Temporal   │                   │
│  └─────────────┘     │   :8000     │     │   :7233     │                   │
│                      └──────┬──────┘     └──────┬──────┘                   │
│                             │                   │                           │
│                             ▼                   ▼                           │
│                      ┌─────────────┐     ┌─────────────┐     ┌───────────┐ │
│                      │  PostgreSQL │     │   Worker    │────▶│  OpenAI   │ │
│                      │   :5432     │     │             │     │    API    │ │
│                      └─────────────┘     └──────┬──────┘     └───────────┘ │
│                                                 │                           │
│                                                 ▼                           │
│                                          ┌─────────────┐                   │
│                                          │    MinIO    │                   │
│                                          │ :9000/:9001 │                   │
│                                          └─────────────┘                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Request Flow

```
1. Client uploads PDF          ─────▶  FastAPI validates, stores in MinIO
                                              │
2. FastAPI starts workflow     ◀──────────────┘
         │
         ▼
3. Temporal schedules Worker   ─────▶  Worker fetches PDF from MinIO
                                              │
4. Worker extracts text        ◀──────────────┘
         │
         ▼
5. Worker calls OpenAI         ─────▶  OpenAI returns structured clauses
                                              │
6. Worker stores results       ◀──────────────┘
         │
         ▼
7. Client fetches extraction   ─────▶  FastAPI returns JSON response
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- OpenAI API key

### Run

```bash
# Clone and enter directory
git clone <repo-url>
cd charmelio

# Copy env and set API key
cp .env.example .env
# Edit .env and set OPENAI_API_KEY

# Start all services
make up

# Check services are healthy
make healthcheck
```

### Test the API

```bash
# Upload a contract
curl -X POST \
  -F "file=@sample_contracts/simple.pdf" \
  http://localhost:8000/api/extract

# Response: {"document_id": "abc-123", "filename": "simple.pdf", "status": "pending"}

# Wait ~30-60 seconds, then fetch results
curl http://localhost:8000/api/extractions/abc-123

# List all extractions
curl "http://localhost:8000/api/extractions?page=1&page_size=10"
```

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make install` | Install package locally (pip install -e .) |
| `make lint` | Run ruff linter |
| `make test` | Run tests |
| `make cov` | Run tests with coverage report |
| `make clean` | Remove cache files and coverage |
| `make up` | Start Docker services |
| `make down` | Stop Docker services |
| `make ps` | Show running containers |
| `make logs` | Follow all logs |
| `make logs-api` | Follow API logs only |
| `make restart` | Restart all services |
| `make healthcheck` | Check all services health |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/extract` | Upload PDF, start extraction |
| `GET` | `/api/extractions/{document_id}` | Get extraction results |
| `GET` | `/api/extractions` | List all extractions (paginated) |
| `GET` | `/health` | Liveness probe |
| `GET` | `/health/ready` | Readiness probe (checks DB, MinIO, Temporal) |

### POST /api/extract

**Request:**

```bash
curl -X POST -F "file=@contract.pdf" http://localhost:8000/api/extract
```

**Response (200):**

```json
{
  "document_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "filename": "contract.pdf",
  "status": "pending"
}
```

**Errors:**

- `400` - Not a PDF file
- `413` - File exceeds 25MB limit
- `503` - Extraction service unavailable

### GET /api/extractions/{document_id}

**Response (200):**

```json
{
  "extraction_id": "ext-789",
  "document_id": "abc-123",
  "filename": "contract.pdf",
  "status": "completed",
  "model_used": "gpt-4o-mini",
  "extraction_result": {
    "parties": {
      "party_one": "Acme Corporation",
      "party_two": "Beta Industries",
      "additional_parties": []
    },
    "dates": {
      "effective_date": "2025-01-01",
      "termination_date": "2026-01-01",
      "term_length": "12 months"
    },
    "clauses": {
      "governing_law": "State of California",
      "termination": "Either party may terminate with 30 days written notice",
      "confidentiality": "All information shared shall remain confidential...",
      "indemnification": "Each party shall indemnify the other...",
      "limitation_of_liability": "Neither party shall be liable for indirect damages...",
      "payment_terms": "Net 30 days from invoice date",
      "dispute_resolution": "Disputes shall be resolved through binding arbitration",
      "intellectual_property": "Work for hire provisions..."
    },
    "confidence": 0.92,
    "summary": "Master Services Agreement between Acme Corporation and Beta Industries"
  },
  "created_at": "2025-01-09T12:34:56Z"
}
```

**Errors:**

- `404` - Document not found
- `404` - No extraction found for document

### GET /api/extractions

**Query Parameters:**

- `page` (default: 1, min: 1)
- `page_size` (default: 10, min: 1, max: 100)

**Response (200):**

```json
{
  "items": [...],
  "total": 42,
  "page": 1,
  "page_size": 10
}
```

## Data Model

```
┌─────────────────────────────────┐
│           documents             │
├─────────────────────────────────┤
│ id            UUID (PK)         │
│ filename      VARCHAR(255)      │
│ content_type  VARCHAR(100)      │
│ file_size     INTEGER           │
│ page_count    INTEGER           │
│ raw_text      TEXT              │
│ status        ENUM              │◀─── pending │ processing │ completed │ failed
│ error_message TEXT              │
│ bucket        VARCHAR(63)       │◀─── "uploads"
│ object_key    VARCHAR(512)      │◀─── "{id}.pdf"
│ created_at    TIMESTAMP         │
│ updated_at    TIMESTAMP         │
└───────────────┬─────────────────┘
                │
                │ 1:N
                ▼
┌─────────────────────────────────┐
│          extractions            │
├─────────────────────────────────┤
│ id            UUID (PK)         │
│ document_id   UUID (FK)         │
│ model_used    VARCHAR(80)       │◀─── "gpt-4o-mini"
│ clauses       JSON              │◀─── Full extraction result
│ confidence    FLOAT             │
│ artifact_bucket VARCHAR(63)     │◀─── "extractions"
│ artifact_key  VARCHAR(512)      │◀─── "{doc_id}.json"
│ created_at    TIMESTAMP         │
└─────────────────────────────────┘

Index: (document_id, created_at) for fast latest extraction lookup
```

## Project Structure

```
charmelio/
├── app/
│   ├── main.py                 # FastAPI app creation, lifespan, router includes
│   ├── deps.py                 # Storage singleton
│   ├── core/
│   │   ├── config.py           # Settings (env vars)
│   │   └── logging.py          # Logging setup
│   ├── db/
│   │   ├── models.py           # SQLAlchemy models
│   │   └── session.py          # Database session (async + sync)
│   ├── routes/
│   │   ├── __init__.py         # Router exports
│   │   ├── documents.py        # POST /api/extract
│   │   ├── extractions.py      # GET /api/extractions endpoints
│   │   └── health.py           # Health check endpoints
│   ├── schemas/
│   │   ├── domain.py           # ExtractionResult (LLM output)
│   │   └── api.py              # API response models
│   ├── services/
│   │   ├── __init__.py         # Service exports
│   │   └── pdf_parser.py       # PDF text extraction
│   └── storage/
│       ├── contracts.py        # Storage interfaces
│       ├── factory.py          # Storage factory
│       └── minio_impl.py       # MinIO implementation
├── worker/
│   ├── activities.py           # Temporal activities
│   ├── workflows.py            # ExtractionWorkflow
│   ├── llm_extractor.py        # OpenAI adapter
│   └── run.py                  # Worker entrypoint
├── scripts/
│   ├── e2e_demo.py             # End-to-end demo script
│   └── entrypoint.sh           # Docker entrypoint (runs migrations)
├── tests/
│   ├── conftest.py             # Pytest fixtures
│   ├── test_pdf_parser.py
│   ├── test_llm_extractor.py
│   ├── test_activities.py
│   ├── test_workflows.py
│   ├── test_health.py
│   ├── test_extract.py
│   ├── test_api_extractions.py
│   ├── test_database.py
│   └── test_storage_minio.py
├── sample_contracts/           # Test PDFs
├── alembic/                    # DB migrations
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── pyproject.toml
└── README.md
```

## Implementation Notes

### API Behavior

- **GET /api/extractions/{document_id}** returns the **latest** extraction for that document (`ORDER BY created_at DESC LIMIT 1`). Multiple extractions can exist per document (re-extraction, model comparison).

- **Pagination** on list endpoint uses offset-based pagination with `page` (default: 1) and `page_size` (default: 10, max: 100).

### Storage Artifacts

| Bucket | Key Pattern | Content |
|--------|-------------|---------|
| `uploads` | `{document_id}.pdf` | Original PDF |
| `extractions` | `{document_id}.json` | Extraction result JSON |

We store object keys in the database, not presigned URLs. URLs are generated on-demand when needed.

### Text Truncation

MVP uses **truncation at 200k characters** (no chunking). For very long contracts, clauses near the end may be missed. The LLM processes a single prompt with the full (truncated) text.

### Raw Text Storage

We store `raw_text` in the `documents` table. This enables:
- Re-extraction with different prompts/models without re-parsing PDF
- Debugging extraction issues
- Future: retention policy and encryption at rest recommended for production

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Temporal for orchestration** | Durable workflows with automatic retries, observability via Web UI, clean separation of concerns. Handles LLM timeouts and rate limits gracefully. |
| **MinIO for blob storage** | Keeps large PDFs out of the database. S3-compatible API makes migration to AWS easy. |
| **PostgreSQL for metadata** | Production-ready, ACID compliant, supports concurrent writes. |
| **Sync Temporal activities** | Activities run in thread pool. Async adds complexity without benefit here. |
| **OpenAI Structured Outputs** | Guarantees valid JSON matching our schema. No brittle parsing. |
| **One extraction per LLM call** | Simpler than chunking. Works for contracts up to ~100 pages. |
| **Separate Document/Extraction tables** | Allows re-extraction, model comparison, audit history. |
| **Async SQLAlchemy for API** | Non-blocking database calls for FastAPI routes. |
| **Sync SQLAlchemy for Worker** | Temporal activities are sync, simpler implementation. |

## Tradeoffs

| Constraint | Impact | Future Solution |
|------------|--------|-----------------|
| No OCR | Scanned PDFs return empty text | Add Tesseract/OCRmyPDF activity |
| No auth | Anyone can upload | Add API key or OAuth |
| 200k char truncation | Very long contracts partially processed | Semantic chunking + merge |
| No webhooks | Clients must poll for results | Add webhook on completion |

## Design Dilemmas

These are common discussion points when evaluating the architecture:

### Chat Completions vs Responses API

| Option | Notes |
|--------|-------|
| **Completions** (current) | Works with `response_format.json_schema`, well-documented |
| **Responses** | OpenAI's recommended modern API, supports `store=False`, multi-modal extensibility |

**Decision:** Completions for MVP. Plan migration to Responses API for future features.

### Async vs Sync Activities

| Option | Notes |
|--------|-------|
| **Async** | Consistent with FastAPI patterns, but requires async-compatible libraries |
| **Sync** (current) | Simpler; worker `ThreadPoolExecutor` handles blocking I/O nicely |

**Decision:** Sync activities. pdfplumber and MinIO SDK are sync libraries; wrapping in async adds complexity without benefit.

### Truncation vs Chunking

| Option | Notes |
|--------|-------|
| **Truncation** (current) | Fast to ship; risk missing clauses near document end |
| **Chunking** | Higher recall, more complexity (split/merge/dedupe) |

**Decision:** Truncation for MVP. Add semantic chunking if documents regularly exceed 200k chars.

### PDF Safety

| Risk | Mitigation |
|------|------------|
| Malformed PDFs crash parsers | Catch exceptions, mark document as `failed` |
| Malicious PDFs | Future: add qpdf sanitization, ClamAV scanning |
| Resource exhaustion | Page limit (500), file size limit (25MB) |

**Decision:** MVP catches and marks failures. Add sanitizer for production deployment.

## Running Tests

```bash
# All tests
make test

# With coverage
make cov

# Specific module
PYTHONPATH=. pytest tests/test_pdf_parser.py -v

# Open coverage report
open htmlcov/index.html
```

## Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| FastAPI | http://localhost:8000 | Main API |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Temporal Web | http://localhost:8233 | Workflow visibility |
| MinIO Console | http://localhost:9001 | Storage browser |
| PostgreSQL | localhost:5442 | Database |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required) | OpenAI API key |
| `MODEL_NAME` | `gpt-4o-mini` | Model for extraction |
| `MAX_FILE_SIZE_MB` | `25` | Upload size limit |
| `DATABASE_URL` | `postgresql://...` | Database connection |
| `S3_ENDPOINT` | `http://minio:9000` | MinIO address |
| `S3_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `S3_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `S3_BUCKET_UPLOADS` | `uploads` | Upload bucket |
| `S3_BUCKET_EXTRACTIONS` | `extractions` | Results bucket |
| `TEMPORAL_ADDRESS` | `temporal:7233` | Temporal server |
| `TEMPORAL_NAMESPACE` | `default` | Temporal namespace |
| `WORKER_TASK_QUEUE` | `extraction-queue` | Task queue name |

## Demo

```bash
# 1. Upload
DOC_ID=$(curl -s -X POST -F "file=@sample_contracts/simple.pdf" \
  http://localhost:8000/api/extract | jq -r '.document_id')

echo "Document ID: $DOC_ID"

# 2. Poll until complete
while true; do
  RESP=$(curl -s http://localhost:8000/api/extractions/$DOC_ID)
  STATUS=$(echo $RESP | jq -r '.status // "pending"')
  echo "Status: $STATUS"
  [ "$STATUS" = "completed" ] && break
  [ "$STATUS" = "failed" ] && { echo "Failed!"; break; }
  sleep 5
done

# 3. View results
curl -s http://localhost:8000/api/extractions/$DOC_ID | jq '.extraction_result.clauses'
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `503` on POST /api/extract | Temporal not connected | Check `docker compose logs temporal` and `/health/ready` |
| Extraction stuck on "pending" | Worker not running or crashed | Check `docker compose logs worker` |
| Empty extraction result | PDF is scanned (image-only) | OCR not implemented (see Tradeoffs) |
| "No extraction found" | Processing still in progress | Wait and retry; check Temporal UI at :8233 |
| "File exceeds limit" | PDF > 25MB | Reduce file size or increase `MAX_FILE_SIZE_MB` |

## License

MIT
