"""
Unit tests for Ollama Local LLM Client and Graceful Fallback (AD-01 Option 1A).
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

from unittest.mock import MagicMock, patch
import json
import pytest

from src.core.llm_interface import (
    LLMClientFactory,
    MockLLMClient,
    OllamaLLMClient,
    QAResponse,
)
from src.core.vector_store import Citation


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

    citation = Citation(
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

    response = client.generate_answer(query="What is 0x10 subfunction 0x01?", citations=[citation])
    assert isinstance(response, QAResponse)
    assert response.is_mock_fallback is True
    assert response.generation_source == "FALLBACK_TEMPLATE_MOCK"
    assert "NOTICE: Generated via Fallback Client" in response.disclaimer
    assert "0x10 subfunction 0x01 is default session" in response.answer


def test_ollama_mocked_online_success():
    client = OllamaLLMClient(host="http://localhost:11434")

    citation = Citation(
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

    mock_ollama_reply = json.dumps({"response": "According to ISO 14229, subfunction 0x01 is DefaultSession."}).encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.read.return_value = mock_ollama_reply
    mock_resp.__enter__.return_value = mock_resp

    with patch.object(client, "is_available", return_value=True):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            qa_res = client.generate_answer("What is subfunction 0x01?", [citation])
            assert qa_res.is_mock_fallback is False
            assert qa_res.generation_source == "LOCAL_OLLAMA_LLM"
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
