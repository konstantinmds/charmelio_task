# What is the Worker Process?

## Overview

The **Worker** is a separate background process that does the heavy, time-consuming work of extracting clauses from PDF contracts. It runs continuously, polling Temporal for tasks to execute.

## Why Separate API and Worker?

### The Problem Without Workers

```python
# ❌ BAD: Everything in API (synchronous)
@app.post("/api/extract")
async def extract(file: UploadFile):
    # User uploads PDF
    text = extract_text(file)           # Takes 10 seconds ⏰
    clauses = call_openai(text)         # Takes 60 seconds ⏰
    save_to_db(clauses)                 # Takes 2 seconds ⏰

    return {"clauses": clauses}
    # User waits 72 seconds! 😱
    # Connection might timeout!
```

### The Solution With Workers

```python
# ✅ GOOD: API responds immediately, worker does the work
@app.post("/api/extract")
async def extract(file: UploadFile):
    # Save PDF to MinIO
    # Start workflow in Temporal
    return {"id": doc_id, "status": "pending"}
    # User gets response in <1 second! 🎉
    # They can check status later
```

## Architecture Flow

```
┌─────────┐
│  User   │
└────┬────┘
     │ POST /api/extract (PDF file)
     ▼
┌─────────────────┐
│   API Service   │ 1. Upload PDF to MinIO
│   (FastAPI)     │ 2. Create DB record (status=pending)
│   Port 8000     │ 3. Start Temporal workflow
└────┬────────────┘ 4. Return {"id": "123", "status": "pending"}
     │
     │ Starts workflow
     ▼
┌──────────────────┐
│    Temporal      │ Workflow orchestration
│   (Server)       │ - Tracks workflow state
│   Port 7233      │ - Handles retries
└────┬─────────────┘ - Manages timeouts
     │
     │ Schedules activities
     ▼
┌──────────────────────────────────────────────┐
│         Worker Process                       │
│         (Background Service)                 │
│                                              │
│  Activity 1: parse_pdf()                     │
│  ├─ Download from MinIO                     │
│  ├─ Extract text with pdfplumber            │
│  └─ Takes ~10-30 seconds                    │
│                                              │
│  Activity 2: llm_extract()                  │
│  ├─ Call OpenAI API                         │
│  ├─ Get structured clause data              │
│  └─ Takes ~30-60 seconds                    │
│                                              │
│  Activity 3: store_results()                │
│  ├─ Save to database                        │
│  ├─ Upload results to MinIO                 │
│  ├─ Update status to "completed"            │
│  └─ Takes ~2-5 seconds                      │
└──────────────────────────────────────────────┘
     │
     ▼
┌─────────┐
│  User   │ GET /api/extractions/123
│         │ ← {"id": "123", "status": "completed", "clauses": {...}}
└─────────┘
```

## Code Structure

### API Service (`app/main.py`)
```python
from temporalio.client import Client
from worker.workflows import ExtractionWorkflow

@app.on_event("startup")
async def start_temporal():
    app.state.temporal = await Client.connect("temporal:7233")

@app.post("/api/extract")
async def extract(file: UploadFile):
    # Quick operations only
    document_id = str(uuid4())

    # Save to MinIO
    storage_client.put_object("uploads", f"{document_id}.pdf", await file.read())

    # Create DB record
    with get_db() as db:
        db.add(Document(id=document_id, status="pending"))
        db.commit()

    # Start workflow (doesn't wait for completion!)
    await app.state.temporal.start_workflow(
        ExtractionWorkflow.run,
        document_id,
        id=f"extraction-{document_id}",
        task_queue="extraction-queue"
    )

    # Return immediately
    return {"id": document_id, "status": "pending"}
```

### Worker Service (`worker/run.py`)
```python
# This runs forever, polling for work
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from worker.workflows import ExtractionWorkflow
from worker.activities import parse_pdf, llm_extract, store_results

async def main():
    # Connect to Temporal
    client = await Client.connect("temporal:7233")

    # Create worker
    worker = Worker(
        client,
        task_queue="extraction-queue",
        workflows=[ExtractionWorkflow],
        activities=[parse_pdf, llm_extract, store_results]
    )

    # Run forever, polling for tasks
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
```

