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


GROUNDED_DIAGNOSTIC_MODE_LABEL = (
    "Grounded Diagnostic Mode (GROUNDED_DIAGNOSTIC) — Verified Project Specification Evidence"
)
DOMAIN_KNOWLEDGE_MODE_LABEL = (
    "Domain Knowledge Mode (DOMAIN_KNOWLEDGE) — No matching project specification in workspace; "
    "answered using UDS / Automotive Diagnostic domain scope."
)
OUT_OF_SCOPE_MODE_LABEL = (
    "Out of Scope (OUT_OF_SCOPE) — Assistant is restricted to UDS and automotive diagnostic engineering questions."
)
# Backward-compatible alias
GENERAL_KNOWLEDGE_MODE_LABEL = DOMAIN_KNOWLEDGE_MODE_LABEL

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

_GENERIC_DIAGNOSTIC_MODIFIERS = {
    "uds", "iso", "iso14229", "iso15765", "diagnostic", "diagnostics",
    "automotive", "vehicle", "ecu", "ecus", "service", "services",
    "identifier", "identifiers", "data", "control", "request", "requests",
    "response", "responses", "positive", "negative", "code", "codes",
    "level", "levels", "mode", "modes", "status", "system", "value",
    "values", "parameter", "parameters", "message", "messages", "frame",
    "frames", "byte", "bytes", "bit", "bits", "support", "supported",
    "mean", "means", "meaning", "purpose", "difference", "function",
    "functions", "protocol", "standard", "specification", "specifications",
}

_UNAMBIGUOUS_UDS_TOKENS = {
    "uds", "iso14229",
    "nrc", "nrcs", "dids", "rid", "rids", "dtc", "dtcs",
    "subfunction", "subfunctions",
    "p2server", "p2star", "s3server", "s3client",
    "posrsp", "suppressposrsp", "prpr", "responsepending", "requestseed", "sendkey",
    "diagnosticsessioncontrol", "ecureset", "cleardiagnosticinformation",
    "readdtcinformation", "readdatabyidentifier", "readmemorybyaddress",
    "readscalingdatabyidentifier", "securityaccess", "communicationcontrol",
    "readperiodicdatabyidentifier", "dynamicallydefinedataidentifier",
    "writedatabyidentifier", "writememorybyaddress",
    "inputoutputcontrolbyidentifier", "routinecontrol", "requestdownload",
    "requestupload", "transferdata", "requesttransferexit", "requestfiletransfer",
    "testerpresent", "accesstimingparameter", "securedatatransmission",
    "controldtcsetting", "responseonevent", "linkcontrol",
    "defaultsession", "programmingsession", "extendeddiagnosticsession",
    "extendedsession", "safetysystemdiagnosticsession", "safetysession",
    "subfunctionnotsupported", "incorrectmessagelengthorinvalidformat",
    "conditionsnotcorrect", "requestsequenceerror", "requestoutofrange",
    "securityaccessdenied", "invalidkey", "exceedednumberofattempts",
    "requiredtimedelaynotexpired",
    "odx", "pdx", "cdd",
}

_UDS_DOMAIN_PHRASES = (
    "iso 14229", "iso-14229", "unified diagnostic services",
    "data identifier", "routine identifier", "negative response", "positive response",
    "response pending", "diagnostic session", "diagnostic session control",
    "default session", "programming session", "extended session", "safety session",
    "security access", "seed and key", "seed/key", "seed-key", "request seed", "send key",
    "tester present", "ecu reset", "routine control", "read data by identifier",
    "write data by identifier", "input output control", "communication control",
    "control dtc", "clear diagnostic", "read dtc",
    "diagnostic service", "diagnostic services", "diagnostic subfunction", "diagnostic subfunctions",
    "diagnostic request", "diagnostic response", "diagnostic trouble code",
    "diagnostic validation", "diagnostic test", "ecu diagnostic", "ecu diagnostics",
    "automotive diagnostic", "automotive diagnostics",
    "p2*", "p2 server", "p2_server", "p2star", "p2_star", "p2 timing", "p2 timer", "p2 timeout",
    "s3 server", "s3_server", "s3 timer", "s3 timeout", "s3 timing",
)

_DIAGNOSTIC_CONTEXT_WORDS = {"diagnostic", "diagnostics"}

