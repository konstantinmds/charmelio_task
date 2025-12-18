# Multi-stage build for optimal image size (~500MB vs 773MB)

# Build stage - install dependencies with build tools
FROM python:3.11-slim AS builder
WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and extract production dependencies
COPY pyproject.toml ./
RUN python - <<'PY'
from pathlib import Path
from tomllib import load

# Only production dependencies (not dev/test)
deps = load(open('pyproject.toml', 'rb'))['project']['dependencies']
Path('requirements.txt').write_text('\n'.join(deps))
PY

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage - minimal image with only what's needed
FROM python:3.11-slim
WORKDIR /app

# Install only runtime dependencies (curl for healthchecks)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder (no gcc, no build tools!)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code, metadata, and migrations (needed for tests and alembic)
COPY pyproject.toml ./pyproject.toml
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app
COPY worker ./worker
COPY tests ./tests
COPY sample_contracts ./sample_contracts

# Expose API port
EXPOSE 8000

# Default command (can be overridden for worker)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
