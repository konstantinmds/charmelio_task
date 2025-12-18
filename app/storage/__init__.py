"""Storage package: object storage abstraction."""

from app.storage.contracts import ObjectStorage, Presigner, StorageError
from app.storage.minio_impl import MinioStorage

__all__ = ["ObjectStorage", "Presigner", "StorageError", "MinioStorage"]
