from unittest.mock import MagicMock

import pytest
from minio.error import S3Error

from app.storage.contracts import StorageError
from app.storage.factory import _normalize_endpoint, build_storage
from app.storage.minio_impl import MinioStorage


def _make_s3_error(bucket: str | None = None, key: str | None = None) -> S3Error:
    return S3Error(None, "AccessDenied", "denied", "resource", "request", "host", bucket, key)


def test_put_bytes_happy_path():
    client = MagicMock()
    storage = MinioStorage(client)

    result = storage.put_bytes(
        "uploads",
        "doc.pdf",
        b"data",
        content_type="application/pdf",
        metadata={"a": "b"},
    )

    assert result == "uploads/doc.pdf"
    client.put_object.assert_called_once()
    kwargs = client.put_object.call_args.kwargs
    assert kwargs["bucket_name"] == "uploads"
    assert kwargs["object_name"] == "doc.pdf"
    assert kwargs["data"].read() == b"data"  # BytesIO object
    assert kwargs["length"] == 4
    assert kwargs["content_type"] == "application/pdf"
    assert kwargs["metadata"] == {"a": "b"}


def test_get_bytes_happy_path():
    obj = MagicMock()
    obj.read.return_value = b"hello"
    obj.headers = {"content-type": "text/plain"}

    client = MagicMock()
    client.get_object.return_value = obj
    storage = MinioStorage(client)

    data, headers = storage.get_bytes("uploads", "doc.pdf")

    assert data == b"hello"
    assert headers == {"content-type": "text/plain"}
    obj.read.assert_called_once()
    obj.close.assert_called_once()
    client.get_object.assert_called_once_with("uploads", "doc.pdf")


def test_ensure_bucket_creates_when_missing():
    client = MagicMock()
    client.bucket_exists.side_effect = [False, False]
    storage = MinioStorage(client)

    storage.ensure_bucket("uploads")
    storage.ensure_bucket("extractions")

    assert client.bucket_exists.call_count == 2
    client.make_bucket.assert_any_call("uploads")
    client.make_bucket.assert_any_call("extractions")


def test_ensure_bucket_noop_when_exists():
    client = MagicMock()
    client.bucket_exists.return_value = True
    storage = MinioStorage(client)

    storage.ensure_bucket("uploads")

    client.make_bucket.assert_not_called()


def test_presign_get_happy_path():
    client = MagicMock()
    client.get_presigned_url.return_value = "http://signed-url"
    storage = MinioStorage(client)

    url = storage.presign_get("uploads", "doc.pdf", ttl_seconds=600)

    assert url == "http://signed-url"
    client.get_presigned_url.assert_called_once_with(
        method="GET", bucket_name="uploads", object_name="doc.pdf", expires=600
    )


def test_error_mapping_for_s3error_put():
    client = MagicMock()
    client.put_object.side_effect = _make_s3_error("uploads", "doc.pdf")
    storage = MinioStorage(client)

    with pytest.raises(StorageError) as excinfo:
        storage.put_bytes("uploads", "doc.pdf", b"data")

    err = excinfo.value
    assert err.op == "put"
    assert err.bucket == "uploads"
    assert err.key == "doc.pdf"
    assert "denied" in err.message


def test_error_mapping_generic_exception_get():
    client = MagicMock()
    client.get_object.side_effect = RuntimeError("boom")
    storage = MinioStorage(client)

    with pytest.raises(StorageError) as excinfo:
        storage.get_bytes("uploads", "missing.pdf")

    err = excinfo.value
    assert err.op == "get"
    assert err.bucket == "uploads"
    assert err.key == "missing.pdf"
    assert "boom" in err.message


def test_factory_build_storage_ensures_buckets(monkeypatch):
    # Prepare fake client
    client = MagicMock()
    client.bucket_exists.side_effect = [False, False]

    created_clients = {}

    def fake_minio(endpoint, access_key, secret_key, secure):
        created_clients["args"] = (endpoint, access_key, secret_key, secure)
        return client

    monkeypatch.setattr("app.storage.factory.Minio", fake_minio)
    monkeypatch.setenv("S3_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("S3_ACCESS_KEY", "ak")
    monkeypatch.setenv("S3_SECRET_KEY", "sk")
    monkeypatch.setenv("S3_BUCKET_UPLOADS", "uploads")
    monkeypatch.setenv("S3_BUCKET_EXTRACTIONS", "extractions")

    storage = build_storage()

    assert isinstance(storage, MinioStorage)
    assert created_clients["args"] == ("minio:9000", "ak", "sk", False)
    assert client.bucket_exists.call_count == 2
    client.make_bucket.assert_any_call("uploads")
    client.make_bucket.assert_any_call("extractions")


def test_normalize_endpoint_strips_scheme_and_sets_secure():
    host, secure = _normalize_endpoint("https://example.com:9000")
    assert host == "example.com:9000"
    assert secure is True

    host, secure = _normalize_endpoint("http://example.com:9000/")
    assert host == "example.com:9000"
    assert secure is False
