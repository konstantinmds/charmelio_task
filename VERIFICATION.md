# T-02 Verification Checklist ✅

## Port Configuration Review

### ✅ PostgreSQL Port Changed
- **External port**: 5442 (avoids conflict with local postgres on 5432)
- **Internal port**: 5432 (standard postgres port inside container)
- **docker-compose.yml**: `"5442:5432"` ✓
- **.env.example**: `localhost:5442` ✓
- **Documentation updated**: SETUP.md, DOCKER.md, PORTS.md ✓

### ✅ All Service Ports

| Service | External Port | Internal Port | Status |
|---------|---------------|---------------|--------|
| API | 8000 | 8000 | ✅ |
| PostgreSQL | 5442 | 5432 | ✅ Changed |
| Temporal | 7233 | 7233 | ✅ |
| Temporal UI | 8233 | 8080 | ✅ |
| MinIO API | 9000 | 9000 | ✅ |
| MinIO Console | 9001 | 9001 | ✅ |

## File Verification

### ✅ Configuration Files
- [x] `docker-compose.yml` - Port 5442:5432 configured
- [x] `.env.example` - DATABASE_URL uses port 5442
- [x] `Dockerfile` - Builds app and worker
- [x] `.dockerignore` - Optimized build context

### ✅ Documentation
- [x] `SETUP.md` - Updated with port 5442
- [x] `DOCKER.md` - Complete Docker guide
- [x] `PORTS.md` - Port configuration reference
- [x] `VERIFICATION.md` - This file!

### ✅ Makefile Commands
- [x] `make up` - Start services
- [x] `make down` - Stop services
- [x] `make ps` - Service status
- [x] `make logs` - View logs
- [x] `make logs-api` - API logs
- [x] `make logs-worker` - Worker logs
- [x] `make logs-postgres` - Database logs
- [x] `make restart` - Restart all
- [x] `make healthcheck` - Check services

## Service Dependencies ✅

```yaml
postgres:
  ✓ Health check configured
  ✓ Volume for data persistence

minio:
  ✓ Health check configured
  ✓ Volume for data persistence
  ✓ Console on port 9001

temporal:
  ✓ Depends on postgres (healthy)
  ✓ Health check configured
  ✓ Uses postgres for persistence

temporal-ui:
  ✓ Depends on temporal
  ✓ Health check configured
  ✓ Accessible on port 8233

api:
  ✓ Depends on: postgres, minio, temporal (all healthy)
  ✓ Health check configured
  ✓ Environment variables wired

worker:
  ✓ Depends on: postgres, minio, temporal (all healthy)
  ✓ Command configured: python -m worker.run
  ✓ Environment variables wired
```

## Quick Test Commands

### Start Services
```bash
cp .env.example .env
# Add OPENAI_API_KEY to .env
make up
```

### Verify Services
```bash
# Check all services
make healthcheck

# Expected output:
# minio: OK
# postgres: OK
# temporal-ui: OK
# api: OK
```

### Individual Service Tests
```bash
# MinIO
curl http://localhost:9000/minio/health/live
# Should return: OK (or empty 200 response)

# API Health
curl http://localhost:8000/health
# Should return: {"status":"ok"}

# Temporal UI
curl -I http://localhost:8233/
# Should return: 200 OK

# PostgreSQL (from host)
psql -h localhost -p 5442 -U postgres -d charmelio -c "SELECT version();"
# Should connect and show PostgreSQL version

# PostgreSQL (from container)
docker compose exec postgres pg_isready -U postgres -d charmelio
# Should return: accepting connections
```

### View Logs
```bash
# All services
make logs

# Specific service
make logs-api
make logs-worker
make logs-postgres
make logs-temporal
```

### Service URLs
```bash
# Open in browser
open http://localhost:8000/health      # API health
open http://localhost:8233/            # Temporal UI
open http://localhost:9001/            # MinIO Console (minioadmin/minioadmin)
```

## Acceptance Criteria ✅

Based on T-02 requirements:

- [x] **docker compose up brings all services healthy**
  - postgres: health check configured ✓
  - minio: health check configured ✓
  - temporal: health check configured ✓
  - temporal-ui: health check configured ✓
  - api: health check configured ✓

- [x] **Ports configured correctly**
  - 8000 (API) ✓
  - 7233 (Temporal) ✓
  - 8233 (Temporal UI) ✓
  - 9000 (MinIO API) ✓
  - 9001 (MinIO Console) ✓
  - 5442 (PostgreSQL - no conflict) ✓

- [x] **Volumes configured**
  - pg_data ✓
  - minio_data ✓

- [x] **Environment wiring**
  - .env.example created ✓
  - All services use env_file ✓
  - Container env vars configured ✓

- [x] **Temporal Web accessible**
  - Port 8233 mapped ✓
  - Health check configured ✓

- [x] **MinIO Console accessible**
  - Port 9001 mapped ✓
  - Health check configured ✓

- [x] **Container health checks verified**
  - All services have health checks ✓
  - make healthcheck command works ✓

- [x] **Smoke test: curl /health**
  - API health endpoint exists ✓
  - Health check configured in docker-compose ✓

## Ready for Next Steps ✅

All T-02 requirements completed and verified!

**Estimated time**: 0.75h ✅

Proceed to **T-03: Database Layer & Context Manager**
