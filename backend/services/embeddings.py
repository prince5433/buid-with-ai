"""
Embeddings & ChromaDB Vector Store Service.

Handles text chunking, embedding generation, and vector storage/retrieval.
"""

import logging
import re
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)


class EmbeddingsService:
    """Manages document embeddings and ChromaDB vector store."""

    COLLECTION_NAME = "document_chunks"

    def __init__(self):
        self._model = None
        self._client = None
        self._collection = None

    def _get_model(self):
        """Lazy-load the embedding model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {settings.embedding_model}")
            self._model = SentenceTransformer(settings.embedding_model)
            logger.info("Embedding model loaded successfully")
        return self._model

    def _get_collection(self):
        """Get or create the ChromaDB collection."""
        if self._collection is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            self._client = chromadb.PersistentClient(
                path=str(settings.chroma_path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"ChromaDB collection '{self.COLLECTION_NAME}' ready with {self._collection.count()} chunks")
        return self._collection

    def chunk_text(
        self,
        text: str,
        chunk_size: int = None,
        chunk_overlap: int = None,
    ) -> list[str]:
        """
        Split text into overlapping chunks.
        
        Uses sentence-aware splitting to avoid breaking mid-sentence.
        """
        chunk_size = chunk_size or settings.chunk_size
        chunk_overlap = chunk_overlap or settings.chunk_overlap

        if not text or not text.strip():
            return []

        # Split into sentences first
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = []
        current_length = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_length = len(sentence.split())

            if current_length + sentence_length > chunk_size and current_chunk:
                # Save current chunk
                chunk_text = " ".join(current_chunk)
                if chunk_text.strip():
                    chunks.append(chunk_text.strip())

                # Keep overlap
                overlap_words = []
                overlap_length = 0
                for s in reversed(current_chunk):
                    words = s.split()
                    if overlap_length + len(words) <= chunk_overlap:
                        overlap_words.insert(0, s)
                        overlap_length += len(words)
                    else:
                        break

                current_chunk = overlap_words
                current_length = overlap_length

            current_chunk.append(sentence)
            current_length += sentence_length

        # Don't forget the last chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            if chunk_text.strip():
                chunks.append(chunk_text.strip())

        return chunks

    def add_document(
        self,
        document_id: str,
        document_name: str,
        pages: list[dict],  # List of {"page_number": int, "text": str}
    ) -> int:
        """
        Chunk, embed, and store document pages in ChromaDB.
        
        Returns the number of chunks added.
        """
        model = self._get_model()
        collection = self._get_collection()

        all_chunks = []
        all_ids = []
        all_metadatas = []

        for page in pages:
            page_num = page["page_number"]
            text = page.get("text", "")

            if not text or not text.strip():
                continue

            chunks = self.chunk_text(text)

            for i, chunk in enumerate(chunks):
                chunk_id = f"{document_id}_p{page_num}_c{i}"
                all_chunks.append(chunk)
                all_ids.append(chunk_id)
                all_metadatas.append({
                    "document_id": document_id,
                    "document_name": document_name,
                    "page_number": page_num,
                    "chunk_index": i,
                })

        if not all_chunks:
            logger.warning(f"No text chunks to index for document {document_name}")
            return 0

        # Generate embeddings
        logger.info(f"Generating embeddings for {len(all_chunks)} chunks from {document_name}")
        embeddings = model.encode(all_chunks, show_progress_bar=False).tolist()

        # Store in ChromaDB (batch to avoid limits)
        batch_size = 100
        for start in range(0, len(all_chunks), batch_size):
            end = min(start + batch_size, len(all_chunks))
            collection.add(
                ids=all_ids[start:end],
                embeddings=embeddings[start:end],
                documents=all_chunks[start:end],
                metadatas=all_metadatas[start:end],
            )

        logger.info(f"Indexed {len(all_chunks)} chunks for {document_name}")
        return len(all_chunks)

    def query(
        self,
        query_text: str,
        n_results: int = 8,
        document_ids: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Query the vector store for relevant chunks.
        
        Returns list of {text, document_name, document_id, page_number, score}
        """
        model = self._get_model()
        collection = self._get_collection()

        if collection.count() == 0:
            return []

        # Generate query embedding
        query_embedding = model.encode([query_text]).tolist()

        # Build where filter if document_ids provided
        where_filter = None
        if document_ids:
            if len(document_ids) == 1:
                where_filter = {"document_id": document_ids[0]}
            else:
                where_filter = {"document_id": {"$in": document_ids}}

        # Query ChromaDB
        try:
            results = collection.query(
                query_embeddings=query_embedding,
                n_results=min(n_results, collection.count()),
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error(f"ChromaDB query failed: {e}")
            return []

        # Format results
        formatted = []
        if results and results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i]
                distance = results["distances"][0][i]
                # Convert cosine distance to similarity score
                score = 1 - distance

                formatted.append({
                    "text": doc,
                    "document_name": meta.get("document_name", "Unknown"),
                    "document_id": meta.get("document_id", ""),
                    "page_number": meta.get("page_number", 0),
                    "score": round(score, 4),
                })

        # Sort by relevance score descending
        formatted.sort(key=lambda x: x["score"], reverse=True)
        return formatted

    def delete_document(self, document_id: str):
        """Remove all chunks for a document from the vector store."""
        collection = self._get_collection()
        try:
            # Get all chunk IDs for this document
            results = collection.get(
                where={"document_id": document_id},
                include=[],
            )
            if results and results["ids"]:
                collection.delete(ids=results["ids"])
                logger.info(f"Deleted {len(results['ids'])} chunks for document {document_id}")
        except Exception as e:
            logger.error(f"Failed to delete document chunks: {e}")

    def get_stats(self) -> dict:
        """Get vector store statistics."""
        collection = self._get_collection()
        return {
            "total_chunks": collection.count(),
            "collection_name": self.COLLECTION_NAME,
        }


# Singleton
embeddings_service = EmbeddingsService()
