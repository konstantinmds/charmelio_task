# Charmelio Architecture

## System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                         USER                                  │
│                  (uploads PDF contract)                       │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         │ HTTP POST /api/extract
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    API SERVICE (FastAPI)                     │
│                      Port 8000                               │
│                                                              │
│  1. Upload PDF to MinIO (uploads bucket)                    │
│  2. Create Document record in Postgres (status=pending)     │
│  3. Start ExtractionWorkflow in Temporal                    │
│  4. Return immediately: {"id": "abc", "status": "pending"}  │
└──┬──────────────────────────────────────────────────────┬───┘
   │                                                       │
   │ Stores PDF                                   Starts  │
   │                                            workflow   │
   ▼                                                       ▼
┌──────────────┐                              ┌────────────────┐
│    MinIO     │                              │   Temporal     │
│  Port 9000   │                              │   Port 7233    │
│              │                              │                │
│ uploads/     │                              │ Orchestrates   │
│ extractions/ │                              │ workflows      │
└──────────────┘                              └────┬───────────┘
   ▲                                                │
   │                                                │ Schedules
   │                                                │ activities
   │                                                ▼
   │                              ┌──────────────────────────────┐
   │                              │   WORKER SERVICE             │
   │                              │   (Background Process)       │
   │                              │                              │
   │                              │  Polls for work from         │
   │                              │  "extraction-queue"          │
   │                              │                              │
   │                              │  Executes 3 activities:      │
   │                              │                              │
   │  Downloads PDF               │  1. parse_pdf()             │
   │◄─────────────────────────────┤     - Download PDF          │
   │                              │     - Extract text          │
   │                              │     - Update DB             │
   │                              │                              │
   │                              │  2. llm_extract()           │
   │                              │     - Call OpenAI           │
   │                              │     - Get clauses           │
   │                              │                              │
   │  Stores results              │  3. store_results()         │
   ├──────────────────────────────►     - Save to MinIO         │
   │                              │     - Update DB             │
   │                              │     - Mark completed        │
   │                              └──────┬───────────────────────┘
   │                                     │
   │                                     │ Updates
   │                                     ▼
   │                              ┌──────────────┐
   │                              │  PostgreSQL  │
   │                              │  Port 5442   │
   │                              │              │
   │                              │ documents    │
   │                              │ extractions  │
   │                              └──────────────┘
   │
   └─────────────────┐
                     │
                     ▼
         ┌──────────────────────┐
         │  User polls status   │
         │  GET /api/extractions/abc │
         │                      │
         │  {"status": "completed", │
         │   "clauses": {...}}  │
         └──────────────────────┘
```

## Component Responsibilities

### API Service (FastAPI)
**Purpose:** Handle HTTP requests quickly
**Runs:** `uvicorn app.main:app`
**Port:** 8000

**Does:**
- Accept PDF uploads
- Validate file size/type
- Store PDFs in MinIO
- Create database records
- Start Temporal workflows
- Return status to users
- Serve extraction results

**Does NOT do:**
- Parse PDFs (worker does this)
- Call OpenAI (worker does this)
- Heavy computation (worker does this)

### Worker Service (Background Process)
**Purpose:** Execute time-consuming tasks
**Runs:** `python -m worker.run`
**Port:** None (background service)

**Does:**
- Poll Temporal for tasks
- Parse PDFs (10-30 sec)
- Call OpenAI API (30-60 sec)
- Store extraction results
- Update database status
- Retry on failures

**Does NOT do:**
- Handle HTTP requests (API does this)
- Interact with users (API does this)

### Temporal (Orchestration)
**Purpose:** Manage workflow state and task scheduling
**Image:** `temporalio/auto-setup:1.25.0`
**Ports:** 7233 (server), 8233 (UI)

**Does:**
- Store workflow state
- Schedule activities on workers
- Handle retries automatically
- Provide visibility via Web UI
- Guarantee exactly-once execution

### MinIO (Object Storage)
**Purpose:** Store PDFs and extraction results
**Image:** `minio/minio:latest`
**Ports:** 9000 (API), 9001 (Console)

**Buckets:**
- `uploads/` - Original PDF files
- `extractions/` - JSON extraction results

### PostgreSQL (Database)
**Purpose:** Store structured metadata
**Image:** `postgres:15-alpine`
**Port:** 5442

**Tables:**
- `documents` - PDF metadata, status
- `extractions` - Clause extraction data

## Request Flow Example

### 1. User Uploads PDF

```http
POST /api/extract HTTP/1.1
Host: localhost:8000
Content-Type: multipart/form-data

