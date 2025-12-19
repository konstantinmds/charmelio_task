# Multi-stage build for optimal image size

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

# Python environment best practices
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Install only runtime dependencies (curl for healthchecks)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code and migrations
COPY pyproject.toml ./pyproject.toml
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app
COPY worker ./worker
COPY scripts/entrypoint.sh ./entrypoint.sh

# Copy test assets (needed for e2e demo, can remove for pure production)
COPY sample_contracts ./sample_contracts

# Set ownership and switch to non-root user
RUN chown -R appuser:appgroup /app
USER appuser

# Expose API port
EXPOSE 8000

# Entrypoint runs migrations, then executes CMD
ENTRYPOINT ["./entrypoint.sh"]

# Default command with production settings
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
