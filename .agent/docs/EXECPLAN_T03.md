# ExecPlan: T-03 Database Layer & Session Utilities

## Purpose
Deliver a reliable persistence layer for documents and extractions that works on Postgres (prod) and SQLite (tests), with clear transaction semantics for activities and FastAPI routes, plus high-coverage tests.

## Context
- Current models (`app/db/models.py`) define Document/Extraction with string UUID PKs and JSON clauses; session utilities live in `app/db/session.py`.
- Startup (`app/main.py`) calls `init_db()` and wires shared resources; no Alembic yet (create_all only).
- Tests exist (`tests/test_database.py`) but do not cover session helpers or latest-extraction behavior.

## Plan
1) Align models for portability (Postgres + SQLite) and Pylance: keep `Mapped` + `mapped_column`, JSON, status enum, and latest-extraction index. Ensure relationships and types are clean.
2) Extend session utilities: keep `get_db()` (commit/rollback/close) and add `get_db_dependency()` (yield/close for FastAPI). Ensure `SessionLocal` is configurable for tests.
3) Add CRUD helpers (optional but short) in `app/db/repository.py`: create_document, add_extraction, latest_extraction(document_id), delete_document.
4) Tests (pytest) for:
   - Model constraints: required fields, enum validation, cascade delete.
   - CRUD happy path: create/update document, insert extraction, latest extraction ordering.
   - Session utils: commit on success, rollback on error, dependency closes session.
   - JSON roundtrip: clauses retains nested keys.
5) Validation: run `pytest -q --disable-warnings`; ensure coverage includes new tests. No migrations required for this ticket.

## Concrete Steps
- Edit `app/db/models.py` if needed to keep mapped_column typing and relationships portable.
- Update `app/db/session.py` to expose `get_db_dependency`.
- Add `app/db/repository.py` with small helpers (optional but preferred).
- Add tests under `tests/test_db_models.py` and `tests/test_session_utils.py` covering steps above.
- Run `pytest` to confirm green.

## Acceptance
- Models create cleanly on SQLite and Postgres.
- `get_db()` commits/rolls back correctly; dependency yields/cleans.
- CRUD + latest-extraction logic verified in tests; cascade delete validated.
- Coverage ≥ 95% for `app/db/` (per pyproject).
