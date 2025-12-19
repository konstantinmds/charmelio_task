"""API routes package."""

from app.routes.documents import router as documents_router
from app.routes.extractions import router as extractions_router
from app.routes.health import router as health_router

__all__ = ["documents_router", "extractions_router", "health_router"]
