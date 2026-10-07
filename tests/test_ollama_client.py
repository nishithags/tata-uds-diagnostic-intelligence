"""
Unit tests for Ollama Local LLM Client and Graceful Fallback (AD-01 Option 1A).
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

from unittest.mock import MagicMock, patch
import json
import pytest

from src.core.llm_interface import (
    DOMAIN_KNOWLEDGE_MODE_LABEL,
    GROUNDED_DIAGNOSTIC_MODE_LABEL,
    LLMClientFactory,
    MockLLMClient,
    OUT_OF_SCOPE_MODE_LABEL,
    OllamaLLMClient,
    QAResponse,
    is_uds_domain_query,
)
from src.core.vector_store import Citation


def _make_sample_uds_citation() -> Citation:
    return Citation(
        chunk_id="chunk_01",
        doc_id="doc_01",
        project_id="test_proj",
        document_name="iso14229.txt",
        page_number=12,
        section_title="DiagnosticSessionControl",
        text_snippet="Service 0x10 subfunction 0x01 is default session.",
        relevance_score=0.95,
        distance=0.05,
        source_hash_sha256="abc123"
    )


def test_ollama_client_initialization():
    client = OllamaLLMClient(host="http://localhost:11434", model="llama3.1:8b")
    assert client.client_id == "ollama/llama3.1:8b"
    assert client.host == "http://localhost:11434"
    assert client.model == "llama3.1:8b"
    assert isinstance(client.mock_fallback, MockLLMClient)


def test_ollama_offline_fallback():
    # Force client to point to an unreachable port
    client = OllamaLLMClient(host="http://localhost:59999", timeout_seconds=0.1)
    assert client.is_available() is False

    citation = _make_sample_uds_citation()

    response = client.generate_answer(query="What is 0x10 subfunction 0x01?", citations=[citation])
    assert isinstance(response, QAResponse)
    assert response.is_mock_fallback is True
    assert response.generation_source == "FALLBACK_TEMPLATE_MOCK"
    assert response.qa_mode == "GROUNDED_DIAGNOSTIC"
    assert "NOTICE: Generated via Fallback Client" in response.disclaimer
    assert "0x10 subfunction 0x01 is default session" in response.answer


def test_ollama_mocked_online_success():
    client = OllamaLLMClient(host="http://localhost:11434")
    citation = _make_sample_uds_citation()

    mock_ollama_reply = json.dumps({"response": "According to ISO 14229, subfunction 0x01 is DefaultSession."}).encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.read.return_value = mock_ollama_reply
    mock_resp.__enter__.return_value = mock_resp

    with patch.object(client, "is_available", return_value=True):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            qa_res = client.generate_answer("What is subfunction 0x01?", [citation])
            assert qa_res.is_mock_fallback is False
            assert qa_res.generation_source == "LOCAL_OLLAMA_LLM"
            assert qa_res.qa_mode == "GROUNDED_DIAGNOSTIC"
            assert "DefaultSession" in qa_res.answer
            assert "Generated via approved Local Ollama LLM" in qa_res.disclaimer


def test_ollama_generate_raw_text_offline_and_online():
    client = OllamaLLMClient(host="http://localhost:59999", timeout_seconds=0.1)
    text, source, is_mock = client.generate_raw_text("Generate UDS test")
    assert is_mock is True
    assert source == "FALLBACK_TEMPLATE_MOCK"

    # Online mocked
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"response": "Raw generated text"}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch.object(client, "is_available", return_value=True):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            text_online, src_online, mock_online = client.generate_raw_text("Generate UDS test")
            assert mock_online is False
            assert src_online == "LOCAL_OLLAMA_LLM"
            assert text_online == "Raw generated text"


def test_factory_returns_ollama_client():
    client = LLMClientFactory.get_client()
    assert isinstance(client, OllamaLLMClient)


def test_uds_question_with_matching_evidence_grounded_diagnostic():
    """A & E. UDS question + matching evidence -> GROUNDED_DIAGNOSTIC with preserved citations and SHA-256 provenance."""
    client = MockLLMClient()
    rid_citation = Citation(
        chunk_id="chunk_rid_0201",
        doc_id="doc_oem_rid",
        project_id="test_proj",
        document_name="oem_rid_spec.txt",
        page_number=4,
        section_title="RoutineControl 0x31",
        text_snippet="RID 0x0201 requires Security Access Level 0x01 in Extended Diagnostic Session (0x03).",
        relevance_score=0.96,
        distance=0.04,
        source_hash_sha256="f00baa1234567890"
    )

    res = client.generate_answer(
        query="What security level is required for RID 0x0201?",
        citations=[rid_citation]
    )
    assert res.qa_mode == "GROUNDED_DIAGNOSTIC"
    assert res.mode_label == GROUNDED_DIAGNOSTIC_MODE_LABEL
    assert len(res.citations) == 1
    assert res.citations[0].document_name == "oem_rid_spec.txt"
    assert res.citations[0].page_number == 4
    assert res.citations[0].section_title == "RoutineControl 0x31"
    assert res.citations[0].source_hash_sha256 == "f00baa1234567890"
    assert "RID 0x0201 requires Security Access Level 0x01" in res.answer


def test_uds_question_no_matching_evidence_domain_knowledge():
    """B & G. UDS question + no matching evidence -> DOMAIN_KNOWLEDGE (online Ollama and safe offline fallback)."""
    # 1. Offline fallback path when Ollama is unavailable
    offline_client = OllamaLLMClient(host="http://localhost:59999", timeout_seconds=0.1)
    offline_res = offline_client.generate_answer(
        query="What does NRC 0x78 mean?",
        citations=[]
    )
    assert offline_res.qa_mode == "DOMAIN_KNOWLEDGE"
    assert offline_res.mode_label == DOMAIN_KNOWLEDGE_MODE_LABEL
    assert "DOMAIN_KNOWLEDGE" in offline_res.answer
    assert offline_res.citations == []
    assert offline_res.is_mock_fallback is True

    # 2. Online Ollama path
    online_client = OllamaLLMClient(host="http://localhost:11434")
    mock_ollama_reply = json.dumps({
        "response": "NRC 0x78 (requestCorrectlyReceived-ResponsePending) indicates the ECU received the request and is processing it."
    }).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = mock_ollama_reply
    mock_resp.__enter__.return_value = mock_resp

    with patch.object(online_client, "is_available", return_value=True):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            online_res = online_client.generate_answer(
                query="What does NRC 0x78 mean?",
                citations=[]
            )
            assert online_res.qa_mode == "DOMAIN_KNOWLEDGE"
            assert online_res.mode_label == DOMAIN_KNOWLEDGE_MODE_LABEL
            assert "DOMAIN_KNOWLEDGE" in online_res.answer
            assert "requestCorrectlyReceived-ResponsePending" in online_res.answer
            assert online_res.citations == []
            assert online_res.is_mock_fallback is False


def test_unrelated_general_question_out_of_scope():
    """C. Unrelated general question -> OUT_OF_SCOPE without invoking general-knowledge LLM generation or attaching citations."""
    uds_citation = _make_sample_uds_citation()
    mock_client = MockLLMClient()
    online_client = OllamaLLMClient(host="http://localhost:11434")

    unrelated_queries = [
        "What is the capital of India?",
        "What is Python programming language?",
        "Explain how a lithium-ion battery works.",
        "When did World War II end?",
    ]

    for q in unrelated_queries:
        assert is_uds_domain_query(q) is False
        res_mock = mock_client.generate_answer(query=q, citations=[uds_citation])
        assert res_mock.qa_mode == "OUT_OF_SCOPE"
        assert res_mock.mode_label == OUT_OF_SCOPE_MODE_LABEL
        assert "OUT_OF_SCOPE" in res_mock.answer
        assert res_mock.citations == []

        with patch.object(online_client, "is_available", return_value=True):
            with patch("urllib.request.urlopen") as mock_urlopen:
                res_online = online_client.generate_answer(query=q, citations=[uds_citation])
                assert res_online.qa_mode == "OUT_OF_SCOPE"
                assert res_online.citations == []
                mock_urlopen.assert_not_called()


def test_domain_knowledge_has_no_fake_diagnostic_citations():
    """D. DOMAIN_KNOWLEDGE response has no fake diagnostic citations even when vector store returns top-k unrelated chunks."""
    session_only_citation = _make_sample_uds_citation()
    mock_client = MockLLMClient()

    res_mock = mock_client.generate_answer(
        query="What does NRC 0x78 mean?",
        citations=[session_only_citation]
    )
    assert res_mock.qa_mode == "DOMAIN_KNOWLEDGE"
    assert res_mock.citations == []
    assert "iso14229.txt" not in res_mock.answer
    assert "abc123" not in res_mock.answer

    online_client = OllamaLLMClient(host="http://localhost:11434")
    mock_ollama_reply = json.dumps({"response": "NRC 0x78 means ResponsePending."}).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = mock_ollama_reply
    mock_resp.__enter__.return_value = mock_resp

    with patch.object(online_client, "is_available", return_value=True):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            res_online = online_client.generate_answer(
                query="What does NRC 0x78 mean?",
                citations=[session_only_citation]
            )
            assert res_online.qa_mode == "DOMAIN_KNOWLEDGE"
            assert res_online.citations == []
            assert "iso14229.txt" not in res_online.answer


def test_uploaded_specifications_are_not_boundary_of_uds_knowledge():
    """H. Verify the currently uploaded specifications do NOT limit what UDS questions are eligible for DOMAIN_KNOWLEDGE."""
    client = MockLLMClient()

    # Simulate a workspace whose uploaded spec only covers ECU Reset (0x11)
    ecu_reset_citation = Citation(
        chunk_id="chunk_reset",
        doc_id="doc_reset",
        project_id="test_proj",
        document_name="ecu_reset_only.txt",
        page_number=1,
        section_title="ECUReset 0x11",
        text_snippet="Service 0x11 ECUReset supports subfunction 0x01 hardReset.",
        relevance_score=0.70,
        distance=0.30,
        source_hash_sha256="deadbeef01"
    )

    eligible_uds_questions = [
        "What does NRC 0x78 mean?",
        "What is UDS service 0x10?",
        "What is the purpose of service 0x27?",
        "What is the difference between 0x22 and 0x2E?",
        "What is Diagnostic Session Control?",
        "What security level is required for RID 0x0201?",
    ]

    for q in eligible_uds_questions:
        assert is_uds_domain_query(q) is True
        res = client.generate_answer(query=q, citations=[ecu_reset_citation])
        assert res.qa_mode == "DOMAIN_KNOWLEDGE", f"Expected DOMAIN_KNOWLEDGE for query: {q}"
        assert res.citations == []

    # Also verify that even when 0x22 IS in an uploaded spec, comparing 0x22 and 0x2E
    # (when 0x2E is absent from the spec) routes to DOMAIN_KNOWLEDGE without partial/fake citations.
    read_did_citation = Citation(
        chunk_id="chunk_0x22",
        doc_id="doc_synth",
        project_id="tata_uds_pilot",
        document_name="synthetic_uds_spec.txt",
        page_number=1,
        section_title="3. Read Data By Identifier (Service 0x22)",
        text_snippet="The ReadDataByIdentifier service (0x22) allows the client to request DID values.",
        relevance_score=0.82,
        distance=0.18,
        source_hash_sha256="8d9660e8c1795039"
    )
    diff_res = client.generate_answer(
        query="What is the difference between 0x22 and 0x2E?",
        citations=[read_did_citation, _make_sample_uds_citation()]
    )
    assert diff_res.qa_mode == "DOMAIN_KNOWLEDGE"
    assert diff_res.citations == []


def test_domain_boundary_false_positive_cases():
    """Verify standalone generic automotive/technical terms do NOT falsely trigger UDS domain mode."""
    client = MockLLMClient()
    uds_citation = _make_sample_uds_citation()

    out_of_scope_boundary_queries = [
        "What is automotive engineering?",
        "Explain firmware security.",
        "What is a VIN?",
        "What is an ECU?",
        "What is session management in web applications?",
        "How do I calibrate a camera sensor?",
        "What is a unique identifier in a database?",
    ]

    for q in out_of_scope_boundary_queries:
        assert is_uds_domain_query(q) is False, f"Expected False for non-UDS query: {q}"
        res = client.generate_answer(query=q, citations=[uds_citation])
        assert res.qa_mode == "OUT_OF_SCOPE", f"Expected OUT_OF_SCOPE for query: {q}"
        assert res.citations == []

    # When explicitly asked in UDS / diagnostic context, VIN / ECU / ISO 15765 / DoIP remain valid
    in_scope_contextual_queries = [
        "How is a VIN read using UDS diagnostic services?",
        "How do ECU diagnostic sessions work?",
        "How is ISO 15765 used in ECU diagnostics?",
        "How does DoIP transport diagnostic requests?",
    ]
    for q in in_scope_contextual_queries:
        assert is_uds_domain_query(q) is True, f"Expected True for contextual diagnostic query: {q}"
        res = client.generate_answer(query=q, citations=[])
        assert res.qa_mode == "DOMAIN_KNOWLEDGE"
        assert res.citations == []
