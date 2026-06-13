"""SQLAlchemy database models and session management."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from config import settings

DATABASE_URL = f"sqlite:///{settings.storage_path / 'docintel.db'}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency to get DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Document(Base):
    """Represents an uploaded document."""

    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    file_hash = Column(String(64), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)

    # Processing status
    status = Column(String(20), default="uploading")  # uploading, parsing, classifying, indexing, ready, error
    error_message = Column(Text, nullable=True)

    # Classification result (JSON)
    classification = Column(JSON, nullable=True)

    # Metadata
    page_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    pages = relationship("Page", back_populates="document", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "original_filename": self.original_filename,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "status": self.status,
            "error_message": self.error_message,
            "classification": self.classification,
            "page_count": self.page_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Page(Base):
    """Represents a single page of a document."""

    __tablename__ = "pages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_number = Column(Integer, nullable=False)

    # Content
    extracted_text = Column(Text, nullable=True)
    has_tables = Column(Boolean, default=False)
    table_data = Column(JSON, nullable=True)  # Extracted table data as JSON

    # Image storage
    image_filename = Column(String(255), nullable=True)

    # Relationships
    document = relationship("Document", back_populates="pages")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "page_number": self.page_number,
            "has_tables": self.has_tables,
            "text_length": len(self.extracted_text) if self.extracted_text else 0,
            "has_image": self.image_filename is not None,
        }


class ChatSession(Base):
    """Stores chat conversation history."""

    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """A single message in a chat conversation."""

    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(10), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    citations = Column(JSON, nullable=True)  # List of {doc_name, page_number}
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("ChatSession", back_populates="messages")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "citations": self.citations,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Create all tables
Base.metadata.create_all(bind=engine)