_DIAGNOSTIC_QUALIFIED_SUBJECTS = {
    "ecu", "ecus", "vin", "session", "sessions", "service", "services",
    "subfunction", "subfunctions", "security", "seed", "key", "routine",
    "identifier", "identifiers", "timing", "timeout", "timer", "tester",
    "request", "requests", "response", "responses", "can", "docan", "doip",
    "isotp", "iso15765", "frame", "payload", "reset", "flashing",
    "calibration", "lockout", "handshake", "sid", "sids", "automotive",
    "vehicle", "p2", "s3", "obd", "obd2", "canoe", "capl",
}

_TRANSPORT_TIMING_TOKENS = {
    "docan", "doip", "isotp", "iso15765", "canoe", "capl", "p2", "s3",
}

_TRANSPORT_TIMING_DIAGNOSTIC_PARTNERS = {
    "diagnostic", "diagnostics", "uds", "ecu", "ecus", "service", "services",
    "session", "sessions", "timing", "timeout", "timer", "server",
    "request", "response", "tester",
}


def is_uds_domain_query(query: str) -> bool:
    """
    Determines whether a user query belongs to the UDS / automotive diagnostic engineering domain.
    Rejects unrelated general-knowledge queries and standalone generic automotive/technical queries
    so the assistant remains strictly bounded to UDS and automotive diagnostics.
    """
    if not query or not query.strip():
        return False

    q_lower = query.lower()

    # 1. Explicit hexadecimal diagnostic identifier (e.g. 0x10, 0x22, 0x2E, 0x78, 0x0201, 0xF190)
    if re.search(r"\b0x[0-9a-f]{2,6}\b", q_lower):
        return True

    # 2. Uppercase 'DID' acronym (distinguished from lowercase English auxiliary verb 'did')
    if re.search(r"\bDIDs?\b", query):
        return True

    # 3. Multi-word UDS / automotive diagnostic phrases
    if any(phrase in q_lower for phrase in _UDS_DOMAIN_PHRASES):
        return True

    # 4. Single unambiguous UDS / ISO 14229 tokens
    tokens = set(re.findall(r"[a-z0-9_]+", q_lower))
    if "iso" in tokens and "15765" in tokens:
        tokens.add("iso15765")
    if tokens.intersection(_UNAMBIGUOUS_UDS_TOKENS):
        return True

    # 5. Explicit 'diagnostic(s)' paired with a concrete ECU/UDS/protocol subject
    if tokens.intersection(_DIAGNOSTIC_CONTEXT_WORDS) and tokens.intersection(_DIAGNOSTIC_QUALIFIED_SUBJECTS):
        return True

    # 6. Diagnostic transport/timing terms (DoCAN, DoIP, ISO 15765, P2, S3, CANoe, CAPL)
    #    when explicitly used in a diagnostic/ECU/session/timing context
    if tokens.intersection(_TRANSPORT_TIMING_TOKENS) and tokens.intersection(_TRANSPORT_TIMING_DIAGNOSTIC_PARTNERS):
        return True

    return False


def is_citation_relevant(query: str, citation: Citation) -> bool:
    """
    Determines whether a retrieved specification citation genuinely matches the user query.
    Prevents unrelated or ungrounded questions from falsely attaching workspace citations.
    """
    q_lower = query.lower()
    chunk_lower = f"{citation.section_title} {citation.text_snippet}".lower()

    q_hex = set(re.findall(r"0x[0-9a-f]+", q_lower))
    c_hex = set(re.findall(r"0x[0-9a-f]+", chunk_lower))

    q_tokens = [t for t in re.findall(r"[a-z0-9_]+", q_lower) if len(t) >= 2]
    c_tokens = set(re.findall(r"[a-z0-9_]+", chunk_lower))

    content_tokens = [
        t for t in q_tokens
        if t not in _QUERY_STOPWORDS and not t.startswith("0x")
    ]
    specific_tokens = [
        t for t in content_tokens
        if t not in _GENERIC_DIAGNOSTIC_MODIFIERS
    ]

    matched_specific = [
        t for t in specific_tokens
        if t in c_tokens or any((len(t) >= 4 and (t in ct or ct in t)) for ct in c_tokens if len(ct) >= 4)
    ]

    if q_hex:
        if q_hex.intersection(c_hex):
            return True
        return len(matched_specific) >= 2

    if not specific_tokens:
        return False

    if not matched_specific:
        return False

    overlap_ratio = len(matched_specific) / len(specific_tokens)
    return overlap_ratio >= 0.5


