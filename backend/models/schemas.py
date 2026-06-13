"""Pydantic schemas for API request/response validation."""

from pydantic import BaseModel, Field
from typing import Optional


# === Upload Schemas ===

class UploadResponse(BaseModel):
    """Response after uploading files."""
    task_id: str
    files: list[dict]
    message: str


class DocumentStatus(BaseModel):
    """Status of a document being processed."""
    id: str
    filename: str
    status: str
    error: Optional[str] = None
    classification: Optional[dict] = None
    page_count: int = 0


# === Chat Schemas ===

class ChatRequest(BaseModel):
    """Chat message request."""
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = None


class Citation(BaseModel):
    """A citation reference in a chat response."""
    document_name: str
    page_number: int
    document_id: str
    relevance_score: float = 0.0


class ChatResponse(BaseModel):
    """Chat response with citations."""
    message: str
    citations: list[Citation] = []
    session_id: str


# === Document Schemas ===

class DocumentInfo(BaseModel):
    """Document information."""
    id: str
    original_filename: str
    file_size: int
    mime_type: str
    status: str
    error_message: Optional[str] = None
    classification: Optional[dict] = None
    page_count: int
    created_at: Optional[str] = None


class DocumentListResponse(BaseModel):
    """List of documents."""
    documents: list[DocumentInfo]
    total: int


# === Classification Schema ===

class ContentCharacteristics(BaseModel):
    """Content characteristics of a document."""
    has_tables: bool = False
    has_images: bool = False
    has_handwriting: bool = False
    is_scanned: bool = False
    has_charts: bool = False
    language: str = "en"
    page_count: int = 0


class ClassificationResult(BaseModel):
    """Structured classification result from LLM."""
    document_type: str = "other"
    topic: str = "other"
    content_characteristics: ContentCharacteristics = ContentCharacteristics()
    sensitivity_level: str = "internal"
    summary: str = ""
    key_entities: list[str] = []
    confidence_score: float = 0.0
