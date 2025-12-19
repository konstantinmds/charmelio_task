"""MinIO-backed implementation of the storage interfaces."""

from __future__ import annotations

import io
from typing import Mapping

from minio import Minio
from minio.error import S3Error

from app.storage.contracts import ObjectStorage, Presigner, StorageError


def _wrap_error(op: str, bucket: str | None, key: str | None, exc: Exception) -> StorageError:
    return StorageError(op=op, bucket=bucket, key=key, message=str(exc))


class MinioStorage(ObjectStorage, Presigner):
    """Object storage abstraction backed by MinIO SDK."""

    def __init__(self, client: Minio):
        self._client = client

    # --------------------
    # ObjectStorage methods
    # --------------------
    def put_bytes(
        self,
        bucket: str,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> str:
        try:
            # MinIO requires a file-like object with read() method
            self._client.put_object(
                bucket_name=bucket,
                object_name=key,
                data=io.BytesIO(data),
                length=len(data),
                content_type=content_type,
                metadata=dict(metadata) if metadata else None,
            )
            return f"{bucket}/{key}"
        except S3Error as exc:  # pragma: no cover - covered via wrapping
            raise _wrap_error("put", bucket, key, exc) from exc
        except Exception as exc:  # pragma: no cover - covered via wrapping
            raise _wrap_error("put", bucket, key, exc) from exc

    def get_bytes(self, bucket: str, key: str) -> tuple[bytes, Mapping[str, str]]:
        try:
            obj = self._client.get_object(bucket, key)
            try:
                data = obj.read()
                headers = obj.headers or {}
            finally:
                obj.close()
            return data, headers
        except S3Error as exc:  # pragma: no cover - covered via wrapping
            raise _wrap_error("get", bucket, key, exc) from exc
        except Exception as exc:  # pragma: no cover - covered via wrapping
            raise _wrap_error("get", bucket, key, exc) from exc

    def ensure_bucket(self, name: str) -> None:
        try:
            if not self._client.bucket_exists(name):
                self._client.make_bucket(name)
        except S3Error as exc:  # pragma: no cover - covered via wrapping
            raise _wrap_error("ensure_bucket", name, None, exc) from exc
        except Exception as exc:  # pragma: no cover - covered via wrapping
            raise _wrap_error("ensure_bucket", name, None, exc) from exc

    # -------------
    # Presigner API
    # -------------
    def presign_get(self, bucket: str, key: str, ttl_seconds: int = 900) -> str:
        try:
            return self._client.get_presigned_url(
                method="GET",
                bucket_name=bucket,
                object_name=key,
                expires=ttl_seconds,
            )
        except S3Error as exc:  # pragma: no cover - covered via wrapping
            raise _wrap_error("presign_get", bucket, key, exc) from exc
        except Exception as exc:  # pragma: no cover - covered via wrapping
            raise _wrap_error("presign_get", bucket, key, exc) from exc


__all__ = ["MinioStorage"]
