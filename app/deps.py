"""Shared dependencies for FastAPI routes and workers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.storage.minio_impl import MinioStorage

_storage: "MinioStorage | None" = None


def get_storage() -> "MinioStorage":
    """Get or lazily initialize the storage singleton.

    Lazy initialization avoids failures at import time when MinIO is unavailable.
    """
    global _storage
    if _storage is None:
        from app.storage.factory import build_storage

        _storage = build_storage()
    return _storage


__all__ = ["get_storage"]
