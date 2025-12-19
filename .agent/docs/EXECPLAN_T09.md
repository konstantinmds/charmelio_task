# T-09 API — Startup & Health

This ExecPlan is a living document. Maintain it in accordance with `.agent/PLANS.md` from the repository root so a newcomer can complete the work using only this file.

## Purpose / Big Picture

Bring the FastAPI service up cleanly with database, storage, and Temporal client wiring, and expose health endpoints for liveness (`/health`) and readiness (`/health/ready`). This lets Docker, CI, and developers quickly detect whether the stack is up and dependencies are reachable without crashing the API if Temporal is unavailable.

## Progress

- [ ] (2025-01-09 00:00Z) Draft startup/health design
- [ ] (2025-01-09 00:00Z) Implement startup wiring (DB tables, storage singleton ensure, Temporal client) in `app/main.py`
- [ ] (2025-01-09 00:00Z) Add `/health` and `/health/ready` endpoints
- [ ] (2025-01-09 00:00Z) Add tests for liveness and readiness (success/failure), coverage ≥95% for health handlers

## Surprises & Discoveries

- None yet; record any Temporal client connection quirks, storage ensure idempotency observations, or test isolation issues as they arise.

## Decision Log

- Planned: Do not crash startup if Temporal client connect fails; stash `None` on `app.state.temporal` and surface in readiness.
- Planned: Use `Base.metadata.create_all(engine)` as MVP instead of Alembic; document future migration path.
- Planned: Storage singleton `app.deps.storage` handles bucket ensure on import; readiness may call `ensure_bucket` again safely.
- Planned: Health endpoints are cheap; liveness has no dependencies, readiness checks DB, storage, Temporal.
- Planned: Use FastAPI dependency override in tests to inject fake DB handle; monkeypatch storage and temporal state to avoid network.
- Planned: Coverage gate ≥95% for `app/main.py` health handlers.
- Planned: Storage interface is `get_bytes(bucket, key) -> bytes` and `put_bytes(bucket, key, data, content_type=None)` (documented for consistency).

## Outcomes & Retrospective

Target end state:
- `app/main.py` wires startup: creates DB tables, ensures storage buckets via singleton, connects Temporal client to `app.state.temporal` (tolerates failure).
- Liveness endpoint `GET /health` returns `{status: "ok"}` 200.
- Readiness endpoint `GET /health/ready` checks DB, storage, Temporal; returns 200 when all ok, else 503 with component-specific error details.
- Tests cover liveness and readiness (success and failure paths) with ≥95% coverage for health code in `app/main.py`.

## Context and Orientation

Repository root: `/Users/tijanapetrovic/Documents/inner_outer_projs/charmelio_clean`

Key modules:
- `app/main.py` will host startup hooks and health routes.
- `app/db/session.py` provides `engine` and `get_db_dependency` (dependency for sessions).
- `app/db/models.py` defines `Base`; tables created via `Base.metadata.create_all(bind=engine)`.
- `app/config.py` (or similar) exposes `settings.temporal_address`.
- `app/deps.py` exposes `storage` singleton (ensures buckets on import); storage interface uses `ensure_bucket(name)`, `get_bytes(bucket, key) -> bytes`, `put_bytes(...)`.
- Temporal client: `temporalio.client.Client.connect`.

## Plan of Work

1. Inspect `app/main.py` existing content; ensure FastAPI app initialization location and router structure.
2. Implement startup event:
   - Call `Base.metadata.create_all(bind=engine)` (MVP).
   - Instantiate Temporal client with `settings.temporal_address`; on failure, set `app.state.temporal = None`.
   - Ensure storage singleton import occurs (buckets ensured as side effect); no crash on failure.
3. Add models for health responses if desired (`Health` Pydantic model) and add endpoints:
   - `GET /health` returns status ok.
   - `GET /health/ready`: check DB via simple `SELECT 1` using dependency; check storage by `ensure_bucket` for uploads/extractions; check Temporal by presence of `app.state.temporal`; respond 200 on all ok else 503 with detail per component.
4. Write tests in `tests/test_health.py` using `TestClient`:
   - Liveness: expect 200/ok.
   - Readiness success: override DB dependency to a stub that executes; monkeypatch storage.ensure_bucket to no-op; set `app.state.temporal` to dummy; expect 200 with all ok.
   - Readiness failure: DB execute raises, storage ensure raises, temporal None; expect 503 with detail showing errors.
   - Use dependency overrides and monkeypatch to avoid real network/DB.
5. Run tests with coverage gate for `app/main.py` (health portions):
   - `PYTHONPATH=. pytest tests/test_health.py --cov=app/main.py --cov-report=term-missing --cov-fail-under=95`

## Concrete Steps

Work from repository root.

1. Review current main and settings:
     PYTHONPATH=. python - <<'PY'
     import inspect
     import app.main as m
     print("Has app:", hasattr(m, "app"))
     PY

2. Implement startup + health in `app/main.py` per Plan of Work (ensure storage import, Temporal connect with try/except, create_all).

3. Add tests `tests/test_health.py` with dependency overrides:
     - Override `get_db_dependency` to yield stub `execute`/`close`.
     - Monkeypatch `app.deps.storage.ensure_bucket`.
     - Set `app.state.temporal` explicitly in tests.

4. Run tests with coverage:
     PYTHONPATH=. pytest tests/test_health.py --cov=app/main.py --cov-report=term-missing --cov-fail-under=95

## Validation and Acceptance

Work is accepted when:
- API starts without crashing if Temporal is unavailable; readiness reflects failure.
- `/health` returns 200 with status ok.
- `/health/ready` returns 200 when DB/storage/Temporal are reachable; returns 503 with per-component error info when any fail.
- Tests described above pass with coverage ≥95% for health code.

## Idempotence and Recovery

- Startup can be re-run safely; `create_all` and storage ensure are idempotent. Temporal connect failures do not crash the service.
- Tests are isolated via dependency overrides; rerunnable without external services.

## Artifacts and Notes

Expected test command:
     PYTHONPATH=. pytest tests/test_health.py --cov=app/main.py --cov-report=term-missing --cov-fail-under=95

New/changed files after completion:
     app/main.py (startup wiring, health endpoints)
     tests/test_health.py (health tests)

## Interfaces and Dependencies

- FastAPI app in `app/main.py`.
- DB: `app.db.session.engine`, `get_db_dependency`; `Base` from `app.db.models`.
- Storage: `app.deps.storage` singleton; `ensure_bucket(name)`, `get_bytes(bucket, key) -> bytes`, `put_bytes(...)`.
- Temporal: `temporalio.client.Client.connect(settings.temporal_address)`.
- Tests use `fastapi.testclient.TestClient`, `pytest`, and dependency overrides/monkeypatch.

Initial version created 2025-01-09.***