[PDF file data]
```

**API Response (immediate):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "filename": "contract.pdf",
  "file_size": 125000,
  "created_at": "2025-01-15T10:30:00Z"
}
```

### 2. Workflow Executes (Background)

**Timeline:**
```
T+0s:   Workflow started
T+1s:   Activity: parse_pdf started
T+15s:  Activity: parse_pdf completed (text extracted)
T+15s:  Activity: llm_extract started
T+75s:  Activity: llm_extract completed (clauses extracted)
T+75s:  Activity: store_results started
T+77s:  Activity: store_results completed
T+77s:  Workflow completed
```

### 3. User Checks Status

```http
GET /api/extractions/550e8400-e29b-41d4-a716-446655440000
```

**Response:**
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "filename": "contract.pdf",
  "page_count": 12,
  "extraction": {
    "parties": {
      "party_one": "Acme Corp",
      "party_two": "Beta Inc"
    },
    "dates": {
      "effective_date": "2025-01-01",
      "termination_date": "2026-01-01"
    },
    "clauses": {
      "governing_law": "California",
      "termination": "Either party may terminate with 30 days notice"
    }
  }
}
```

## Scalability

### Vertical Scaling
```yaml
# Give more resources to specific services
services:
  worker:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

### Horizontal Scaling
```bash
# Run multiple worker instances
docker compose up -d --scale worker=5

# Each worker polls the same queue
# Temporal distributes work among them
```

### Load Distribution
```
Single Worker:        Multiple Workers:

API → Temporal       API → Temporal
        ↓                    ↓
      Worker              Worker 1 ←┐
        ↓                   ↓        │
   (processes            (task A)   │
    all tasks)                      ├─ Temporal distributes
                          Worker 2 ←┤
                            ↓        │
                         (task B)   │
                                    │
                          Worker 3 ←┘
                            ↓
                         (task C)
```

## Data Flow

### Upload Flow
```
User → API → MinIO (PDF stored)
         ↓
      Postgres (document record created)
         ↓
     Temporal (workflow started)
```

### Processing Flow
```
Temporal → Worker → MinIO (get PDF)
             ↓
         PDF Parser (extract text)
             ↓
         OpenAI API (extract clauses)
             ↓
      MinIO (store results JSON)
             ↓
      Postgres (update status)
```

### Retrieval Flow
```
User → API → Postgres (get document + extraction)
         ↓
      Response (JSON)
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| API Framework | FastAPI | HTTP endpoints |
| Worker Runtime | Python 3.11 | Background processing |
| Orchestration | Temporal | Workflow management |
| Database | PostgreSQL 15 | Structured data |
| Object Storage | MinIO | File storage |
| PDF Parsing | pdfplumber | Text extraction |
| LLM | OpenAI API | Clause extraction |
| Container | Docker | Deployment |

## Monitoring

### Health Checks
```bash
curl http://localhost:8000/health      # API
curl http://localhost:9000/minio/health/live  # MinIO
docker compose exec postgres pg_isready       # Postgres
curl http://localhost:8233/               # Temporal UI
```

### Logs
```bash
make logs-api       # API requests/responses
make logs-worker    # Activity execution
make logs-temporal  # Workflow orchestration
make logs-postgres  # Database queries
```

### Temporal UI
http://localhost:8233
- View running workflows
- See workflow history
- Monitor activity execution times
- Debug failures

## Security Considerations

### Authentication (Future)
- API key validation
- User authentication
- Rate limiting

### Data Protection
- PDFs stored in MinIO (can encrypt)
- Database credentials in `.env`
- OpenAI API key secured

### Network
- Services isolated in Docker network
- Only necessary ports exposed
- TLS/SSL in production

## Summary

**Charmelio** is a microservices architecture where:
- **API** handles user requests quickly
- **Worker** does heavy processing in background
- **Temporal** orchestrates the workflow
- **MinIO** stores files
- **PostgreSQL** stores metadata

This separation allows for:
- Fast response times
- Independent scaling
- Better reliability
- Clear separation of concerns
