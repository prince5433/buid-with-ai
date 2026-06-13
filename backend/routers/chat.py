"""
Chat Router.

Handles chat messages with RAG-powered responses and citation tracking.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models.database import get_db, ChatSession, ChatMessage
from models.schemas import ChatRequest, ChatResponse, Citation
from security.middleware import sanitize_chat_input
from services.rag_agent import rag_agent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    """Process a chat message and return a RAG-powered response."""
    # Sanitize input
    message = sanitize_chat_input(request.message)
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Get or create session
    session_id = request.session_id
    if session_id:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            session = ChatSession(id=session_id)
            db.add(session)
            db.flush()
    else:
        session = ChatSession()
        db.add(session)
        db.flush()
        session_id = session.id

    # Get conversation history
    history = []
    if session:
        past_messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        history = [{"role": m.role, "content": m.content} for m in past_messages]

    # Save user message
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=message,
    )
    db.add(user_msg)
    db.flush()

    # Process with RAG agent
    try:
        result = rag_agent.process_query(
            message=message,
            conversation_history=history,
        )
    except Exception as e:
        logger.error(f"RAG processing failed: {e}")
        result = {
            "answer": "I'm sorry, I encountered an error while processing your question. Please try again.",
            "citations": [],
            "route": "error",
        }

    # Save assistant message
    assistant_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=result["answer"],
        citations=result["citations"],
    )
    db.add(assistant_msg)
    db.commit()

    # Build response
    citations = [
        Citation(
            document_name=c["document_name"],
            page_number=c["page_number"],
            document_id=c["document_id"],
            relevance_score=c.get("relevance_score", 0.0),
        )
        for c in result["citations"]
    ]

    return ChatResponse(
        message=result["answer"],
        citations=citations,
        session_id=session_id,
    )


@router.get("/chat/sessions")
async def list_sessions(db: Session = Depends(get_db)):
    """List all chat sessions."""
    sessions = db.query(ChatSession).order_by(ChatSession.created_at.desc()).limit(20).all()
    return {
        "sessions": [
            {
                "id": s.id,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "message_count": len(s.messages),
            }
            for s in sessions
        ]
    }


@router.get("/chat/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, db: Session = Depends(get_db)):
    """Get all messages in a chat session."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    return {
        "session_id": session_id,
        "messages": [m.to_dict() for m in messages],
    }