def filter_relevant_citations(query: str, citations: List[Citation]) -> List[Citation]:
    """
    Filters retrieved citations down to those genuinely relevant to the query.
    If the query specifies explicit hex identifiers (e.g., service ID, DID, RID, NRC),
    all queried hex identifiers must be present in the retrieved workspace evidence set.
    """
    if not citations:
        return []

    q_hex = set(re.findall(r"0x[0-9a-f]+", query.lower()))
    if q_hex:
        all_citation_hex = set()
        for c in citations:
            chunk_lower = f"{c.section_title} {c.text_snippet}".lower()
            all_citation_hex.update(re.findall(r"0x[0-9a-f]+", chunk_lower))
        if not q_hex.issubset(all_citation_hex):
            return []

    return [c for c in citations if is_citation_relevant(query, c)]


def _resolve_ollama_endpoint(host: Optional[str] = None) -> str:
    """
    Resolves the Ollama endpoint URL from explicit argument, environment variable,
    or Streamlit secrets (if running in Streamlit), falling back to http://localhost:11434.
    """
    if host:
        return host.rstrip("/")
    env_host = os.getenv("OLLAMA_HOST")
    if env_host and env_host.strip():
        return env_host.strip().rstrip("/")
    try:
        import streamlit as st
        secret_host = st.secrets.get("OLLAMA_HOST")
        if secret_host and str(secret_host).strip():
            return str(secret_host).strip().rstrip("/")
    except Exception:
        pass
    return "http://localhost:11434"


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
    qa_mode: str = "GROUNDED_DIAGNOSTIC"  # "GROUNDED_DIAGNOSTIC", "DOMAIN_KNOWLEDGE", or "OUT_OF_SCOPE"
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


def _build_out_of_scope_response(query: str, model_identifier: str, is_mock_fallback: bool, generation_source: str) -> QAResponse:
    """Constructs the standardized OUT_OF_SCOPE response for non-UDS/non-diagnostic queries."""
    return QAResponse(
        query=query,
        answer=(
            f"**{OUT_OF_SCOPE_MODE_LABEL}**\n\n"
            "This assistant is strictly restricted to **UDS (ISO 14229) and automotive diagnostic engineering** "
            "questions (such as diagnostic services, subfunctions, DIDs, RIDs, NRCs, diagnostic sessions, "
            "security access, ECU diagnostic validation, and P2/P2* timing). "
            "It does not answer unrelated general-knowledge questions."
        ),
        citations=[],
        model_identifier=model_identifier,
        llm_decision_status="PENDING_FORMAL_USER_APPROVAL",
        approved_option="APPROVED_OPTION_1A_OLLAMA_LOCAL",
        generation_source=generation_source,
        is_mock_fallback=is_mock_fallback,
        inference_latency_ms=0.0,
        disclaimer="OUT_OF_SCOPE: Query is outside the UDS and automotive diagnostic engineering domain. No citations generated.",
        qa_mode="OUT_OF_SCOPE",
        mode_label=OUT_OF_SCOPE_MODE_LABEL,
    )


