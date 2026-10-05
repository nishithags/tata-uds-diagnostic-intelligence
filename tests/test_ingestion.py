"""
Unit tests for Document Ingestion and Parsing.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

import io
import pypdf
import pytest
from src.core.ingestion import DocumentIngestionEngine, IngestionError


@pytest.fixture
def engine():
    return DocumentIngestionEngine(max_size_mb=10)


def create_sample_pdf(content_pages: list[str]) -> bytes:
    """Helper to generate an in-memory valid PDF for testing."""
    writer = pypdf.PdfWriter()
    for text in content_pages:
        page = writer.add_blank_page(width=612, height=792)
        # In pypdf, add_blank_page creates a blank page; for text testing we can write text stream or use writer
    # Actually pypdf PdfWriter can write pages or text, or we can use a helper
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_compute_sha256(engine):
    data = b"ISO 14229-1 Diagnostic Specification"
    h1 = engine.compute_sha256(data)
    h2 = engine.compute_sha256(data)
    assert h1 == h2
    assert len(h1) == 64


def test_ingest_text_metadata_and_provenance(engine):
    sample_text = """
1. Diagnostic Session Control (0x10)
This service enables distinct diagnostic sessions in the server.

Table 1: Session Control Subfunctions
| Subfunction | Description |
| 0x01 | Default Session |
| 0x02 | Programming Session |
| 0x03 | Extended Diagnostic Session |
    """
    doc = engine.ingest_text(
        text=sample_text,
        filename="uds_spec_sample.txt",
        project_id="test_project_1",
        metadata={"category": "STANDARD"}
    )

    assert doc.doc_id.startswith("doc_")
    assert doc.project_id == "test_project_1"
    assert doc.filename == "uds_spec_sample.txt"
    assert doc.file_type == "TEXT/MD"
    assert doc.total_pages == 1
    assert len(doc.file_hash_sha256) == 64
    assert len(doc.pages) == 1
    assert "Diagnostic Session Control" in doc.pages[0].text
    assert len(doc.pages[0].tables) >= 1
    table = doc.pages[0].tables[0]
    assert "Subfunction" in table.headers or "0x01" in str(table.rows)


def test_section_detection(engine):
    sample_text = """
1. Scope
This document specifies UDS services.

2. Normative References
ISO 14229-1 and ISO 15765-2.

9.2 Service 0x22 ReadDataByIdentifier
Used to read DIDs.
    """
    doc = engine.ingest_text(
        text=sample_text,
        filename="sections_test.md",
        project_id="test_proj"
    )
    detected = doc.pages[0].detected_sections
    assert any("Scope" in s for s in detected)
    assert any("Service 0x22" in s for s in detected)
