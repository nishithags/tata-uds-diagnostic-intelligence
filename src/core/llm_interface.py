"""
LLM Integration Interface and Ollama Client for Phase 5.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Implements approved Architectural Decision AD-01 (Option 1A):
- Connects to local Ollama runtime (Llama 3.1 8B / Qwen 2.5 7B) at http://localhost:11434.
- Strictly air-gapped; zero external cloud egress.
- Implements dynamic health checking with automatic, graceful fallback to MockLLMClient
  if the Ollama daemon or model weights are offline or uninstalled.
- Explicitly flags generation source: LOCAL_OLLAMA_LLM vs FALLBACK_TEMPLATE_MOCK
  to guarantee full transparency to engineers.
"""

from abc import ABC, abstractmethod
import os
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.request
import json
from pydantic import BaseModel, Field

from src.core.vector_store import Citation


class QAResponse(BaseModel):
    """Structured response containing synthesized answer, citations, and provenance metadata."""
    __test__ = False
    query: str
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    model_identifier: str
    llm_decision_status: str = "PENDING_FORMAL_USER_APPROVAL"
    approved_option: str = "APPROVED_OPTION_1A_OLLAMA_LOCAL"
    generation_source: str = "FALLBACK_TEMPLATE_MOCK"  # "LOCAL_OLLAMA_LLM" or "FALLBACK_TEMPLATE_MOCK"
    is_mock_fallback: bool = True
    inference_latency_ms: float = 0.0
    disclaimer: str = ""


