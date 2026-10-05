"""
Knowledge Q&A Page for UDS Diagnostic Intelligence Platform.
Provides cited diagnostic Q&A workspace grounded in project specifications.
"""

import streamlit as st
from src.core.activity_store import ActivityAction, activity_store
from src.core.llm_interface import LLMClientFactory
from src.core.vector_store import IsolatedVectorStore


def render_knowledge_page(active_ws):
    """Renders the Knowledge Q&A workspace."""
    vector_store = IsolatedVectorStore()
    llm_client = LLMClientFactory.get_client()

    st.markdown("### 🔎 Diagnostic Knowledge Q&A Workspace")
    st.caption(
        f"Query diagnostic specifications for workspace **`{active_ws.name}`** (`{active_ws.project_id}`). "
        "All answers are grounded in ingested specifications with exact page, section, and cryptographic hash attribution."
    )

    sample_queries = [
        "What are the prerequisites and valid subfunctions for Diagnostic Session Control (0x10)?",
        "Explain the seed and key handshake state transitions in Security Access (0x27).",
        "Which Negative Response Codes (NRC) apply to WriteDataByIdentifier (0x2E)?",
        "What is the required timing behavior for P2Server and NRC 0x78 Response Pending?"
    ]

    col_q, col_sample = st.columns([3, 2])
    with col_sample:
        selected_sample = st.selectbox(
            "Reference Sample Queries",
            ["-- Select a Reference Query --"] + sample_queries,
            help="Choose a pre-configured automotive diagnostic query."
        )

    default_text = selected_sample if selected_sample != "-- Select a Reference Query --" else ""
    user_query = col_q.text_input(
        "Diagnostic Requirement or Specification Query",
        value=default_text,
        placeholder="e.g. What session is required for service 0x2E?"
    )

    col_btn, col_topk = st.columns([1, 4])
    top_k = col_topk.slider("Maximum Citations", min_value=1, max_value=10, value=4)
    run_query = col_btn.button("Search Knowledge", type="primary")

    if run_query:
        if not user_query.strip():
            st.warning("Please enter a diagnostic question or select a sample query.")
        else:
            with st.spinner("Retrieving diagnostic evidence from vector index and synthesizing response..."):
                try:
                    citations = vector_store.query(
                        project_id=active_ws.project_id,
                        query_text=user_query,
                        top_k=top_k
                    )
                    qa_result = llm_client.generate_answer(query=user_query, citations=citations)

                    # Log activity with exact user query text
                    activity_store.log_activity(
                        session_id=st.session_state.session_id,
                        user_id=st.session_state.user_id,
                        project_id=active_ws.project_id,
                        action=ActivityAction.KNOWLEDGE_QUERY,
                        endpoint="UI",
                        http_method="UI",
                        query_text=user_query,
                        status="SUCCESS",
                        duration_ms=getattr(qa_result, "inference_latency_ms", 0.0),
                        metadata={
                            "citations_count": len(citations),
                            "model": getattr(qa_result, "model_identifier", "mock"),
                            "is_mock": getattr(qa_result, "is_mock_fallback", True)
                        }
                    )

                    st.markdown("---")
                    st.markdown("#### 📋 Specification Synthesis & Evidence Answer")

                    if getattr(qa_result, "is_mock_fallback", True):
                        st.warning("🟡 **Runtime Engine:** `Deterministic Fallback Mock` — Local Ollama offline. Response synthesized deterministically from authorized citations.")
                    else:
                        st.success(f"🟢 **Runtime Engine:** `Local Ollama LLM ({qa_result.model_identifier})` — Latency: {qa_result.inference_latency_ms:.1f}ms | Air-gapped on-premise execution.")

                    st.markdown(
                        f"""
                        <div class="eng-card">
                            <div style="font-size:0.95rem; line-height:1.6; color:#F8FAFC;">
                                {qa_result.answer}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    st.caption(f"🛡️ *{qa_result.disclaimer}*")

                    st.markdown("---")
                    st.markdown("#### 📚 Verified Source Citations & Provenance")
                    if not citations:
                        st.info("No matching specifications found in this workspace. Upload diagnostic specifications in the Documents page.")
                    else:
                        for idx, c in enumerate(citations, start=1):
                            score_pct = c.relevance_score * 100
                            with st.expander(f"Citation [{idx}] — {c.document_name} | Page {c.page_number} | Section: '{c.section_title}' (Match: {score_pct:.1f}%)"):
                                st.markdown("**Verbatim Specification Excerpt:**")
                                st.code(c.text_snippet, language="text")
                                c_col1, c_col2, c_col3 = st.columns(3)
                                c_col1.caption(f"**Document ID:** `{c.doc_id}`")
                                c_col2.caption(f"**Chunk ID:** `{c.chunk_id}`")
                                c_col3.caption(f"**SHA-256:** `{c.source_hash_sha256[:16]}...`")

                except Exception as e:
                    activity_store.log_activity(
                        session_id=st.session_state.session_id,
                        user_id=st.session_state.user_id,
                        project_id=active_ws.project_id,
                        action=ActivityAction.KNOWLEDGE_QUERY,
                        endpoint="UI",
                        http_method="UI",
                        query_text=user_query,
                        status="FAILURE",
                        metadata={"error": str(e)}
                    )
                    st.error(f"Knowledge retrieval error: {str(e)}")
