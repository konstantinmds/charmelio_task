# T-04 MinIO Storage Wrapper (Backend Infra Abstraction)

This ExecPlan is a living document. Maintain it in accordance with `.agent/PLANS.md` from the repository root so a newcomer can complete the work using only this file.

## Purpose / Big Picture

We need a single object-storage abstraction so FastAPI routes and background workers stop depending directly on the MinIO SDK. After this change, code can import `storage` from `app.deps` to create buckets, upload bytes, download bytes, and optionally generate presigned download URLs. Startup must ensure the `uploads` and `extractions` buckets exist. Behavior will be proven through unit tests that mock MinIO and achieve at least 95% coverage over `app/storage/*`.

## Progress

- [x] (2025-12-18 21:42Z) Define storage contracts and StorageError.
- [x] (2025-12-18 22:52Z) Implement MinioStorage with error mapping and bucket ensure logic.
- [x] (2025-12-18 23:38Z) Wire factory and app.deps to instantiate storage once and ensure buckets.
- [x] (2025-12-18 22:26Z) Add mocked unit tests for happy paths and error mapping; verify coverage target.

## Surprises & Discoveries

- (2025-12-18 23:42Z) pyproject.toml has global `fail_under = 95` that applies to total coverage, not per-package. Storage package achieves 100% coverage as required, but overall project is at 85%.
- (2025-12-18 23:40Z) Session utility tests needed updating to use monkeypatch instead of SessionLocal.configure() for SQLAlchemy 2.x compatibility.
- (2025-12-18 23:41Z) Document model requires `object_key` field which tests were missing.

## Decision Log

- (2025-12-18 23:38Z) Created lazy `get_storage()` in app/deps.py rather than eagerly instantiating at import time to avoid failures when MinIO is unavailable.
- (2025-12-18 23:38Z) Used `_normalize_endpoint()` helper to extract host:port and determine secure flag from full URL, matching env var pattern in .env.example.

## Outcomes & Retrospective

**Shipped:**
- `app/storage/contracts.py` - ObjectStorage and Presigner protocols with StorageError
- `app/storage/minio_impl.py` - MinioStorage implementation with full error mapping
- `app/storage/factory.py` - build_storage() factory with bucket auto-creation
- `app/storage/__init__.py` - Package exports
- `app/deps.py` - Lazy storage singleton via get_storage()
- `tests/test_storage_minio.py` - 9 tests covering happy paths and error mapping (100% coverage on storage package)

**Fixed along the way:**
- Session utility tests now work correctly with SQLAlchemy 2.x
- Added missing object_key field to test fixtures

**Remaining gaps:**
- Overall project coverage is 85% (below 95% threshold) - existing issue outside T-04 scope

## Context and Orientation

Repository root: `/Users/tijanapetrovic/Documents/inner_outer_projs/charmelio_clean`. Backend Python code lives in `app/`; background worker code lives in `worker/`; tests are in `tests/`. MinIO is the S3-compatible object store already used by the project. We will add a new `app/storage/` package containing interfaces and a MinIO implementation, plus a factory that builds the storage client from environment variables. `app/deps.py` holds shared singleton dependencies for FastAPI; it will expose the storage instance. Bucket conventions: PDF uploads use `uploads/{document_id}.pdf`; extraction JSON uses `extractions/{document_id}.json`.

## Plan of Work

First, create `app/storage/contracts.py` defining the storage protocols and `StorageError`. The `ObjectStorage` protocol will specify `put_bytes`, `get_bytes`, and `ensure_bucket` with the exact signatures in the ticket, and `Presigner` will specify `presign_get`. `StorageError` will carry `op`, `bucket`, `key`, and a readable message to wrap SDK failures.

Next, implement `app/storage/minio_impl.py` with a `MinioStorage` class that satisfies the protocols. It will hold a `minio.Minio` client, map `minio.error.S3Error` (and other exceptions) to `StorageError`, and implement `put_bytes` (using `put_object` with content type and metadata, returning `"bucket/key"`), `get_bytes` (streaming all bytes and surfacing headers/metadata), `ensure_bucket` (idempotent `bucket_exists` then `make_bucket`), and `presign_get` (using MinIO presign API with `ttl_seconds`). Minimal comments only where behavior is non-obvious.

Then, add `app/storage/factory.py` with `build_storage()` that reads env vars for endpoint, access key, secret key, and secure flag, plus optional `UPLOADS_BUCKET` and `EXTRACTIONS_BUCKET` (defaulting to `uploads` and `extractions`). It will create the MinIO client, wrap it in `MinioStorage`, and call `ensure_bucket` for both buckets during construction. Update `app/deps.py` to instantiate storage once at import time (`storage = build_storage()`) so both API and worker imports share it.