class BaseLLMClient(ABC):
    """Abstract Base Class for diagnostic LLM inference clients."""
    __test__ = False

    @property
    @abstractmethod
    def client_id(self) -> str:
        pass

    @abstractmethod
    def generate_answer(self, query: str, citations: List[Citation]) -> QAResponse:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the underlying inference runtime is online and reachable."""
        pass


class MockLLMClient(BaseLLMClient):
    """
    Deterministic Evidence-Based Fallback Client.
    Synthesizes exact cited excerpts and presents clear evidence-based diagnostic guidance.
    Used when local Ollama is offline or uninstalled.
    """
    __test__ = False

    @property
    def client_id(self) -> str:
        return "mock-deterministic-v1"

    def is_available(self) -> bool:
        return True

    def generate_answer(self, query: str, citations: List[Citation]) -> QAResponse:
        start_time = time.time()
        if not citations:
            return QAResponse(
                query=query,
                answer=(
                    "No relevant diagnostic knowledge found in the current workspace. "
                    "Please verify that the required UDS/OEM specifications have been uploaded and ingested."
                ),
                citations=[],
                model_identifier=self.client_id,
                llm_decision_status="PENDING_FORMAL_USER_APPROVAL",
                generation_source="FALLBACK_TEMPLATE_MOCK",
                is_mock_fallback=True,
                inference_latency_ms=0.0,
                disclaimer="No matching documents found in isolated workspace collection."
            )

        evidence_lines = []
        for i, c in enumerate(citations[:3], start=1):
            evidence_lines.append(
                f"**Evidence [{i}] (Source: `{c.document_name}`, Page {c.page_number}, Section '{c.section_title}', "
                f"Relevance: {c.relevance_score * 100:.1f}%):**\n"
                f"> {c.text_snippet.replace(chr(10), ' ')}\n"
            )

        summary_intro = (
            f"Based on the ingested diagnostic specifications for query **\"{query}\"**, "
            f"the following cited evidence was retrieved:\n\n"
            + "\n".join(evidence_lines)
            + "\n### Diagnostic Guidance Summary:\n"
            f"- Information is sourced directly from **{len(citations)}** verified chunk(s) across "
            f"document(s): {', '.join(sorted(list({c.document_name for c in citations}))) }.\n"
            f"- Top cited section: **{citations[0].section_title}** (Page {citations[0].page_number}).\n"
            f"- Full chunk excerpts and cryptographic hashes are verifiable in the Citations panel below."
        )

        elapsed_ms = (time.time() - start_time) * 1000.0

        return QAResponse(
            query=query,
            answer=summary_intro,
            citations=citations,
            model_identifier=self.client_id,
            llm_decision_status="PENDING_FORMAL_USER_APPROVAL",
            generation_source="FALLBACK_TEMPLATE_MOCK",
            is_mock_fallback=True,
            inference_latency_ms=round(elapsed_ms, 2),
            disclaimer=(
                "NOTICE: Generated via Fallback Client (Deterministic Template Mock). "
                "Local Ollama daemon is offline or model weights are not loaded. "
                "Retrieved citations and diagnostic excerpts above are deterministic extracts from authorized documents."
            )
        )


class OllamaLLMClient(BaseLLMClient):
    """
    Approved Local LLM Client (AD-01 Option 1A).
    Interacts with local Ollama runtime via REST API (default: http://localhost:11434).
    Automatically and safely falls back to MockLLMClient when Ollama is unavailable.
    """
    __test__ = False

    def __init__(
        self,
        host: Optional[str] = None,
        model: str = "llama3.1:8b",
        timeout_seconds: float = 3.0
    ):
        resolved_host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.host = resolved_host.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.mock_fallback = MockLLMClient()

    @property
    def client_id(self) -> str:
        return f"ollama/{self.model}"

    def is_available(self) -> bool:
        """Pings Ollama daemon API with a short timeout to check availability."""
        try:
            req = urllib.request.Request(f"{self.host}/api/tags", headers={"User-Agent": "Tata-UDS-Assistant"})
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def generate_answer(self, query: str, citations: List[Citation]) -> QAResponse:
        """
        Attempts local Ollama generative response.
        If Ollama is unreachable or errors, automatically falls back to MockLLMClient.
        """
        if not self.is_available():
            return self.mock_fallback.generate_answer(query, citations)

        start_time = time.time()
        try:
            # Build cited context prompt
            context_snippets = "\n".join([f"[{c.document_name} p.{c.page_number}]: {c.text_snippet}" for c in citations[:4]])
            prompt = (
                f"You are an expert UDS Automotive Diagnostic Assistant at Tata Technologies.\n"
                f"Answer the diagnostic question using ONLY the provided specification excerpts.\n\n"
                f"SPECIFICATIONS:\n{context_snippets}\n\n"
                f"QUESTION: {query}\n\n"
                f"ANSWER:"
            )

            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 512}
            }
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.host}/api/generate",
                data=req_data,
                headers={"Content-Type": "application/json", "User-Agent": "Tata-UDS-Assistant"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                generated_text = data.get("response", "").strip()

            elapsed_ms = (time.time() - start_time) * 1000.0

            return QAResponse(
                query=query,
                answer=generated_text,
                citations=citations,
                model_identifier=self.client_id,
                llm_decision_status="PENDING_FORMAL_USER_APPROVAL",
                approved_option="APPROVED_OPTION_1A_OLLAMA_LOCAL",
                generation_source="LOCAL_OLLAMA_LLM",
                is_mock_fallback=False,
                inference_latency_ms=round(elapsed_ms, 2),
                disclaimer="Generated via approved Local Ollama LLM (air-gapped, zero cloud egress)."
            )
        except Exception as e:
            # Safe automatic fallback
            fallback_res = self.mock_fallback.generate_answer(query, citations)
            fallback_res.disclaimer = f"NOTICE: Ollama call failed ({str(e)}). Returned deterministic fallback."
            return fallback_res

    def generate_raw_text(self, prompt: str) -> Tuple[str, str, bool]:
        """
        Sends raw prompt to Ollama.
        Returns (text, generation_source, is_mock).
        """
        if not self.is_available():
            return "Local Ollama daemon is offline. Deterministic rule-based template generation active.", "FALLBACK_TEMPLATE_MOCK", True

        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 1024}
            }
            req = urllib.request.Request(
                f"{self.host}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "").strip(), "LOCAL_OLLAMA_LLM", False
        except Exception:
            return "Ollama generation failed. Used deterministic template fallback.", "FALLBACK_TEMPLATE_MOCK", True


# Maintain backward compatibility
PendingApprovalLLMAdapter = MockLLMClient


class LLMClientFactory:
    """Factory delivering the approved local LLM client with automatic fallback."""

    @staticmethod
    def get_client() -> BaseLLMClient:
        return OllamaLLMClient()
