"""
End-to-End Retrieval Pipeline Test:
Document -> Ingestion -> Chunks -> Embeddings -> Vector Store -> Query -> Cited Source.

Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

import shutil
import tempfile
import pytest
from src.core.chunking import ContextAwareChunker
from src.core.ingestion import DocumentIngestionEngine
from src.core.llm_interface import LLMClientFactory
from src.core.vector_store import IsolatedVectorStore


@pytest.fixture
def e2e_pipeline():
    temp_dir = tempfile.mkdtemp()
    store = IsolatedVectorStore(persist_dir=temp_dir)
    ingestion = DocumentIngestionEngine()
    chunker = ContextAwareChunker(chunk_size_chars=400, overlap_chars=50)
    llm = LLMClientFactory.get_client()
    yield store, ingestion, chunker, llm
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_end_to_end_diagnostic_retrieval(e2e_pipeline):
    store, ingestion, chunker, llm = e2e_pipeline
    project_id = "e2e_uds_bcm_verification"

    # 1. Authorize and ingest diagnostic specification
    spec_document = """
    Section 1. Scope and Architecture
    This document defines the UDS diagnostic interface for the Body Control Module.
    Standard ISO 14229-1 rules apply with OEM specific extensions.

    Section 2. Service 0x27 Security Access Protocol
    To unlock diagnostic programming or critical DID write operations, the tester must authenticate.
    Subfunction 0x01: RequestSeed is supported in Extended Session (0x03).
    The server responds with positive response 0x67 0x01 followed by a 4-byte random seed.

    Section 3. Key Validation and Negative Responses
    Subfunction 0x02: SendKey transmits the calculated key.
    If the key does not match the required mathematical transform, the server returns NRC 0x35 (InvalidKey).
    If the tester fails 3 consecutive authentication attempts, the ECU enforces NRC 0x36 (ExceededNumberOfAttempts)
    and locks further attempts for a minimum delay of 10 seconds.
    """

    # Ingestion step
    doc = ingestion.ingest_text(
        text=spec_document,
        filename="bcm_uds_security_spec.txt",
        project_id=project_id,
        metadata={"spec_version": "v2.1", "doc_type": "OEM_SPEC"}
    )
    assert doc.doc_id.startswith("doc_")
    assert len(doc.file_hash_sha256) == 64

    # Chunking step
    chunks = chunker.chunk_document(doc)
    assert len(chunks) >= 3

    # Embedding and vector storage step
    stored_count = store.add_chunks(project_id=project_id, chunks=chunks)
    assert stored_count == len(chunks)
    assert store.count_chunks(project_id) == stored_count

    # 2. Benchmark Query 1: Invalid key NRC retrieval
    q1 = "What NRC is returned if the security key is invalid for Service 0x27?"
    citations_q1 = store.query(project_id=project_id, query_text=q1, top_k=2)

    assert len(citations_q1) > 0
    top_c1 = citations_q1[0]
    # Check that retrieved citation explicitly contains the expected NRC rule
    assert "NRC 0x35" in top_c1.text_snippet or "InvalidKey" in top_c1.text_snippet
    assert top_c1.document_name == "bcm_uds_security_spec.txt"
    assert top_c1.page_number == 1
    assert top_c1.source_hash_sha256 == doc.file_hash_sha256
    assert top_c1.relevance_score > 0.0

    # 3. Benchmark Query 2: Seed request subfunction
    q2 = "Which subfunction is used to request a seed in Security Access 0x27?"
    citations_q2 = store.query(project_id=project_id, query_text=q2, top_k=2)

    assert len(citations_q2) > 0
    top_c2 = citations_q2[0]
    assert "0x01" in top_c2.text_snippet and ("RequestSeed" in top_c2.text_snippet or "Seed" in top_c2.text_snippet)

    # 4. Generate answer and verify evidence synthesis
    answer_res = llm.generate_answer(query=q1, citations=citations_q1)
    assert "NRC 0x35" in answer_res.answer or "InvalidKey" in answer_res.answer
    assert "PENDING_FORMAL_USER_APPROVAL" == answer_res.llm_decision_status
    assert len(answer_res.citations) == len(citations_q1)
