"""
Documents Router.

Handles document listing, page image retrieval, and document deletion.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from models.database import get_db, Document, Page
from models.schemas import DocumentListResponse, DocumentInfo
from services.storage import storage_service
from services.embeddings import embeddings_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(db: Session = Depends(get_db)):
    """List all documents with their classification and status."""
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    
    document_list = [
        DocumentInfo(
            id=doc.id,
            original_filename=doc.original_filename,
            file_size=doc.file_size,
            mime_type=doc.mime_type,
            status=doc.status,
            error_message=doc.error_message,
            classification=doc.classification,
            page_count=doc.page_count,
            created_at=doc.created_at.isoformat() if doc.created_at else None,
        )
        for doc in docs
    ]

    return DocumentListResponse(documents=document_list, total=len(document_list))


@router.get("/documents/{document_id}")
async def get_document(document_id: str, db: Session = Depends(get_db)):
    """Get detailed information about a specific document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    pages = (
        db.query(Page)
        .filter(Page.document_id == document_id)
        .order_by(Page.page_number)
        .all()
    )

    return {
        "document": doc.to_dict(),
        "pages": [p.to_dict() for p in pages],
    }


@router.get("/documents/{document_id}/pages/{page_number}/image")
async def get_page_image(document_id: str, page_number: int, db: Session = Depends(get_db)):
    """Serve a decrypted page image."""
    page = (
        db.query(Page)
        .filter(Page.document_id == document_id, Page.page_number == page_number)
        .first()
    )

    if not page or not page.image_filename:
        raise HTTPException(status_code=404, detail="Page image not found")

    try:
        image_data = storage_service.retrieve_page_image(page.image_filename)
        return Response(
            content=image_data,
            media_type="image/png",
            headers={
                "Cache-Control": "private, max-age=3600",
                "X-Content-Type-Options": "nosniff",
            },
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Page image file not found")
    except ValueError as e:
        logger.error(f"Image decryption failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve page image")


@router.get("/documents/{document_id}/pages/{page_number}/text")
async def get_page_text(document_id: str, page_number: int, db: Session = Depends(get_db)):
    """Get extracted text for a specific page."""
    page = (
        db.query(Page)
        .filter(Page.document_id == document_id, Page.page_number == page_number)
        .first()
    )

    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    return {
        "document_id": document_id,
        "page_number": page_number,
        "text": page.extracted_text or "",
        "has_tables": page.has_tables,
        "table_data": page.table_data,
    }


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, db: Session = Depends(get_db)):
    """Delete a document and all associated data."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from vector store
    embeddings_service.delete_document(document_id)

    # Delete files from storage
    storage_service.delete_document_files(doc.stored_filename, document_id)

    # Delete from database (cascades to pages)
    db.delete(doc)
    db.commit()

    logger.info(f"Deleted document: {doc.original_filename} ({document_id})")
    return {"message": f"Document '{doc.original_filename}' deleted successfully"}


@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get system statistics."""
    doc_count = db.query(Document).count()
    ready_count = db.query(Document).filter(Document.status == "ready").count()
    page_count = db.query(Page).count()
    
    vector_stats = embeddings_service.get_stats()
    storage_stats = storage_service.get_storage_stats()

    return {
        "documents": {
            "total": doc_count,
            "ready": ready_count,
            "pages": page_count,
        },
        "vector_store": vector_stats,
        "storage": storage_stats,
    }
