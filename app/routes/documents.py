"""Document upload and extraction endpoints."""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Document, DocumentStatus
from app.db.session import get_db
from app.deps import get_storage
from worker.workflows import ExtractionWorkflow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["documents"])


@router.post("/extract")
async def extract(
    request: Request,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF for clause extraction."""
    # Validate content type
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files supported")

    # Read and validate size
    content = await file.read()
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.MAX_FILE_SIZE_MB}MB limit",
        )

    # Check Temporal availability
    temporal = getattr(request.app.state, "temporal", None)
    if temporal is None:
        raise HTTPException(status_code=503, detail="Extraction service unavailable")

    # Create document record
    document_id = str(uuid4())
    object_key = f"{document_id}.pdf"
    doc = Document(
        id=document_id,
        filename=file.filename or "unnamed.pdf",
        content_type=file.content_type,
        file_size=len(content),
        object_key=object_key,
        bucket=settings.S3_BUCKET_UPLOADS,
        status=DocumentStatus.pending,
    )
    db.add(doc)
    await db.commit()

    # Upload to MinIO
    storage = get_storage()
    storage.put_bytes(
        settings.S3_BUCKET_UPLOADS,
        object_key,
        content,
        content_type="application/pdf",
    )

    # Start extraction workflow
    await temporal.start_workflow(
        ExtractionWorkflow.run,
        document_id,
        id=f"extraction-{document_id}",
        task_queue=settings.WORKER_TASK_QUEUE,
    )

    logger.info("Started extraction workflow for document %s", document_id)

    return {
        "document_id": document_id,
        "filename": file.filename,
        "status": "pending",
    }
