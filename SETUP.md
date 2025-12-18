# Charmelio Setup Guide

## T-01: Repo Scaffold & Tooling ✅

### Directory Structure

```
charmelio_clean/
├── app/              # FastAPI application code
├── worker/           # Temporal worker activities and workflows
├── tests/            # Test files (pytest)
├── sample_contracts/ # Sample PDF files for testing
├── tools/            # Utility scripts (e.g., gen_pdfs.py)
├── pyproject.toml    # Project configuration
├── Makefile          # Build and test commands
├── requirements.txt  # Dependencies
└── .pre-commit-config.yaml  # Pre-commit hooks
```

### Installation

```bash
# Install dependencies
make install

# Or manually
pip install -e .
```

### Usage

```bash
# Run tests
make test

# Run tests with coverage
make cov

# Run linter
make lint

# Clean generated files
make clean
```

### Pre-commit Hooks

Install pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

### Configuration

- **pytest**: Configured in `pyproject.toml`
  - Coverage threshold: 95%
  - Coverage reports: terminal + HTML (`htmlcov/`)
  - Test paths: `tests/`

- **ruff**: Configured in `pyproject.toml`
  - Line length: 120
  - Python version: 3.11+

### What's Included

- **Minimal FastAPI app** (`app/main.py`) with `/health` endpoint
- **Basic test** (`tests/test_health.py`) to verify setup
- Coverage configured for `app/` module (worker will be added in T-07)

### Acceptance Criteria ✅

- [x] `pytest` runs successfully
- [x] `make cov` generates HTML coverage report
- [x] `ruff` passes (configuration ready)
- [x] Directory structure created
- [x] Makefile with all targets
- [x] Pre-commit hooks configured

### Testing

```bash
# Should now pass with >95% coverage
make test

# Generate and view coverage report
make cov
```

### Next Steps

✅ Proceed to **T-02: Docker Compose** setup.

---

## T-02: Docker Compose (API, Worker, Temporal, MinIO, Postgres) ✅

### Services Included

1. **postgres** - PostgreSQL 15 database (port 5442 - avoids conflict with local postgres)
2. **minio** - S3-compatible object storage (ports 9000, 9001)
3. **temporal** - Workflow orchestration server (port 7233)
4. **temporal-ui** - Temporal Web UI (port 8233)
5. **api** - FastAPI application (port 8000)
6. **worker** - Temporal worker for extraction workflows

### Docker Image Optimization ✅

Our Dockerfile uses **multi-stage build** for optimal image size:
- **Before:** 773MB per image
- **After:** ~500MB per image
- **Savings:** 273MB (35% reduction)

The optimization removes build tools (gcc) and test dependencies from the production image while maintaining full functionality. See `IMAGE_SIZE.md` and `OPTIMIZATION.md` for details.

### Quick Start

```bash
# Copy environment variables
cp .env.example .env

# Edit .env and add your OPENAI_API_KEY
# vim .env

# Start all services
make up

# Check service status
make ps

# View logs
make logs

# Check health of all services
make healthcheck
```

### Service URLs

- **API**: http://localhost:8000
- **API Health**: http://localhost:8000/health
- **Temporal UI**: http://localhost:8233
- **MinIO Console**: http://localhost:9001 (login: minioadmin/minioadmin)
- **MinIO API**: http://localhost:9000

### Docker Commands

```bash
make up          # Start all services
make down        # Stop all services
make ps          # Show service status
make logs        # Follow all logs
make logs-api    # Follow API logs only
make logs-worker # Follow worker logs only
make restart     # Restart all services
make healthcheck # Check service health
```

### Service Dependencies

```
API & Worker depend on:
  ├── postgres (healthy)
  ├── minio (healthy)
  └── temporal (healthy)
      └── postgres (healthy)
```

### Volumes

- `pg_data` - PostgreSQL data
- `minio_data` - MinIO object storage data

### Environment Variables

All configured in `.env` (see `.env.example`):

- **Database**: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
- **MinIO**: MINIO_ROOT_USER, MINIO_ROOT_PASSWORD
- **Temporal**: TEMPORAL_ADDRESS, WORKER_TASK_QUEUE
- **OpenAI**: OPENAI_API_KEY, MODEL_NAME
- **App**: MAX_FILE_SIZE_MB

### Acceptance Criteria ✅

- [x] `docker compose up` brings all services healthy
- [x] Temporal Web accessible at http://localhost:8233
- [x] MinIO console accessible at http://localhost:9001
- [x] Container healthchecks configured
- [x] Smoke test: `curl http://localhost:8000/health` returns `{"status":"ok"}`

**Estimated time:** 0.75h ✅

### Worker Infrastructure ✅

The worker service is configured and will start successfully, although actual workflows and activities will be implemented in later tickets:

**Created:**
- `worker/run.py` - Worker entry point (polls Temporal for tasks)
- `worker/config.py` - Environment-based configuration
- `worker/workflows.py` - Placeholder for T-08 (Temporal Workflow)
- `worker/activities.py` - Placeholder for T-07 (Temporal Activities)

**Status:**
- ✅ Worker container starts without errors
- ✅ Connects to Temporal successfully
- ⏳ No workflows/activities registered yet (T-07, T-08)

### Troubleshooting

**Worker error: "No module named worker.run"**
- ✅ Fixed! Created `worker/run.py` with proper module structure

**Worker exits immediately**
- Normal if no workflows are registered yet
- Will run continuously once workflows are added in T-07/T-08

### Next Steps

Proceed to **T-03: Database Layer & Context Manager**.
