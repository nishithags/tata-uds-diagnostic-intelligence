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
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.request
import json
from pydantic import BaseModel, Field

from src.core.embeddings import AUTOMOTIVE_UDS_LEXICON
from src.core.vector_store import Citation


GENERAL_KNOWLEDGE_MODE_LABEL = "General Knowledge Mode — No relevant project specification matched this query."
GROUNDED_DIAGNOSTIC_MODE_LABEL = "Grounded Diagnostic Mode — Verified Project Specification Evidence"

_QUERY_STOPWORDS = {
    "what", "which", "when", "where", "who", "whom", "whose", "why", "how",
    "does", "do", "did", "is", "are", "was", "were", "be", "been", "being",
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "for", "of",
    "to", "in", "on", "at", "by", "with", "from", "into", "about", "as",
    "can", "could", "would", "should", "shall", "will", "may", "might", "must",
    "explain", "describe", "tell", "me", "give", "show", "list", "define",
    "apply", "required", "require", "requires", "valid", "behavior", "work",
    "works", "working", "used", "use", "using", "between", "under", "over",
    "after", "before", "during", "without", "within", "this", "that", "these",
    "those", "their", "there", "here", "have", "has", "had", "not", "no",
    "yes", "any", "all", "some", "such", "than", "too", "very", "just",
    "only", "also", "more", "most", "other", "another", "each", "every",
    "both", "either", "neither", "many", "much", "few", "little", "own",
    "same", "so", "up", "down", "out", "off", "again", "further", "once",
    "programming", "language",
}


def is_citation_relevant(query: str, citation: Citation) -> bool:
    """
    Determines whether a retrieved specification citation genuinely matches the user query.
    Prevents unrelated general questions from falsely attaching diagnostic citations.
    """
    q_lower = query.lower()
    chunk_lower = f"{citation.section_title} {citation.text_snippet}".lower()

    q_hex = set(re.findall(r"0x[0-9a-f]+", q_lower))
    c_hex = set(re.findall(r"0x[0-9a-f]+", chunk_lower))

    q_tokens = [t for t in re.findall(r"[a-z0-9_]+", q_lower) if len(t) >= 3]
    c_tokens = set(re.findall(r"[a-z0-9_]+", chunk_lower))

    content_tokens = [
        t for t in q_tokens
        if t not in _QUERY_STOPWORDS and not t.startswith("0x")
    ]

    uds_anchors = set(AUTOMOTIVE_UDS_LEXICON)

    matched_content = [
        t for t in content_tokens
        if t in c_tokens or any(t in ct or ct in t for ct in c_tokens if len(ct) >= 4)
    ]
    matched_uds_anchors = [
        t for t in content_tokens
        if t in uds_anchors and (t in c_tokens or any(t in ct for ct in c_tokens))
    ]

    if q_hex:
        if q_hex.intersection(c_hex):
            return True
        return len(matched_uds_anchors) >= 1 and len(matched_content) >= 2

    if not content_tokens:
        return False

    if not matched_content:
        return False

    if matched_uds_anchors:
        return True

    overlap_ratio = len(matched_content) / len(content_tokens)
    return overlap_ratio >= 0.5


