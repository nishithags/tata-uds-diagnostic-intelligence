"""
Unit tests for Ollama Local LLM Client and Graceful Fallback (AD-01 Option 1A).
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

from unittest.mock import MagicMock, patch
import json
import pytest

from src.core.llm_interface import (
    GENERAL_KNOWLEDGE_MODE_LABEL,
    GROUNDED_DIAGNOSTIC_MODE_LABEL,
    LLMClientFactory,
    MockLLMClient,
    OllamaLLMClient,
    QAResponse,
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


def test_diagnostic_question_with_matching_evidence_grounded_mode():
    """1. Diagnostic question with matching evidence -> grounded answer + citations."""
    client = MockLLMClient()
    citation = _make_sample_uds_citation()

    res = client.generate_answer(
        query="What are the valid subfunctions for Diagnostic Session Control 0x10?",
        citations=[citation]
    )
    assert res.qa_mode == "GROUNDED_DIAGNOSTIC"
    assert res.mode_label == GROUNDED_DIAGNOSTIC_MODE_LABEL
    assert len(res.citations) == 1
    assert res.citations[0].source_hash_sha256 == "abc123"
    assert "0x10 subfunction 0x01 is default session" in res.answer


def test_general_question_no_matching_evidence_general_knowledge_mode():
    """2. General question with no matching evidence -> general-answer path."""
    # Offline / fallback path
    offline_client = OllamaLLMClient(host="http://localhost:59999", timeout_seconds=0.1)
    offline_res = offline_client.generate_answer(
        query="What is the capital of France?",
        citations=[]
    )
    assert offline_res.qa_mode == "GENERAL_KNOWLEDGE"
    assert offline_res.mode_label == GENERAL_KNOWLEDGE_MODE_LABEL
    assert GENERAL_KNOWLEDGE_MODE_LABEL in offline_res.answer

    # Online Ollama LLM path
    online_client = OllamaLLMClient(host="http://localhost:11434")
    mock_ollama_reply = json.dumps({"response": "The capital of France is Paris."}).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = mock_ollama_reply
    mock_resp.__enter__.return_value = mock_resp

    with patch.object(online_client, "is_available", return_value=True):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            online_res = online_client.generate_answer(
                query="What is the capital of France?",
                citations=[]
            )
            assert online_res.qa_mode == "GENERAL_KNOWLEDGE"
            assert online_res.mode_label == GENERAL_KNOWLEDGE_MODE_LABEL
            assert GENERAL_KNOWLEDGE_MODE_LABEL in online_res.answer
            assert "The capital of France is Paris." in online_res.answer
            assert online_res.is_mock_fallback is False


def test_general_answer_has_no_fake_diagnostic_citations():
    """3. General answer has NO fake diagnostic citations even if vector search returned unrelated top-k chunks."""
    uds_citation = _make_sample_uds_citation()
    mock_client = MockLLMClient()

    res_mock = mock_client.generate_answer(
        query="What is Python programming language?",
        citations=[uds_citation]
    )
    assert res_mock.qa_mode == "GENERAL_KNOWLEDGE"
    assert res_mock.citations == []

    online_client = OllamaLLMClient(host="http://localhost:11434")
    mock_ollama_reply = json.dumps({"response": "Python is a high-level programming language."}).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = mock_ollama_reply
    mock_resp.__enter__.return_value = mock_resp

    with patch.object(online_client, "is_available", return_value=True):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            res_online = online_client.generate_answer(
                query="What is Python programming language?",
                citations=[uds_citation]
            )
            assert res_online.qa_mode == "GENERAL_KNOWLEDGE"
            assert res_online.citations == []
            assert "iso14229.txt" not in res_online.answer


def test_legacy_no_evidence_message_not_triggered_for_general_questions():
    """4. Existing 'no evidence' safety behavior is not incorrectly triggered for general questions."""
    uds_citation = _make_sample_uds_citation()
    mock_client = MockLLMClient()

    for citations_arg in ([], [uds_citation]):
        res = mock_client.generate_answer(
            query="Explain how a lithium-ion battery works.",
            citations=citations_arg
        )
        assert "No relevant diagnostic knowledge found in the current workspace" not in res.answer
        assert res.qa_mode == "GENERAL_KNOWLEDGE"
        assert GENERAL_KNOWLEDGE_MODE_LABEL in res.answer
        assert res.citations == []
