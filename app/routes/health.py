"""Health check endpoints."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Liveness probe."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness_check(request: Request):
    """Readiness probe - checks DB, storage, Temporal."""
    checks = {}
    all_ok = True

    # Check database
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        all_ok = False

    # Check storage
    minio = request.app.state.minio
    if minio is not None:
        try:
            minio.bucket_exists(settings.S3_BUCKET_UPLOADS)
            checks["storage"] = "ok"
        except Exception as e:
            checks["storage"] = f"error: {e}"
            all_ok = False
    else:
        checks["storage"] = "not configured"
        all_ok = False

    # Check Temporal
    if getattr(request.app.state, "temporal", None) is not None:
        checks["temporal"] = "ok"
    else:
        checks["temporal"] = "not connected"
        all_ok = False

    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
    )
