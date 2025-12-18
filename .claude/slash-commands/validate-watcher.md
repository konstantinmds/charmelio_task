---
name: validate-watcher
description: Validate the folder watcher service configuration and test file ingestion
---

You are helping validate the folder watcher service for the BH Accounting Knowledge Base. The watcher monitors `inbox/<tenant_slug>/<case_uuid>/<drop_uuid>/<filename>` for new files and processes them into the system.

## Tasks

1. **Check Configuration**
   - Verify `.env` has required settings: `INBOX_ROOT`, `MINIO_*`, `POSTGRES_*`
   - Confirm inbox directory exists: `mkdir -p inbox` if needed
   - Check Docker services are running: `docker compose ps` (watcher, postgres, minio)

2. **Verify Database Setup**
   - Check tenant table has test data: `SELECT * FROM tenant WHERE slug='acme';`
   - Check case_file table has test case: `SELECT * FROM case_file;`
   - If missing, provide seed SQL from README.md:
     ```sql
     INSERT INTO tenant(slug,name) VALUES('acme','Acme d.o.o.') ON CONFLICT DO NOTHING;
     INSERT INTO case_file(id,tenant_id,label) VALUES('22222222-2222-2222-2222-222222222222',(SELECT id FROM tenant WHERE slug='acme'),'VAT FBiH 2025-10');
     ```

3. **Test File Drop**
   - Create test structure: `mkdir -p inbox/acme/22222222-2222-2222-2222-222222222222/33333333-3333-3333-3333-333333333333/`
   - Create test file: `echo "Test content" > /tmp/sample.txt`
   - Atomic move: `mv /tmp/sample.txt inbox/acme/22222222-2222-2222-2222-222222222222/33333333-3333-3333-3333-333333333333/sample.txt`

4. **Verify Processing**
   - Check artifact table: `SELECT id, sha256, mime_type, created_at FROM artifact ORDER BY created_at DESC LIMIT 5;`
   - Check ingest_task table: `SELECT id, artifact_id, status, created_at FROM ingest_task ORDER BY created_at DESC LIMIT 5;`
   - Check file moved to `.processed`: `ls inbox/.processed/acme/`
   - Check metrics: `curl http://localhost:8002/metrics | grep watcher`

5. **Report Results**
   - Summarize what worked and what failed
   - Provide next steps if issues found
   - Reference README.md "Folder Watcher (MVP)" section for troubleshooting

## Expected Outputs

- `watcher_files_seen_total` increments
- `watcher_artifacts_created_total{tenant="acme"}` increments
- New rows in `artifact` and `ingest_task` tables
- File moved to `inbox/.processed/...`

If anything fails, check Docker logs: `docker compose logs watcher`
