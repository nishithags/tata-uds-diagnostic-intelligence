"""
Unit tests for Citation Metadata completeness and traceability verification.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

import shutil
import tempfile
import pytest
from src.core.chunking import ContextAwareChunker
from src.core.ingestion import DocumentIngestionEngine
from src.core.vector_store import IsolatedVectorStore


@pytest.fixture
def citation_env():
    temp_dir = tempfile.mkdtemp()
    store = IsolatedVectorStore(persist_dir=temp_dir)
    ingestion = DocumentIngestionEngine()
    chunker = ContextAwareChunker()
    yield store, ingestion, chunker
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_citation_fields_completeness(citation_env):
    store, ingestion, chunker = citation_env

    spec_text = """
    9.2.1 Service 0x22 ReadDataByIdentifier
    The ReadDataByIdentifier service allows the client to request data record values from the server
    identified by one or more dataIdentifiers (DIDs).
    
    Preconditions:
    Allowed in default and extended diagnostic sessions.
    If a requested DID is secured, NRC 0x33 (SecurityAccessDenied) shall be returned.
    """

    doc = ingestion.ingest_text(
        text=spec_text,
        filename="iso14229_service_0x22.txt",
        project_id="test_citation_proj"
    )
    chunks = chunker.chunk_document(doc)
    store.add_chunks(project_id="test_citation_proj", chunks=chunks)

    citations = store.query(
        project_id="test_citation_proj",
        query_text="ReadDataByIdentifier 0x22 NRC 0x33 security access",
        top_k=3
    )

    assert len(citations) >= 1
    top_c = citations[0]

    # Verify all 6 mandatory citation elements
    assert top_c.document_name == "iso14229_service_0x22.txt"
    assert top_c.page_number == 1
    assert "0x22" in top_c.section_title or "Service" in top_c.section_title or "General" in top_c.section_title
    assert "ReadDataByIdentifier" in top_c.text_snippet
    assert 0.0 <= top_c.relevance_score <= 1.0
    assert len(top_c.source_hash_sha256) == 64
    assert top_c.chunk_id.startswith(doc.doc_id)
