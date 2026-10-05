"""
Vector Storage & Retrieval Module for Phase 1 Knowledge Pilot.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Implementation Choice Notice:
- ChromaDB is used here as an implementation choice for local persistent vector storage
  per the company reference options (Reference Solution Document, Page 22:
  'FAISS or ChromaDB; Milvus or self-hosted Weaviate for scale').
  It is an implementation choice for the pilot, NOT a company-mandated technology.
- ChromaDB default embedding function is explicitly FORBIDDEN and NOT used.
  All embeddings are computed explicitly using the project's configured BaseEmbeddingService.
- Project/Workspace collections are strictly isolated to prevent cross-project contamination.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import chromadb
from chromadb.config import Settings

from src.core.config import config
from src.core.chunking import DocumentChunk
from src.core.embeddings import BaseEmbeddingService, EmbeddingServiceFactory


class Citation(BaseModel):
    """
    Formal citation structure returned by the retrieval engine.
    Allows exact verification of where retrieved diagnostic knowledge originated.
    """
    chunk_id: str
    doc_id: str
    project_id: str
    document_name: str
    page_number: int
    section_title: str
    text_snippet: str
    relevance_score: float  # Cosine similarity score [0.0, 1.0]
    distance: float
    source_hash_sha256: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IsolatedVectorStore:
    """
    Manages workspace-isolated ChromaDB vector collections.
    Enforces strict metadata partitioning and explicit vector generation.
    """

    def __init__(self, persist_dir: Optional[str] = None, embedding_service: Optional[BaseEmbeddingService] = None):
        self.persist_dir = persist_dir or str(config.vector_store_dir)
        self.embedding_service = embedding_service or EmbeddingServiceFactory.create()
        
        # Initialize ChromaDB persistent client
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )

    def _sanitize_collection_name(self, project_id: str) -> str:
        """ChromaDB collection names must be 3-63 chars, alphanumeric, underscores, hyphens."""
        clean = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in project_id)
        if len(clean) < 3:
            clean = f"ws_{clean}"
        return f"coll_{clean[:55]}"

    def get_or_create_collection(self, project_id: str):
        """
        Retrieves or creates a dedicated collection for a project workspace.
        Ensures NO default embedding function is assigned (we pass explicit embeddings).
        """
        collection_name = self._sanitize_collection_name(project_id)
        return self.client.get_or_create_collection(
            name=collection_name,
            metadata={
                "project_id": project_id,
                "embedding_model": self.embedding_service.model_name,
                "dimension": self.embedding_service.dimension
            }
        )

    def add_chunks(self, project_id: str, chunks: List[DocumentChunk]) -> int:
        """
        Embeds and stores document chunks in the project's isolated collection.
        Embeddings are generated explicitly via the configured BaseEmbeddingService.
        """
        if not chunks:
            return 0

        collection = self.get_or_create_collection(project_id)

        chunk_ids = [c.chunk_id for c in chunks]
        texts = [c.content for c in chunks]
        metadatas = [
            {
                "doc_id": c.doc_id,
                "project_id": c.project_id,
                "document_name": c.document_name,
                "page_number": c.page_number,
                "section_title": c.section_title or "General",
                "char_count": c.char_count,
                "source_hash_sha256": c.source_hash_sha256
            }
            for c in chunks
        ]

        # Explicitly compute embeddings using the approved service
        embeddings = self.embedding_service.embed_texts(texts)

        # Upsert into isolated ChromaDB collection
        collection.upsert(
            ids=chunk_ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
        return len(chunks)

    def query(self, project_id: str, query_text: str, top_k: int = 5) -> List[Citation]:
        """
        Performs semantic search strictly within the specified project workspace.
        Returns ranked citations with relevance scores, exact source page, section, and text snippet.
        """
        if not query_text or not query_text.strip():
            return []

        collection = self.get_or_create_collection(project_id)
        
        # Verify collection has entries
        count = collection.count()
        if count == 0:
            return []

        # Explicitly compute query embedding
        query_vector = self.embedding_service.embed_query(query_text)

        # Query isolated collection, filtering strictly by project_id
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, count),
            where={"project_id": project_id},
            include=["documents", "metadatas", "distances"]
        )

        citations: List[Citation] = []
        if not results or not results["ids"] or not results["ids"][0]:
            return citations

        ids = results["ids"][0]
        docs = results["documents"][0] if results.get("documents") else [""] * len(ids)
        metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(ids)
        distances = results["distances"][0] if results.get("distances") else [0.0] * len(ids)

        for chunk_id, text, meta, dist in zip(ids, docs, metas, distances):
            # Chroma default L2 distance to cosine-similarity conversion:
            # For normalized vectors, cosine distance = 1 - cosine_similarity = (L2_dist^2)/2
            # Or bounded relevance score = max(0.0, 1.0 - (dist / 2.0))
            relevance = max(0.0, min(1.0, 1.0 - (dist / 2.0)))

            citations.append(
                Citation(
                    chunk_id=chunk_id,
                    doc_id=meta.get("doc_id", ""),
                    project_id=meta.get("project_id", project_id),
                    document_name=meta.get("document_name", "Unknown Document"),
                    page_number=int(meta.get("page_number", 1)),
                    section_title=meta.get("section_title", "General"),
                    text_snippet=text,
                    relevance_score=round(relevance, 4),
                    distance=round(dist, 4),
                    source_hash_sha256=meta.get("source_hash_sha256", ""),
                    metadata=meta
                )
            )

        # Sort descending by relevance score
        citations.sort(key=lambda c: c.relevance_score, reverse=True)
        return citations

    def count_chunks(self, project_id: str) -> int:
        """Returns the total number of chunks stored for a project workspace."""
        collection = self.get_or_create_collection(project_id)
        return collection.count()

    def delete_project_collection(self, project_id: str) -> None:
        """Deletes all indexed vectors for a workspace upon project deletion."""
        collection_name = self._sanitize_collection_name(project_id)
        try:
            self.client.delete_collection(name=collection_name)
        except Exception:
            pass
