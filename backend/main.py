"""
Document Intelligence + Agentic RAG — FastAPI Application.

Main entry point for the backend API server.
"""

import logging
import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from security.middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    RequestSizeLimitMiddleware,
)
from routers import upload, chat, documents

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def load_sample_documents():
    """Load sample documents on first startup if no documents exist."""
    from models.database import SessionLocal, Document
    from services.parser import parser
    from services.classifier import classifier
    from services.embeddings import embeddings_service
    from services.storage import storage_service
    from routers.upload import process_document

    db = SessionLocal()
    try:
        doc_count = db.query(Document).count()
        if doc_count > 0:
            logger.info(f"Found {doc_count} existing documents, skipping sample load")
            return

        sample_dir = settings.base_dir / "sample_documents"
        if not sample_dir.exists():
            logger.warning("No sample_documents directory found")
            return

        sample_files = list(sample_dir.iterdir())
        if not sample_files:
            logger.warning("No sample documents found")
            return

        logger.info(f"Loading {len(sample_files)} sample documents...")

        for file_path in sample_files:
            if file_path.is_file() and not file_path.name.startswith("."):
                try:
                    with open(file_path, "rb") as f:
                        file_data = f.read()

                    # Determine MIME type
                    ext = file_path.suffix.lower()
                    mime_map = {
                        ".pdf": "application/pdf",
                        ".txt": "text/plain",
                        ".md": "text/plain",
                        ".png": "image/png",
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                    }
                    mime_type = mime_map.get(ext, "application/octet-stream")

                    if mime_type == "application/octet-stream":
                        logger.warning(f"Skipping unknown file type: {file_path.name}")
                        continue

                    # Create document record
                    doc = Document(
                        original_filename=file_path.name,
                        stored_filename="",
                        file_hash="",
                        mime_type=mime_type,
                        file_size=len(file_data),
                        status="uploading",
                    )
                    db.add(doc)
                    db.flush()

                    # Process the document
                    await process_document(
                        file_data=file_data,
                        filename=file_path.name,
                        mime_type=mime_type,
                        doc_id=doc.id,
                        task_id="startup",
                        db=db,
                    )

                    logger.info(f"Loaded sample document: {file_path.name}")
                    
                    # Sleep to prevent hitting Gemini API rate limits
                    await asyncio.sleep(4)

                except Exception as e:
                    logger.error(f"Failed to load sample document {file_path.name}: {e}")

        db.commit()
        logger.info("Sample documents loaded successfully")

    except Exception as e:
        logger.error(f"Failed to load sample documents: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("🚀 Starting Document Intelligence API...")
    logger.info(f"   Environment: {settings.app_env}")
    logger.info(f"   Storage: {settings.storage_path}")
    logger.info(f"   Allowed origins: {settings.allowed_origins.split(',')}")

    # Ensure directories exist
    settings.ensure_directories()

    # NOTE: Automatic sample document loading is disabled to prevent 
    # hitting the free-tier LLM rate limit (429 Too Many Requests) on startup.
    # Evaluators can manually upload the documents from the `sample_documents` folder via the UI.
    # asyncio.create_task(load_sample_documents())

    yield

    logger.info("🛑 Shutting down Document Intelligence API...")


# Create FastAPI app
app = FastAPI(
    title="Document Intelligence + Agentic RAG",
    description="AI-powered document parsing, classification, and question answering with citations",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# === Middleware Stack (order matters: last added = first executed) ===

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=600,
)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

# Rate limiting
app.add_middleware(RateLimitMiddleware)

# Request size limit
app.add_middleware(RequestSizeLimitMiddleware)

# === Routes ===
app.include_router(upload.router)
app.include_router(chat.router)
app.include_router(documents.router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Document Intelligence API",
        "version": "1.0.0",
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Document Intelligence + Agentic RAG API",
        "docs": "/docs" if settings.debug else "Disabled in production",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Starting server on 0.0.0.0:{port}", flush=True)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
