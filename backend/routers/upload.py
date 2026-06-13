"""
Upload Router.

Handles file uploads, processing pipeline, and status tracking.
"""

import uuid
import asyncio
import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from models.database import get_db, Document, Page
from models.schemas import UploadResponse, DocumentStatus
from security.file_validation import validate_file
from security.middleware import sanitize_filename
from services.parser import parser
from services.classifier import classifier
from services.embeddings import embeddings_service
from services.storage import storage_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["upload"])

# In-memory status tracking for real-time updates
_processing_status: dict[str, dict] = {}
_ws_connections: dict[str, list[WebSocket]] = {}


async def notify_status(task_id: str, file_id: str, status: str, error: str = None, classification: dict = None):
    """Send status update to connected WebSocket clients."""
    _processing_status.setdefault(task_id, {})[file_id] = {
        "status": status,
        "error": error,
        "classification": classification,
    }

    # Broadcast to WebSocket clients
    if task_id in _ws_connections:
        message = {
            "task_id": task_id,
            "file_id": file_id,
            "status": status,
            "error": error,
            "classification": classification,
        }
        dead_connections = []
        for ws in _ws_connections[task_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.append(ws)

        for ws in dead_connections:
            _ws_connections[task_id].remove(ws)


async def process_document(
    file_data: bytes,
    filename: str,
    mime_type: str,
    doc_id: str,
    task_id: str,
    db: Session,
):
    """Full processing pipeline for a single document."""
    try:
        # === Stage 1: Store encrypted file ===
        await notify_status(task_id, doc_id, "uploading")
        stored_filename, file_hash = storage_service.store_document(file_data, filename)

        # Update DB
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.stored_filename = stored_filename
            doc.file_hash = file_hash
            doc.status = "parsing"
            db.commit()

        # === Stage 2: Parse document ===
        await notify_status(task_id, doc_id, "parsing")
        parsed = await asyncio.to_thread(
            parser.parse, file_data, mime_type, filename
        )

        # Store pages and images
        has_any_tables = False
        page_data_for_indexing = []

        for parsed_page in parsed.pages:
            # Store page image
            image_filename = None
            if parsed_page.image_bytes:
                image_filename = storage_service.store_page_image(
                    parsed_page.image_bytes, doc_id, parsed_page.page_number
                )

            # Create page record
            page = Page(
                document_id=doc_id,
                page_number=parsed_page.page_number,
                extracted_text=parsed_page.text,
                has_tables=parsed_page.has_tables,
                table_data=parsed_page.table_data,
                image_filename=image_filename,
            )
            db.add(page)

            if parsed_page.has_tables:
                has_any_tables = True

            page_data_for_indexing.append({
                "page_number": parsed_page.page_number,
                "text": parsed_page.text,
            })

        # Update document page count
        if doc:
            doc.page_count = len(parsed.pages)
            doc.status = "classifying"
            db.commit()

        # === Stage 3: Classify document ===
        await notify_status(task_id, doc_id, "classifying")
        all_text = "\n\n".join(p.text for p in parsed.pages if p.text)
        classification_result = await asyncio.to_thread(
            classifier.classify,
            text_content=all_text,
            filename=filename,
            page_count=len(parsed.pages),
            has_tables=has_any_tables,
        )

        if doc:
            doc.classification = classification_result
            doc.status = "indexing"
            db.commit()

        # === Stage 4: Index in vector store ===
        await notify_status(task_id, doc_id, "indexing")
        chunks_added = await asyncio.to_thread(
            embeddings_service.add_document,
            document_id=doc_id,
            document_name=filename,
            pages=page_data_for_indexing,
        )

        # === Done ===
        if doc:
            doc.status = "ready"
            doc.updated_at = datetime.now(timezone.utc)
            db.commit()

        await notify_status(task_id, doc_id, "ready", classification=classification_result)
        logger.info(f"Document {filename} processed successfully ({chunks_added} chunks indexed)")

    except Exception as e:
        logger.error(f"Document processing failed for {filename}: {e}")
        try:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                doc.status = "error"
                doc.error_message = str(e)[:500]
                db.commit()
        except Exception:
            pass
        await notify_status(task_id, doc_id, "error", error=str(e)[:500])


@router.post("/upload", response_model=UploadResponse)
async def upload_files(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Upload one or more documents for processing."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 files per upload")

    task_id = str(uuid.uuid4())
    file_infos = []

    for file in files:
        # Validate file
        file_data, detected_mime = await validate_file(file)
        safe_filename = sanitize_filename(file.filename)

        # Create document record
        doc = Document(
            original_filename=safe_filename,
            stored_filename="",  # Will be set during processing
            file_hash="",  # Will be set during processing
            mime_type=detected_mime,
            file_size=len(file_data),
            status="uploading",
        )
        db.add(doc)
        db.flush()  # Get the ID

        file_infos.append({
            "id": doc.id,
            "filename": safe_filename,
            "size": len(file_data),
            "mime_type": detected_mime,
            "status": "uploading",
        })

        # Start async processing
        asyncio.create_task(
            process_document(file_data, safe_filename, detected_mime, doc.id, task_id, db)
        )

    db.commit()

    return UploadResponse(
        task_id=task_id,
        files=file_infos,
        message=f"Processing {len(files)} file(s)",
    )


@router.get("/upload/status/{task_id}")
async def get_upload_status(task_id: str):
    """Get processing status for an upload task."""
    if task_id in _processing_status:
        return {"task_id": task_id, "files": _processing_status[task_id]}
    return {"task_id": task_id, "files": {}}


@router.websocket("/ws/upload-status/{task_id}")
async def websocket_upload_status(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time upload status updates."""
    await websocket.accept()

    _ws_connections.setdefault(task_id, []).append(websocket)

    try:
        # Send current status
        if task_id in _processing_status:
            await websocket.send_json({
                "type": "initial_status",
                "files": _processing_status[task_id],
            })

        # Keep connection alive
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                # Send ping to keep alive
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        if task_id in _ws_connections:
            _ws_connections[task_id] = [
                ws for ws in _ws_connections[task_id] if ws != websocket
            ]
