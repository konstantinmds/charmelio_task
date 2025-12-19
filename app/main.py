"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from minio import Minio
from temporalio.client import Client as TemporalClient

from app.core.config import settings
from app.core.logging import setup_logging
from app.db import init_db
from app.routes import documents_router, extractions_router, health_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup, cleanup on shutdown."""
    setup_logging()

    # Initialize database tables
    await init_db()

    # MinIO client
    if settings.S3_ENDPOINT and settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY:
        app.state.minio = Minio(
            settings.S3_ENDPOINT.replace("http://", "").replace("https://", ""),
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            secure=settings.S3_ENDPOINT.startswith("https"),
        )
    else:
        app.state.minio = None

    # Temporal client - tolerate failure
    try:
        app.state.temporal = await TemporalClient.connect(
            settings.TEMPORAL_ADDRESS,
            namespace=settings.TEMPORAL_NAMESPACE,
        )
        logger.info("Connected to Temporal at %s", settings.TEMPORAL_ADDRESS)
    except Exception as e:
        logger.warning("Failed to connect to Temporal: %s", e)
        app.state.temporal = None

    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Register routers
app.include_router(health_router)
app.include_router(documents_router)
app.include_router(extractions_router)
