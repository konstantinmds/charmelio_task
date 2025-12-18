# Quick Reference

## What is the Worker?

**Simple Answer:** A background process that does the slow, heavy work (extracting PDF clauses) so the API can respond quickly to users.

## Analogy

Think of it like a restaurant:

```
API = Waiter
- Takes orders quickly
- Responds to customers
- Doesn't cook the food

Worker = Kitchen
- Cooks the actual food
- Takes time to prepare
- Works in the background

Temporal = Order System
- Tracks orders
- Tells kitchen what to make
- Notifies when food is ready
```

## Two Main Services

### API Service (Port 8000)
```bash
# What it runs
uvicorn app.main:app --host 0.0.0.0 --port 8000

# What it does
- Accepts PDF uploads
- Starts background job
- Returns immediately: {"status": "pending"}
- Lets users check status later
```

### Worker Service (No Port - Background)
```bash
# What it runs
python -m worker.run

# What it does
- Waits for work from Temporal
- Parses PDF (slow!)
- Calls OpenAI (slow!)
- Saves results
- Updates status to "completed"
```

## The Workflow

```
1. User uploads PDF
   ↓
2. API returns: "pending" (in 1 second)
   ↓
3. Worker processes in background (60 seconds)
   ↓
4. User checks status later
   ↓
5. API returns: "completed" with results
```

## Why This Design?

### Without Worker (Bad)
```python
@app.post("/extract")
def extract(file):
    text = parse_pdf(file)      # 10 seconds
    clauses = call_openai(text)  # 60 seconds
    return clauses               # User waits 70 seconds! 😱
```

### With Worker (Good)
```python
@app.post("/extract")
async def extract(file):
    start_background_job(file)
    return {"status": "pending"}  # User waits 1 second! 🎉

# Worker does the slow work in background
```

## Docker Commands

```bash
# Start everything
make up

# View API logs
make logs-api

# View worker logs (to see PDF processing)
make logs-worker

# Check if services are healthy
make healthcheck

# Stop everything
make down
```

## Viewing Worker Activity

### Check Logs
```bash
make logs-worker
```

You'll see output like:
```
[INFO] Worker started, polling extraction-queue
[INFO] Received task: parse_pdf(doc-123)
[INFO] Parsing PDF...
[INFO] Extracted 2500 words from 12 pages
[INFO] Task completed in 15.2s
[INFO] Received task: llm_extract(doc-123)
[INFO] Calling OpenAI API...
[INFO] Extracted 8 clauses
[INFO] Task completed in 45.8s
```

### Temporal UI
Visit http://localhost:8233
- See all running workflows
- View workflow history
- Check which activities succeeded/failed
- See execution times

## Files to Understand

| File | What It Does |
|------|--------------|
| `app/main.py` | API endpoints (fast responses) |
| `worker/run.py` | Worker startup (polls for tasks) |
| `worker/workflows.py` | Defines the extraction workflow |
| `worker/activities.py` | Individual tasks (parse PDF, call OpenAI) |
| `docker-compose.yml` | Runs both API and Worker |

## Common Questions

**Q: Why do I need a worker? Can't the API just do everything?**
A: For short tasks (<5 sec), yes. But PDF extraction + OpenAI takes 60+ seconds. Users would timeout waiting.

**Q: How many workers can I run?**
A: As many as you want! Scale with: `docker compose up -d --scale worker=5`

**Q: What if the worker crashes?**
A: Temporal detects it and assigns the task to another worker. No work is lost.

**Q: Can I see what the worker is doing?**
A: Yes! Check `make logs-worker` or view Temporal UI at http://localhost:8233

**Q: Does the worker need its own database?**
A: No, it shares the same Postgres, MinIO, and Temporal as the API.

## Summary

| Component | Role | Runs |
|-----------|------|------|
| API | Front desk - takes requests | `uvicorn app.main:app` |
| Worker | Kitchen - does the work | `python -m worker.run` |
| Temporal | Manager - coordinates everything | Temporal server |
| Postgres | Filing cabinet - stores data | PostgreSQL |
| MinIO | Storage room - stores files | MinIO server |

The worker is just **another instance of your app** running a different command that polls for background tasks instead of handling HTTP requests.
