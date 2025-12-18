"""Factory for building storage instances from environment configuration."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from minio import Minio

from app.storage.minio_impl import MinioStorage


def _normalize_endpoint(endpoint: str) -> tuple[str, bool]:
    """Extract host:port from endpoint URL and determine if secure (https).

    Returns:
        Tuple of (host:port, secure_flag)
    """
    parsed = urlparse(endpoint)
    secure = parsed.scheme == "https"
    host = parsed.netloc or parsed.path.rstrip("/")
    return host, secure


def build_storage() -> MinioStorage:
    """Build MinioStorage from environment variables and ensure buckets exist.

    Environment variables:
        S3_ENDPOINT: Full URL to MinIO/S3 endpoint (e.g., http://localhost:9000)
        S3_ACCESS_KEY: Access key for authentication
        S3_SECRET_KEY: Secret key for authentication
        S3_BUCKET_UPLOADS: Name of uploads bucket (default: uploads)
        S3_BUCKET_EXTRACTIONS: Name of extractions bucket (default: extractions)
    """
    endpoint = os.environ.get("S3_ENDPOINT", "http://localhost:9000")
    access_key = os.environ.get("S3_ACCESS_KEY", "minioadmin")
    secret_key = os.environ.get("S3_SECRET_KEY", "minioadmin")
    uploads_bucket = os.environ.get("S3_BUCKET_UPLOADS", "uploads")
    extractions_bucket = os.environ.get("S3_BUCKET_EXTRACTIONS", "extractions")

    host, secure = _normalize_endpoint(endpoint)
    client = Minio(host, access_key=access_key, secret_key=secret_key, secure=secure)
    storage = MinioStorage(client)

    storage.ensure_bucket(uploads_bucket)
    storage.ensure_bucket(extractions_bucket)

    return storage


__all__ = ["build_storage"]
