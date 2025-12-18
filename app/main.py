"""FastAPI application entry point with shared resources."""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from minio import Minio

from app.core.config import settings
from app.core.logging import setup_logging
from app.db import SessionLocal, init_db
from app.db.migrations import run_migrations


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize core resources (logging, DB, clients) on startup and clean up on shutdown.

    Mirrors the accounting_dare pattern: we prepare a DB session factory, HTTP client,
    and optional MinIO client for background tasks or dependency injection.
    """
    setup_logging()
    # Prefer migrations; fallback to create_all if migrations fail.
    try:
        run_migrations(settings.DATABASE_URL)
    except Exception:
        init_db()

    app.state.settings = settings
    app.state.db_session = SessionLocal
    app.state.http = httpx.AsyncClient(timeout=30)

    # MinIO client is optional; only initialize when credentials are present.
    if settings.S3_ENDPOINT and settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY:
        app.state.minio = Minio(
            settings.S3_ENDPOINT.replace("http://", "").replace("https://", ""),
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            secure=settings.S3_ENDPOINT.startswith("https"),
        )
    else:
        app.state.minio = None

    try:
        yield
    finally:
        await app.state.http.aclose()


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