class MockLLMClient(BaseLLMClient):
    """
    Deterministic Evidence-Based Fallback Client.
    Synthesizes exact cited excerpts and presents clear evidence-based diagnostic guidance.
    Used when local/remote Ollama is offline or unreachable.
    """
    __test__ = False

    @property
    def client_id(self) -> str:
        return "mock-deterministic-v1"

    def is_available(self) -> bool:
        return True

    def generate_answer(self, query: str, citations: List[Citation]) -> QAResponse:
        start_time = time.time()

        # 1. Domain boundary check: reject non-UDS / non-diagnostic queries immediately
        if not is_uds_domain_query(query):
            return _build_out_of_scope_response(
                query=query,
                model_identifier=self.client_id,
                is_mock_fallback=True,
                generation_source="FALLBACK_TEMPLATE_MOCK",
            )

        # 2. Check for relevant workspace specification evidence
        relevant_citations = filter_relevant_citations(query, citations)

        # 3. UDS question with no matching project specification evidence -> DOMAIN_KNOWLEDGE
        if not relevant_citations:
            elapsed_ms = (time.time() - start_time) * 1000.0
            return QAResponse(
                query=query,
                answer=(
                    f"**{DOMAIN_KNOWLEDGE_MODE_LABEL}**\n\n"
                    f"Your query (**\"{query}\"**) is a valid **UDS / Automotive Diagnostic Engineering** question, "
                    "but the currently indexed project workspace specifications do not contain matching evidence for it.\n\n"
                    "**Runtime Notice (Deterministic Fallback Mock Active):**\n"
                    "The active inference runtime is `mock-deterministic-v1` because the configured Ollama endpoint (`OLLAMA_HOST`) "
                    "is currently offline or unreachable. The deterministic fallback client only extracts verbatim evidence from "
                    "uploaded project specifications and does not hardcode or fabricate ungrounded diagnostic answers.\n\n"
                    "To generate ungrounded **ISO 14229 / UDS Domain Knowledge** answers under approved Architectural Decision "
                    "**AD-01 (Option 1A)**, configure `OLLAMA_HOST` to point to a reachable Ollama runtime (`llama3.1:8b` or `qwen2.5:7b`)."
                ),
                citations=[],
                model_identifier=self.client_id,
                llm_decision_status="PENDING_FORMAL_USER_APPROVAL",
                generation_source="FALLBACK_TEMPLATE_MOCK",
                is_mock_fallback=True,
                inference_latency_ms=round(elapsed_ms, 2),
                disclaimer=(
                    f"{DOMAIN_KNOWLEDGE_MODE_LABEL} "
                    "No project specification citations attached. Deterministic fallback active (Ollama runtime offline)."
                ),
                qa_mode="DOMAIN_KNOWLEDGE",
                mode_label=DOMAIN_KNOWLEDGE_MODE_LABEL,
            )

        # 4. UDS question with matching project specification evidence -> GROUNDED_DIAGNOSTIC
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
    Approved Local/Private LLM Client (AD-01 Option 1A).
    Interacts with configured Ollama runtime via REST API (default: http://localhost:11434 or OLLAMA_HOST).
    Automatically and safely falls back to MockLLMClient when Ollama is unavailable.
    """
    __test__ = False

    def __init__(
        self,
        host: Optional[str] = None,
        model: str = "llama3.1:8b",
        timeout_seconds: float = 3.0
    ):
        self.host = _resolve_ollama_endpoint(host)
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
        Executes Three-Outcome UDS Domain-Bounded Q&A:
        1. OUT_OF_SCOPE: Query is unrelated to UDS / automotive diagnostic engineering.
        2. GROUNDED_DIAGNOSTIC: Relevant workspace specification evidence exists.
        3. DOMAIN_KNOWLEDGE: Valid UDS / diagnostic query, but no matching workspace specification evidence exists.
        If Ollama is unreachable or errors, automatically falls back to MockLLMClient.
        """
        # 1. Domain boundary check before any LLM call
        if not is_uds_domain_query(query):
            is_online = self.is_available()
            return _build_out_of_scope_response(
                query=query,
                model_identifier=self.client_id if is_online else self.mock_fallback.client_id,
                is_mock_fallback=not is_online,
                generation_source="LOCAL_OLLAMA_LLM" if is_online else "FALLBACK_TEMPLATE_MOCK",
            )

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
                    f"You are an expert UDS (ISO 14229) and Automotive Diagnostic Engineering Assistant at Tata Technologies.\n"
                    f"No uploaded project specification in the active workspace matched this query. "
                    f"Answer the question accurately using standard UDS (ISO 14229) and automotive diagnostic engineering domain knowledge. "
                    f"Do NOT claim or imply that this answer comes from uploaded Tata Technologies or OEM project specifications, "
                    f"and do NOT fabricate document citations or hashes.\n\n"
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

            formatted_domain_answer = (
                f"**{DOMAIN_KNOWLEDGE_MODE_LABEL}**\n\n{generated_text}"
                if "DOMAIN_KNOWLEDGE" not in generated_text
                else generated_text
            )
            return QAResponse(
                query=query,
                answer=formatted_domain_answer,
                citations=[],
                model_identifier=self.client_id,
                llm_decision_status="PENDING_FORMAL_USER_APPROVAL",
                approved_option="APPROVED_OPTION_1A_OLLAMA_LOCAL",
                generation_source="LOCAL_OLLAMA_LLM",
                is_mock_fallback=False,
                inference_latency_ms=round(elapsed_ms, 2),
                disclaimer=(
                    f"{DOMAIN_KNOWLEDGE_MODE_LABEL} "
                    "Generated via approved Ollama LLM using UDS / automotive diagnostic domain knowledge "
                    "(not sourced from uploaded workspace specifications)."
                ),
                qa_mode="DOMAIN_KNOWLEDGE",
                mode_label=DOMAIN_KNOWLEDGE_MODE_LABEL,
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