### Workflow Definition (`worker/workflows.py`)
```python
from temporalio import workflow
from datetime import timedelta

@workflow.defn
class ExtractionWorkflow:
    @workflow.run
    async def run(self, document_id: str) -> dict:
        # Step 1: Parse PDF
        parsed = await workflow.execute_activity(
            parse_pdf,
            document_id,
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=workflow.RetryPolicy(maximum_attempts=3)
        )

        # Step 2: Extract clauses with LLM
        extracted = await workflow.execute_activity(
            llm_extract,
            args=[document_id, parsed["text"]],
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=workflow.RetryPolicy(maximum_attempts=2)
        )

        # Step 3: Store results
        await workflow.execute_activity(
            store_results,
            args=[document_id, extracted],
            start_to_close_timeout=timedelta(seconds=30)
        )

        return {"status": "completed", "document_id": document_id}
```

### Activities (`worker/activities.py`)
```python
from temporalio import activity

@activity.defn
async def parse_pdf(document_id: str) -> dict:
    # Download PDF from MinIO
    pdf_bytes = storage_client.get_object("uploads", f"{document_id}.pdf")

    # Extract text
    text, pages = extract_text_and_pages(pdf_bytes)

    # Update database
    with get_db() as db:
        doc = db.query(Document).filter(Document.id == document_id).first()
        doc.raw_text = text
        doc.page_count = pages
        doc.status = "processing"
        db.commit()

    return {"text": text, "page_count": pages}

@activity.defn
async def llm_extract(document_id: str, text: str) -> dict:
    # Call OpenAI API
    result = await extract_clauses(text)
    return result.model_dump()

@activity.defn
async def store_results(document_id: str, data: dict) -> None:
    # Save to MinIO
    storage_client.put_object(
        "extractions",
        f"{document_id}.json",
        json.dumps(data).encode()
    )

    # Update database
    with get_db() as db:
        db.add(Extraction(document_id=document_id, clauses=data))
        doc = db.query(Document).filter(Document.id == document_id).first()
        doc.status = "completed"
        db.commit()
```

## Docker Setup

In `docker-compose.yml`, we run the same image twice with different commands:

```yaml
services:
  # API Service - handles HTTP requests
  api:
    build: .
    command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    ports:
      - "8000:8000"

  # Worker Service - processes background tasks
  worker:
    build: .
    command: ["python", "-m", "worker.run"]  # Different command!
    # No ports exposed - it's a background worker
```

## Benefits of This Architecture

### 1. **Fast API Responses**
- Users get immediate response
- No timeout issues
- Better user experience

### 2. **Scalability**
```bash
# Can scale workers independently
docker compose up -d --scale worker=5  # Run 5 workers!
```

### 3. **Reliability**
- Temporal handles retries automatically
- If worker crashes, another picks up the work
- Workflow state is persisted

### 4. **Visibility**
- View workflow progress in Temporal UI
- See which activities succeeded/failed
- Inspect workflow history

### 5. **Resource Isolation**
- CPU-intensive work doesn't block API
- Can give workers more resources
- API stays responsive

## How the Worker Actually Runs

The worker is a **long-running process** that:

1. **Connects to Temporal** on startup
2. **Polls** the task queue for work
3. **Executes activities** when work arrives
4. **Reports results** back to Temporal
5. **Repeats forever** (or until stopped)

```python
# Simplified worker loop
while True:
    task = await temporal_client.poll_activity_task(queue="extraction-queue")
    if task:
        result = await execute_activity(task)
        await temporal_client.complete_activity(task.id, result)
```

## Viewing Worker Activity

### Check Worker Logs
```bash
make logs-worker
```

### Temporal UI
Visit http://localhost:8233 to see:
- Running workflows
- Completed workflows
- Failed workflows
- Activity execution times
- Retry attempts

## Common Questions

### Q: Can't the API just do everything?
**A:** For small tasks, yes. But for PDF extraction + OpenAI calls (60+ seconds), users would timeout waiting. Async background processing is better.

### Q: Why not just use Celery or RQ?
**A:** Temporal provides:
- Workflow state persistence
- Automatic retries
- Durable timers
- Better visibility/debugging
- Type-safe workflows

### Q: How many workers should I run?
**A:** Start with 1-2. Scale up based on:
- Queue depth
- Processing time
- Available resources

### Q: What if a worker crashes mid-task?
**A:** Temporal detects the failure and schedules the activity on another worker. The workflow continues.

### Q: Can I run workers on different machines?
**A:** Yes! Workers just need to connect to Temporal. You can run them anywhere.

## Summary

The **worker** is a background service that:
- Runs continuously
- Polls Temporal for tasks
- Executes CPU/time-intensive operations
- Allows the API to respond quickly
- Can be scaled independently

It's the **"engine"** that does the actual work, while the **API** is the **"front desk"** that takes orders quickly.
