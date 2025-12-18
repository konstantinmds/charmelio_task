# 

## Background

A lean MVP to demo contract clause extraction in a single afternoon: one FastAPI service handles PDF upload, text extraction, OpenAI-based clause detection (structured JSON), Postgres storage, and retrieval APIs. Includes **Temporal** for orchestration and **MinIO** for object storage, all runnable locally via Docker Compose.

## Requirements

### Must Have

* Single binary/service (FastAPI) with synchronous processing.
* Accept PDF (≤ 25 MB), extract text, call **OpenAI Responses API** with **Structured Outputs** to produce JSON.
* Store raw text + extraction in SQLite; expose endpoints to fetch one or list many.
* Minimal config via env; Dockerized; health endpoint.

### Should Have

* Basic pagination for list endpoint; simple error handling and validation.
* Unit tests for parser and API happy path.

### Won’t Have (MVP)

* OCR for scanned PDFs, multi-tenant auth.


### Architecture Overview (Extended: Temporal + MinIO)

```plantuml
@startuml
skinparam componentStyle rectangle
actor Client as C
rectangle "FastAPI Service" as API {
  [POST /api/extract]
  [GET /api/extractions/{document_id}]
  [GET /api/extractions]
  [GET /health]
}
component "pdfplumber" as PDF
component "OpenAI Responses
(Structured Outputs)" as OAI
component "Temporal Server" as Temporal
component "Worker (Activities)" as Worker
cloud "MinIO (S3-compatible)" as MinIO
DATABASE "SQLite" as DB

C --> API
API --> MinIO : PUT uploads/<doc>.pdf
API --> DB : INSERT document
API --> Temporal : start ExtractionWorkflow(docId)
Temporal --> Worker : schedule activities
Worker --> MinIO : GET uploads/<doc>.pdf
Worker --> PDF : Extract text
Worker --> OAI : Extract clauses (JSON Schema)
Worker --> MinIO : PUT extractions/<doc>.json
Worker --> DB : UPSERT extraction + UPDATE doc status
API --> DB : read results for GETs
@enduml
```

### Buckets & Paths

* `uploads/<document_id>.pdf`
* `extractions/<document_id>.json`

### Development Approach: Small, Testable Chunks

Each chunk ships in ≤ 60–90 minutes with full tests and coverage ≥ 90% (line/branch). Merge only when green.

1. **Foundations** — project scaffold, settings, health route.
2. **DB Layer** — SQLAlchemy models + CRUD helpers (no endpoints yet).
3. **PDF Parser** — pure function `extract_text_and_pages` with unit tests and fixtures.
4. **LLM Adapter** — OpenAI client wrapper with strict schema + mocked tests.
5. **POST /api/extract** — endpoint using parser + adapter; tests incl. size/type validation.
6. **GET endpoints** — retrieval + pagination, including DB queries.
7. **Error/Observability** — exception mapping, timing metrics, logging.
8. **Docs & Demo** — README, sample scripts.

Each step: commit → run `make test` → inspect `htmlcov/` → PR.

### Tooling & Commands

* **pytest** + **pytest-cov** with **coverage fail-under = 95%** (HTML).
* **pytest-asyncio** for async activity tests, **pytest-docker** (optional) for spinning up Temporal/MinIO.
* **unittest.mock** /**pytest-mock** to isolate OpenAI + MinIO.
