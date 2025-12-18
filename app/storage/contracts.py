"""Storage interfaces and error types."""

from __future__ import annotations

from typing import Mapping, Protocol, runtime_checkable


class StorageError(Exception):
    """Wraps underlying storage exceptions with operation context."""

    def __init__(self, op: str, bucket: str | None, key: str | None, message: str):
        self.op = op
        self.bucket = bucket
        self.key = key
        self.message = message
        super().__init__(self.__str__())

    def __str__(self) -> str:  # pragma: no cover - trivial string formatting
        bucket_repr = self.bucket or "<unknown>"
        key_repr = self.key or "<unknown>"
        return f"{self.op} failed for bucket={bucket_repr} key={key_repr}: {self.message}"


@runtime_checkable
class ObjectStorage(Protocol):
    """Contract for object storage implementations."""

    def put_bytes(
        self,
        bucket: str,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> str:
        ...

    def get_bytes(self, bucket: str, key: str) -> tuple[bytes, Mapping[str, str]]:
        ...

    def ensure_bucket(self, name: str) -> None:
        ...


@runtime_checkable
class Presigner(Protocol):
    """Optional presigner interface for generating temporary URLs."""

    def presign_get(self, bucket: str, key: str, ttl_seconds: int = 900) -> str:
        ...


__all__ = ["StorageError", "ObjectStorage", "Presigner"]
