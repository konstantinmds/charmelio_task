# Port Configuration

## Overview

This document explains the port mappings for all services to avoid conflicts with local services.

## Port Mappings

### External Ports (Host → Container)

| Service | Host Port | Container Port | URL | Notes |
|---------|-----------|----------------|-----|-------|
| API | 8000 | 8000 | http://localhost:8000 | FastAPI application |
| Temporal Server | 7233 | 7233 | - | gRPC endpoint |
| Temporal UI | 8233 | 8080 | http://localhost:8233 | Web interface |
| MinIO API | 9000 | 9000 | http://localhost:9000 | S3-compatible API |
| MinIO Console | 9001 | 9001 | http://localhost:9001 | Web interface |
| **PostgreSQL** | **5442** | **5432** | - | **Changed to avoid local postgres conflict** |

## Database Connection Strings

### From Host Machine
When connecting from your local machine (e.g., using psql, DBeaver, etc.):
```
postgresql://postgres:postgres@localhost:5442/charmelio
```

### From Docker Containers
When services inside Docker connect to postgres (internal):
```
postgresql://postgres:postgres@postgres:5432/charmelio
```

### Environment Variables

In `.env` file:
```bash
# For local development/connections from host
DATABASE_URL=postgresql://postgres:postgres@localhost:5442/charmelio
```

In `docker-compose.yml`:
```yaml
# For API and Worker containers (internal)
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
```

## Why Different Ports?

**PostgreSQL uses port 5442 externally** because:
- Port 5432 is commonly used by local PostgreSQL installations
- Mapping to 5442 avoids port conflicts
- Containers communicate internally via `postgres:5432` (Docker network)
- Host connects via `localhost:5442` (port forwarding)

## Checking Connections

### From Host Machine
```bash
# Using psql
psql -h localhost -p 5442 -U postgres -d charmelio

# Health check via docker
docker compose exec postgres pg_isready -U postgres -d charmelio
```

### Testing All Services
```bash
make healthcheck
```

## Common Issues

### "Port 5432 already in use"
✅ **Fixed!** We use port 5442 externally to avoid this.

### "Connection refused on localhost:5432"
Make sure you're using port **5442** when connecting from your local machine:
```bash
# Wrong
psql -h localhost -p 5432 -U postgres -d charmelio

# Correct
psql -h localhost -p 5442 -U postgres -d charmelio
```

### Database connection from containers
Containers should use `postgres:5432` (not localhost):
```python
# Correct (in container)
DATABASE_URL = "postgresql://postgres:postgres@postgres:5432/charmelio"

# Wrong (will fail in container)
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/charmelio"
```

## Reference Architecture

```
┌─────────────────────────────────────────────────┐
│                  Host Machine                    │
│                                                  │
│  postgres:5432 ← Your local PostgreSQL          │
│                                                  │
│  localhost:5442 ↓ (Docker port forward)         │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────┐
│              Docker Network                      │
│                                                  │
│  postgres:5432 ← Container PostgreSQL            │
│                                                  │
│  API → postgres:5432 (internal connection)      │
│  Worker → postgres:5432 (internal connection)   │
└──────────────────────────────────────────────────┘
```
