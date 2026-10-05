"""
Configuration and Environment Settings for Phase 1 Knowledge Pilot.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Preserves company reference options exactly as documented in Reference Solution Document (pp. 20-25).
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
WORKSPACES_DIR = DATA_DIR / "workspaces"
VECTOR_STORE_DIR = DATA_DIR / "chromadb"
DOCUMENTS_DIR = DATA_DIR / "uploaded_documents"
ACTIVITY_DIR = DATA_DIR / "activity"

# Ensure runtime directories exist
WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
ACTIVITY_DIR.mkdir(parents=True, exist_ok=True)


class KnowledgePilotConfig(BaseModel):
    """
    Knowledge Pilot Configuration.
    
    Documented Implementation Choices:
    - Vector Store: ChromaDB (explicitly listed on page 22: 'FAISS or ChromaDB; Milvus or self-hosted Weaviate for scale').
      Documented as an implementation choice for the pilot, NOT as a company-mandated technology.
    - Embeddings: Permitted options per reference document: 'BGE, E5, Sentence Transformers, or equivalent'.
      Default pilot provider uses the domain-aware equivalent vectorizer to guarantee zero-download air-gapped operation.
    - UI: Streamlit (pilot UI framework per reference document).
    - API: FastAPI (preferred API layer per reference document).
    - LLM: Pending formal user approval.
    """
    app_name: str = "Rule-Verified UDS Knowledge Pilot"
    app_version: str = "0.1.0-phase1"
    
    # Storage settings
    data_dir: Path = DATA_DIR
    workspaces_dir: Path = WORKSPACES_DIR
    vector_store_dir: Path = VECTOR_STORE_DIR
    documents_dir: Path = DOCUMENTS_DIR
    
    # Ingestion settings
    max_file_size_mb: int = 50
    allowed_extensions: list[str] = Field(default_factory=lambda: [".pdf", ".txt", ".md"])
    
    # Chunking settings
    chunk_size_chars: int = 800
    chunk_overlap_chars: int = 150
    
    # Embedding settings
    # Permitted reference options: 'bge', 'e5', 'sentence_transformers', 'domain_equivalent'
    embedding_provider: str = "domain_equivalent"
    embedding_dim: int = 128
    
    # API settings
    api_host: str = Field(default_factory=lambda: os.getenv("UDS_API_HOST", "127.0.0.1"))
    api_port: int = Field(default_factory=lambda: int(os.getenv("UDS_API_PORT", "8000")))
    api_url: str = Field(default_factory=lambda: os.getenv("UDS_API_URL", "http://127.0.0.1:8000"))
    
    # Streamlit settings
    streamlit_port: int = Field(default_factory=lambda: int(os.getenv("UDS_STREAMLIT_PORT", "8501")))
    
    # Activity & Privacy settings
    activity_dir: Path = ACTIVITY_DIR
    activity_db_path: Path = ACTIVITY_DIR / "activity_store.db"
    log_client_ip: bool = Field(default_factory=lambda: os.getenv("UDS_LOG_CLIENT_IP", "false").lower() in ("true", "1", "yes"))
    anonymize_ip: bool = Field(default_factory=lambda: os.getenv("UDS_ANONYMIZE_IP", "true").lower() in ("true", "1", "yes"))
    admin_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("UDS_ADMIN_KEY") or None)


config = KnowledgePilotConfig()
