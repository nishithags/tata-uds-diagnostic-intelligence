"""
Unit tests for Context-Aware Document Chunking.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

import pytest
from src.core.chunking import ContextAwareChunker
from src.core.ingestion import IngestedDocument, PageContent


@pytest.fixture
def chunker():
    return ContextAwareChunker(chunk_size_chars=300, overlap_chars=50)


def test_chunking_metadata_propagation(chunker):
    sample_doc = IngestedDocument(
        doc_id="doc_abc1234567890",
        project_id="ws_bcm_test",
        filename="bcm_diagnostic_spec.pdf",
        file_type="PDF",
        file_size_bytes=1024,
        file_hash_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        total_pages=2,
        pages=[
            PageContent(
                page_number=1,
                text="1. Scope\nThis section defines the scope of BCM diagnostics.\n\n2. Service 0x10\nSession control rules.",
                detected_sections=["1. Scope", "2. Service 0x10"]
            ),
            PageContent(
                page_number=2,
                text="3. Service 0x22 ReadDataByIdentifier\nDefines reading DID parameters for VIN and ECU Software ID.",
                detected_sections=["3. Service 0x22 ReadDataByIdentifier"]
            )
        ],
        ingested_at="2026-09-30T12:00:00Z"
    )

    chunks = chunker.chunk_document(sample_doc)
    assert len(chunks) >= 2

    for c in chunks:
        assert c.doc_id == sample_doc.doc_id
        assert c.project_id == sample_doc.project_id
        assert c.document_name == sample_doc.filename
        assert c.source_hash_sha256 == sample_doc.file_hash_sha256
        assert c.page_number in (1, 2)
        assert c.chunk_id.startswith(sample_doc.doc_id)
        assert len(c.content) > 0


def test_chunk_size_adherence(chunker):
    long_text = "This is a detailed paragraph discussing UDS security access seed key algorithms. " * 10
    sample_doc = IngestedDocument(
        doc_id="doc_size_test",
        project_id="ws_test",
        filename="long_spec.txt",
        file_type="TEXT",
        file_size_bytes=len(long_text),
        file_hash_sha256="hash123",
        total_pages=1,
        pages=[PageContent(page_number=1, text=long_text)]
    )

    chunks = chunker.chunk_document(sample_doc)
    assert len(chunks) > 1
    # Check that chunks do not excessively exceed chunk_size + overlap
    for c in chunks:
        assert c.char_count <= 450
