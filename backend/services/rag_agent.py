import json
import logging
from typing import Optional
from config import settings
from services.embeddings import embeddings_service
from services.llm_provider import llm_provider

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are DocIntel AI, a precise document question-answering assistant. You answer questions based STRICTLY on the provided context from the knowledge base.

CRITICAL RULES — VIOLATIONS ARE UNACCEPTABLE:
1. ONLY use information explicitly present in the provided context chunks to answer.
2. For EVERY factual claim you make, you MUST include an inline citation: [DocumentName, Page X].
3. If the context does not contain relevant information, respond exactly with:
   "I don't have enough information in my knowledge base to answer that question. The documents I have may not cover this topic."
4. NEVER fabricate, infer beyond the text, or hallucinate information not in the context.
5. If you are only partially sure, say so and cite what you can.
6. When presenting tabular data from the context, preserve the table structure.
7. When multiple documents discuss the same topic, synthesize and cite each source.
8. Be concise but thorough. Every statement of fact needs a citation.
9. If the question is a greeting or meta-question (like "hi", "what can you do?"), respond naturally without needing context."""


ROUTING_PROMPT = """You are a query router. Given a user message, determine if it requires document retrieval or is a simple conversational message.

User message: {message}

If the message is a greeting, small talk, or a question about your capabilities, respond with "conversation".
If the message asks about specific information that would be found in documents, respond with "retrieval".

Respond with ONLY one word: "conversation" or "retrieval"."""


class RAGAgent:
    """Multi-step RAG agent with routing, and citation generation."""

    def __init__(self):
        pass

    def _route_query(self, message: str) -> str:
        """Step 1: Determine if the query needs retrieval or is conversational."""
        try:
            response = llm_provider.generate_content(
                prompt=ROUTING_PROMPT.format(message=message),
                temperature=0.0,
                max_tokens=10,
            )
            route = response.strip().lower()
            if route in ("conversation", "retrieval"):
                return route
            return "retrieval"  # Default to retrieval
        except Exception as e:
            logger.warning(f"Routing failed: {e}, defaulting to retrieval")
            return "retrieval"

    def _generate_answer(
        self,
        question: str,
        relevant_chunks: list[dict],
        conversation_history: list[dict] = None,
    ) -> str:
        """Step 4: Generate answer with inline citations."""

        # Build context from relevant chunks
        context_parts = []
        for i, chunk in enumerate(relevant_chunks):
            context_parts.append(
                f"[Source: {chunk['document_name']}, Page {chunk['page_number']}]\n{chunk['text']}"
            )

        context = "\n\n---\n\n".join(context_parts)

        # Build conversation history
        history_text = ""
        if conversation_history:
            for msg in conversation_history[-6:]:  # Last 6 messages for context
                role = "User" if msg["role"] == "user" else "Assistant"
                history_text += f"{role}: {msg['content']}\n"

        prompt = f"""Based on the following context from the knowledge base, answer the user's question.
Include inline citations [DocumentName, Page X] for every factual claim.

CONTEXT:
{context}

{f"CONVERSATION HISTORY:{chr(10)}{history_text}" if history_text else ""}

USER QUESTION: {question}

ANSWER (with inline citations):"""

        try:
            response = llm_provider.generate_content(
                prompt=prompt,
                system_instruction=SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=2048,
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return "I apologize, but I encountered an error while generating the answer. Please try again."

    def _handle_conversation(self, message: str, conversation_history: list[dict] = None) -> str:
        """Handle conversational (non-retrieval) messages."""

        history_text = ""
        if conversation_history:
            for msg in conversation_history[-4:]:
                role = "User" if msg["role"] == "user" else "Assistant"
                history_text += f"{role}: {msg['content']}\n"

        prompt = f"""{f"Previous conversation:{chr(10)}{history_text}" if history_text else ""}
User: {message}

Respond naturally. You are a document Q&A assistant. If asked what you can do, explain that you can answer questions about uploaded documents with citations to specific pages."""

        try:
            response = llm_provider.generate_content(
                prompt=prompt,
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7,
                max_tokens=512,
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Conversation response failed: {e}")
            return "Hello! I'm your document assistant. Upload documents and ask me questions about them!"

    def process_query(
        self,
        message: str,
        conversation_history: list[dict] = None,
    ) -> dict:
        """
        Main entry point: Process a user query through the agentic RAG pipeline.
        
        Returns:
            {
                "answer": str,
                "citations": [{"document_name": str, "page_number": int, "document_id": str}],
                "route": str  # "conversation" or "retrieval"
            }
        """
        logger.info(f"Processing query: {message[:100]}...")

        # Step 1: Route the query
        route = self._route_query(message)
        logger.info(f"Query routed to: {route}")

        if route == "conversation":
            answer = self._handle_conversation(message, conversation_history)
            return {
                "answer": answer,
                "citations": [],
                "route": "conversation",
            }

        # Step 2: Retrieve relevant chunks
        retrieved_chunks = embeddings_service.query(message, n_results=15)

        if not retrieved_chunks:
            return {
                "answer": "I don't have any documents in my knowledge base yet. Please upload some documents first, and then I can answer your questions about them.",
                "citations": [],
                "route": "retrieval",
            }

        # Step 3: Select chunks (bypassing LLM grader to save API quota, using large context limit)
        relevant_chunks = []
        for chunk in retrieved_chunks[:10]:  # Take top 10 chunks directly (OpenAI handles big context well)
            relevant_chunks.append(chunk)

        if not relevant_chunks:
            return {
                "answer": "I searched through all documents in my knowledge base but couldn't find information relevant to your question. The uploaded documents may not cover this topic. Could you try rephrasing, or ask about one of the specific documents?",
                "citations": [],
                "route": "retrieval",
            }

        # Step 4: Generate answer with citations
        answer = self._generate_answer(message, relevant_chunks, conversation_history)

        # Extract unique citations
        seen_citations = set()
        citations = []
        for chunk in relevant_chunks:
            key = (chunk["document_id"], chunk["page_number"])
            if key not in seen_citations:
                seen_citations.add(key)
                citations.append({
                    "document_name": chunk["document_name"],
                    "page_number": chunk["page_number"],
                    "document_id": chunk["document_id"],
                    "relevance_score": chunk["score"],
                })

        # Sort citations by relevance
        citations.sort(key=lambda x: x["relevance_score"], reverse=True)

        return {
            "answer": answer,
            "citations": citations[:6],  # Limit to top 6 citations
            "route": "retrieval",
        }


# Singleton
rag_agent = RAGAgent()