Finally, write `tests/test_storage_minio.py` using `unittest.mock` to fully stub the MinIO client (no network or disk). Cover happy paths (`put_bytes` returns `bucket/key` and forwards content type/metadata; `get_bytes` returns bytes and headers; `ensure_bucket` creates only when missing; `presign_get` returns the mock URL) and error mapping (MinIO `S3Error` becomes `StorageError` with correct op/bucket/key/message; generic exceptions also wrapped). Run pytest with coverage over `app/storage` and keep coverage at or above 95%.

## Concrete Steps

Work in `/Users/tijanapetrovic/Documents/inner_outer_projs/charmelio_clean`.

1) Inspect dependencies if needed: `pip show minio` or review `requirements.txt` to confirm import path.
2) Create `app/storage/contracts.py`, `app/storage/minio_impl.py`, and `app/storage/factory.py` with the behaviors described above.
3) Update `app/deps.py` to import `build_storage` and expose `storage = build_storage()`.
4) Add `tests/test_storage_minio.py` with mocks for the client and S3Error; include tests for happy paths, ensure bucket creation, and error mapping.
5) Run formatting/lint if configured (e.g., `ruff format` and `ruff check`), then run tests with coverage:
   `pytest --maxfail=1 --disable-warnings -q --cov=app/storage --cov-report=term-missing`
6) If coverage is below 95% for `app/storage/*`, expand tests until the threshold is met.

Expected test output: all new tests pass and coverage report shows ≥95% lines covered for `app/storage/*` with no untested branches in critical logic.

## Validation and Acceptance

- Import check: `python - <<'PY'
from app.deps import storage
print(storage)
PY` runs without exceptions.
- Tests: `pytest --maxfail=1 --disable-warnings -q --cov=app/storage --cov-report=term-missing` succeeds with ≥95% coverage on `app/storage/*` and includes cases for put/get/ensure/presign and error mapping.
- Startup expectation (implicit via tests): `build_storage()` calls `ensure_bucket` for `uploads` and `extractions` exactly once each, and `ensure_bucket` is idempotent.
- All API/worker code should import the abstraction only; no new direct MinIO client usage is introduced.

## Idempotence and Recovery

File creation and mocked tests are safe to rerun. `ensure_bucket` is explicitly idempotent (no error if bucket already exists). If a test fails, adjust the implementation or mocks and rerun pytest. No external state or migrations are touched by this plan.

## Artifacts and Notes

New files: `app/storage/contracts.py`, `app/storage/minio_impl.py`, `app/storage/factory.py`, `tests/test_storage_minio.py`. Modified file: `app/deps.py`. Environment variables used: `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_SECURE` (boolean-ish), optional `UPLOADS_BUCKET`, `EXTRACTIONS_BUCKET`. Keep code ASCII and add only minimal clarifying comments where logic is not obvious.

## Interfaces and Dependencies

Protocols in `app/storage/contracts.py`:
- `class ObjectStorage(Protocol)`: `put_bytes(bucket, key, data: bytes, *, content_type: str | None = None, metadata: Mapping[str, str] | None = None) -> str`; `get_bytes(bucket, key) -> tuple[bytes, Mapping[str, str]]`; `ensure_bucket(name: str) -> None`.
- `class Presigner(Protocol)`: `presign_get(bucket: str, key: str, ttl_seconds: int = 900) -> str`.
- `class StorageError(Exception)`: initialized with `op`, `bucket`, `key`, and human-readable message; used to wrap MinIO failures.

Implementation in `app/storage/minio_impl.py`:
- `class MinioStorage(ObjectStorage, Presigner)`: wraps `minio.Minio`; `put_bytes` uses `put_object` with content length, optional content type, and metadata; `get_bytes` reads the stream fully and returns bytes plus headers/metadata; `ensure_bucket` uses `bucket_exists` then `make_bucket`; `presign_get` calls the MinIO presign API with `ttl_seconds`.
- Error handling: catch `minio.error.S3Error` (and generic exceptions) and raise `StorageError(op, bucket, key, str(exc))` so callers only see the abstraction errors.

Factory in `app/storage/factory.py`:
- `build_storage()` constructs `minio.Minio` using env vars for endpoint/creds/secure, wraps it in `MinioStorage`, and calls `ensure_bucket` for `uploads` and `extractions` buckets on creation. Returns the storage instance for reuse.

Dependency wiring in `app/deps.py`:
- Import `build_storage` and set `storage = build_storage()` at module import so API and worker modules can import the singleton.

Testing in `tests/test_storage_minio.py`:
- Use `unittest.mock` to stub MinIO client methods and `S3Error`. Validate happy paths, ensure-bucket behavior, presigning, and error mapping. Achieve ≥95% coverage for `app/storage/*`.

Initial version created 2025-12-18 21:42Z.
