# Session Memory — T-03 DB Layer & Migrations (Story)

We started with a mismatch between the current models and the old tests. Models now use bucket/object_key, file_size, model_used/clauses, and require artifact_key on extractions. Tests were still using s3_key, file_size_bytes, clause_type/clause_text. That caused IntegrityErrors and “no such column” issues. We rewrote tests to match the new schema, added artifact_key to extractions, and switched fixtures from in-memory SQLite to temp files so tables persist across connections.

Coverage kept failing because a root-owned .coverage file blocked writes. The fix is to delete it (sudo rm -f .coverage) or set COVERAGE_FILE=/tmp/.coverage for local runs.

We added Alembic properly: alembic.ini, env.py, initial migration 0001_init for documents/extractions, and a migration helper run_migrations. The Dockerfile now copies alembic files. app.main runs migrations on startup, falling back to create_all. Tests still create schema via Base.metadata for speed; migrations can be run in tests if desired.

Async sessions were optional; missing asyncpg caused import errors. We guarded async imports and raise a clear error when async extras are absent. Sync paths remain available for tests.

Repository delete_document was updated to explicitly delete extractions before documents (SQLite doesn’t enforce ON DELETE CASCADE consistently in our unit setup).

To run tests locally without rebuild: remove .coverage if root-owned, then pytest -q --disable-warnings (or set COVERAGE_FILE). For containers, use bind-mount + pip install -e ".[dev]" and run pytest inside.

Outstanding: ensure asyncpg is installed if we want async engine live; clean up .coverage; rerun pytest to hit the 95% gate; optional small tests to cover remaining branches (e.g., latest_extraction None path, main lifespan lines). Alembic scripts are present; to apply in containers, rebuild or copy alembic/ and alembic.ini into the image (already in Dockerfile now).