def filter_relevant_citations(query: str, citations: List[Citation]) -> List[Citation]:
    """Filters retrieved citations down to those genuinely relevant to the query."""
    if not citations:
        return []
    return [c for c in citations if is_citation_relevant(query, c)]


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
    qa_mode: str = "GROUNDED_DIAGNOSTIC"  # "GROUNDED_DIAGNOSTIC" or "GENERAL_KNOWLEDGE"
    mode_label: str = GROUNDED_DIAGNOSTIC_MODE_LABEL


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
        relevant_citations = filter_relevant_citations(query, citations)

        if not relevant_citations:
            elapsed_ms = (time.time() - start_time) * 1000.0
            return QAResponse(
                query=query,
                answer=(
                    f"**{GENERAL_KNOWLEDGE_MODE_LABEL}**\n\n"
                    f"Your question (**\"{query}\"**) was routed to **General Knowledge Mode** because no matching "
                    "UDS or OEM diagnostic specification evidence was found in the active project workspace.\n\n"
                    "**Runtime Notice (Deterministic Fallback Mock Active):**\n"
                    "The active inference runtime is `mock-deterministic-v1` (Local Ollama daemon is offline or unreachable). "
                    "Because the deterministic fallback client only synthesizes verbatim excerpts from verified workspace "
                    "documents and does not contain general-purpose language model weights, it cannot synthesize open-ended "
                    "general knowledge answers without an active LLM backend.\n\n"
                    "To enable generative general-knowledge answers under approved Architectural Decision **AD-01 (Option 1A)**, "
                    "connect an active Ollama runtime (`llama3.1:8b` or `qwen2.5:7b`) via `OLLAMA_HOST`."
                ),
                citations=[],
                model_identifier=self.client_id,
                llm_decision_status="PENDING_FORMAL_USER_APPROVAL",
                generation_source="FALLBACK_TEMPLATE_MOCK",
                is_mock_fallback=True,
                inference_latency_ms=round(elapsed_ms, 2),
                disclaimer=(
                    f"{GENERAL_KNOWLEDGE_MODE_LABEL} "
                    "No diagnostic citations attached. Active runtime is Deterministic Fallback Mock (Local Ollama offline)."
                ),
                qa_mode="GENERAL_KNOWLEDGE",
                mode_label=GENERAL_KNOWLEDGE_MODE_LABEL,
            )

        ordered_citations = relevant_citations + [c for c in citations if c not in relevant_citations]

        evidence_lines = []
        for i, c in enumerate(relevant_citations[:3], start=1):
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
            f"- Information is sourced directly from **{len(ordered_citations)}** verified chunk(s) across "
            f"document(s): {', '.join(sorted(list({c.document_name for c in ordered_citations}))) }.\n"
            f"- Top cited section: **{relevant_citations[0].section_title}** (Page {relevant_citations[0].page_number}).\n"
            f"- Full chunk excerpts and cryptographic hashes are verifiable in the Citations panel below."
        )

        elapsed_ms = (time.time() - start_time) * 1000.0

        return QAResponse(
            query=query,
            answer=summary_intro,
            citations=ordered_citations,
            model_identifier=self.client_id,
            llm_decision_status="PENDING_FORMAL_USER_APPROVAL",
            generation_source="FALLBACK_TEMPLATE_MOCK",
            is_mock_fallback=True,
            inference_latency_ms=round(elapsed_ms, 2),
            disclaimer=(
                "NOTICE: Generated via Fallback Client (Deterministic Template Mock). "
                "Local Ollama daemon is offline or model weights are not loaded. "
                "Retrieved citations and diagnostic excerpts above are deterministic extracts from authorized documents."
            ),
            qa_mode="GROUNDED_DIAGNOSTIC",
            mode_label=GROUNDED_DIAGNOSTIC_MODE_LABEL,
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
        Attempts local Ollama generative response in Two-Mode Q&A:
        - Mode 1 (GROUNDED_DIAGNOSTIC): When relevant workspace specification evidence exists.
        - Mode 2 (GENERAL_KNOWLEDGE): When no relevant workspace specification evidence matches.
        If Ollama is unreachable or errors, automatically falls back to MockLLMClient.
        """
        if not self.is_available():
            return self.mock_fallback.generate_answer(query, citations)

        relevant_citations = filter_relevant_citations(query, citations)
        start_time = time.time()
        try:
            if relevant_citations:
                ordered_citations = relevant_citations + [c for c in citations if c not in relevant_citations]
                context_snippets = "\n".join(
                    [f"[{c.document_name} p.{c.page_number}]: {c.text_snippet}" for c in relevant_citations[:4]]
                )
                prompt = (
                    f"You are an expert UDS Automotive Diagnostic Assistant at Tata Technologies.\n"
                    f"Answer the diagnostic question using ONLY the provided specification excerpts.\n\n"
                    f"SPECIFICATIONS:\n{context_snippets}\n\n"
                    f"QUESTION: {query}\n\n"
                    f"ANSWER:"
                )
            else:
                ordered_citations = []
                prompt = (
                    f"You are a helpful engineering and general knowledge assistant.\n"
                    f"No project diagnostic specification matched the user's question. "
                    f"Provide a clear, accurate general knowledge answer to the question below. "
                    f"Do not claim or imply that this answer comes from Tata Technologies or OEM project specifications.\n\n"
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

            if relevant_citations:
                return QAResponse(
                    query=query,
                    answer=generated_text,
                    citations=ordered_citations,
                    model_identifier=self.client_id,
                    llm_decision_status="PENDING_FORMAL_USER_APPROVAL",
                    approved_option="APPROVED_OPTION_1A_OLLAMA_LOCAL",
                    generation_source="LOCAL_OLLAMA_LLM",
                    is_mock_fallback=False,
                    inference_latency_ms=round(elapsed_ms, 2),
                    disclaimer="Generated via approved Local Ollama LLM (air-gapped, zero cloud egress).",
                    qa_mode="GROUNDED_DIAGNOSTIC",
                    mode_label=GROUNDED_DIAGNOSTIC_MODE_LABEL,
                )

            formatted_general_answer = (
                f"**{GENERAL_KNOWLEDGE_MODE_LABEL}**\n\n{generated_text}"
                if GENERAL_KNOWLEDGE_MODE_LABEL not in generated_text
                else generated_text
            )
            return QAResponse(
                query=query,
                answer=formatted_general_answer,
                citations=[],
                model_identifier=self.client_id,
                llm_decision_status="PENDING_FORMAL_USER_APPROVAL",
                approved_option="APPROVED_OPTION_1A_OLLAMA_LOCAL",
                generation_source="LOCAL_OLLAMA_LLM",
                is_mock_fallback=False,
                inference_latency_ms=round(elapsed_ms, 2),
                disclaimer=(
                    f"{GENERAL_KNOWLEDGE_MODE_LABEL} "
                    "Generated via Local Ollama LLM using general model knowledge (not sourced from workspace specifications)."
                ),
                qa_mode="GENERAL_KNOWLEDGE",
                mode_label=GENERAL_KNOWLEDGE_MODE_LABEL,
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
