"""
Automated Verification of Project Workspace Isolation and Prevention of Cross-Project Contamination.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

import shutil
import tempfile
import pytest
from src.core.chunking import ContextAwareChunker
from src.core.ingestion import DocumentIngestionEngine
from src.core.vector_store import IsolatedVectorStore


@pytest.fixture
def isolated_env():
    temp_dir = tempfile.mkdtemp()
    store = IsolatedVectorStore(persist_dir=temp_dir)
    ingestion = DocumentIngestionEngine()
    chunker = ContextAwareChunker()
    yield store, ingestion, chunker
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_cross_project_isolation_zero_leakage(isolated_env):
    store, ingestion, chunker = isolated_env

    # 1. Ingest proprietary doc into Project A
    doc_a_text = """
    OEM-A Proprietary Specification:
    DID 0x2001 is used for Powertrain Torque Offset calibration in Extended Session.
    Requires Security Access Level 1 seed key authentication.
    """
    doc_a = ingestion.ingest_text(
        text=doc_a_text,
        filename="oem_a_powertrain.txt",
        project_id="project_alpha"
    )
    chunks_a = chunker.chunk_document(doc_a)
    store.add_chunks(project_id="project_alpha", chunks=chunks_a)

    # 2. Ingest proprietary doc into Project B
    doc_b_text = """
    OEM-B Proprietary Specification:
    DID 0x4002 is used for Radar Sensor RadarAngle calibration in Safety Session.
    Service 0x31 Routine 0x0501 resets the radar alignment.
    """
    doc_b = ingestion.ingest_text(
        text=doc_b_text,
        filename="oem_b_radar.txt",
        project_id="project_beta"
    )
    chunks_b = chunker.chunk_document(doc_b)
    store.add_chunks(project_id="project_beta", chunks=chunks_b)

    # Verify counts in each isolated collection
    assert store.count_chunks("project_alpha") == len(chunks_a)
    assert store.count_chunks("project_beta") == len(chunks_b)

    # 3. Query Project Alpha for Project B terms
    citations_in_alpha = store.query(
        project_id="project_alpha",
        query_text="Radar Sensor RadarAngle 0x4002 calibration"
    )
    # NONE of the citations in Project Alpha can belong to Project Beta
    for c in citations_in_alpha:
        assert c.project_id == "project_alpha"
        assert "Radar" not in c.text_snippet
        assert c.document_name == "oem_a_powertrain.txt"

    # 4. Query Project Beta for Project A terms
    citations_in_beta = store.query(
        project_id="project_beta",
        query_text="Powertrain Torque Offset 0x2001 calibration"
    )
    # NONE of the citations in Project Beta can belong to Project Alpha
    for c in citations_in_beta:
        assert c.project_id == "project_beta"
        assert "Powertrain" not in c.text_snippet
        assert c.document_name == "oem_b_radar.txt"
