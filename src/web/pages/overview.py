"""
Overview / Home Page for UDS Diagnostic Intelligence Platform.
Displays executive KPI metrics, system health, end-to-end diagnostic pipeline,
collapsible architectural decisions, and recent activity log.
"""

import streamlit as st
from src.core.activity_store import activity_store
from src.core.execution_store import execution_store
from src.core.llm_interface import LLMClientFactory
from src.core.test_case_store import test_case_store
from src.core.vector_store import IsolatedVectorStore


def render_overview_page(active_ws):
    """Renders the executive engineering overview command center."""
    vstore = IsolatedVectorStore()
    stored_cases = test_case_store.list_test_cases(active_ws.project_id)
    approved_cases = [c for c in stored_cases if c.review_status == "APPROVED"]
    past_runs = execution_store.list_execution_results(active_ws.project_id)

    passed_runs = [r for r in past_runs if r.overall_verdict == "PASS"]
    pass_rate_str = f"{(len(passed_runs) / len(past_runs) * 100):.1f}%" if past_runs else "N/A"

    total_docs = len(active_ws.documents)
    total_chunks = vstore.count_chunks(active_ws.project_id)

    # Section A: Workspace / Project Header
    st.markdown(
        f"""
        <div class="overview-header-box">
            <div class="ov-title">{active_ws.name}</div>
            <div class="ov-meta">
                <span><b>Target ECU:</b> Powertrain & Body Diagnostic Controller</span>
                <span class="ov-sep">•</span>
                <span><b>Project Reference:</b> Tata Technologies Case Study 5</span>
            </div>
            <div class="ov-desc">
                Rule-verified diagnostic test generation, automated ISO 14229 rule validation, simulated ECU execution, and bidirectional graph traceability.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Section B: KPI Summary
    st.markdown("<div class='section-heading'>Workspace Telemetry & Verification KPIs</div>", unsafe_allow_html=True)
    kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5, kpi_col6 = st.columns(6)

    with kpi_col1:
        st.markdown(
            f"""
            <div class="kpi-metric-box">
                <div class="kpi-metric-label">Indexed Documents</div>
                <div class="kpi-metric-val">{total_docs}</div>
                <div class="kpi-metric-sub">Authorized Specs</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with kpi_col2:
        st.markdown(
            f"""
            <div class="kpi-metric-box">
                <div class="kpi-metric-label">Indexed Chunks</div>
                <div class="kpi-metric-val">{total_chunks}</div>
                <div class="kpi-metric-sub">Vector Embeddings</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with kpi_col3:
        st.markdown(
            f"""
            <div class="kpi-metric-box">
                <div class="kpi-metric-label">Generated Tests</div>
                <div class="kpi-metric-val">{len(stored_cases)}</div>
                <div class="kpi-metric-sub">Rule-Verified Cases</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with kpi_col4:
        st.markdown(
            f"""
            <div class="kpi-metric-box">
                <div class="kpi-metric-label">Approved Tests</div>
                <div class="kpi-metric-val">{len(approved_cases)}</div>
                <div class="kpi-metric-sub">HITL Engineering Sign-Off</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with kpi_col5:
        st.markdown(
            f"""
            <div class="kpi-metric-box">
                <div class="kpi-metric-label">Executed Tests</div>
                <div class="kpi-metric-val">{len(past_runs)}</div>
                <div class="kpi-metric-sub">Simulated ECU Runs</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with kpi_col6:
        st.markdown(
            f"""
            <div class="kpi-metric-box">
                <div class="kpi-metric-label">Pass Rate</div>
                <div class="kpi-metric-val">{pass_rate_str}</div>
                <div class="kpi-metric-sub">First-Pass Verdict</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Section C: System Health
    st.markdown("<div class='section-heading' style='margin-top:1.2rem;'>System Health & Runtime Status</div>", unsafe_allow_html=True)
    h_col1, h_col2, h_col3, h_col4, h_col5 = st.columns(5)

    llm_client = LLMClientFactory.get_client()
    ollama_active = llm_client.is_available()

    with h_col1:
        st.markdown(
            """
            <div class="health-card">
                <div class="health-card-label">RAG Engine</div>
                <div class="health-status operational"><span class="dot dot-green"></span> OPERATIONAL</div>
                <div class="health-sub">ChromaDB isolated vector store</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with h_col2:
        st.markdown(
            """
            <div class="health-card">
                <div class="health-card-label">Rule Engine</div>
                <div class="health-status operational"><span class="dot dot-green"></span> OPERATIONAL</div>
                <div class="health-sub">15 ISO 14229 services active</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with h_col3:
        st.markdown(
            """
            <div class="health-card">
                <div class="health-card-label">Simulated ECU</div>
                <div class="health-status operational"><span class="dot dot-green"></span> OPERATIONAL</div>
                <div class="health-sub">In-process / Virtual CAN dual-tier</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with h_col4:
        st.markdown(
            """
            <div class="health-card">
                <div class="health-card-label">Database & Graph</div>
                <div class="health-status operational"><span class="dot dot-green"></span> OPERATIONAL</div>
                <div class="health-sub">SQLite WAL + NetworkX DiGraph</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with h_col5:
        if ollama_active:
            st.markdown(
                """
                <div class="health-card">
                    <div class="health-card-label">LLM Runtime</div>
                    <div class="health-status operational"><span class="dot dot-green"></span> OLLAMA ACTIVE</div>
                    <div class="health-sub">Llama 3.1 8B • Local runtime</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                """
                <div class="health-card">
                    <div class="health-card-label">LLM Runtime</div>
                    <div class="health-status warning"><span class="dot dot-amber"></span> FALLBACK MOCK</div>
                    <div class="health-sub">Ollama offline • Deterministic active</div>
                </div>
                """,
                unsafe_allow_html=True
            )

    # Section D: End-to-End Diagnostic Pipeline
    st.markdown("<div class='section-heading' style='margin-top:1.2rem;'>Diagnostic Engineering Pipeline</div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="pipeline-container">
            <div class="pipeline-step">Specification Ingestion</div>
            <div class="pipeline-arrow">➔</div>
            <div class="pipeline-step">Knowledge Retrieval</div>
            <div class="pipeline-arrow">➔</div>
            <div class="pipeline-step">Rule Verification</div>
            <div class="pipeline-arrow">➔</div>
            <div class="pipeline-step">Test Generation</div>
            <div class="pipeline-arrow">➔</div>
            <div class="pipeline-step">Human Review</div>
            <div class="pipeline-arrow">➔</div>
            <div class="pipeline-step">ECU Execution</div>
            <div class="pipeline-arrow">➔</div>
            <div class="pipeline-step">Script Export & Traceability</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Section E: Collapsible Architecture & Governance Decisions
    with st.expander("🏛️ Approved Architecture & Governance Decisions (AD-01, AD-02, AD-03)", expanded=False):
        st.markdown(
            """
            <div style="font-size:0.82rem; line-height:1.7; color:#CBD5E1;">
                <div style="margin-bottom:0.75rem;">
                    <b>AD-01 — LLM Model & Host Strategy:</b><br>
                    <span style="color:#94A3B8;">Approved:</span> Local Llama 3.1 8B (or Qwen 2.5 7B) via Ollama, subject to hardware feasibility.
                </div>
                <div style="margin-bottom:0.75rem;">
                    <b>AD-02 — Traceability Graph Store:</b><br>
                    <span style="color:#94A3B8;">Approved:</span> SQLite + NetworkX relational graph equivalent.
                </div>
                <div>
                    <b>AD-03 — Bus / ECU Execution Architecture:</b><br>
                    <span style="color:#94A3B8;">Approved:</span> Decoupled dual-tier architecture:
                    <ul style="margin:0.25rem 0 0 1.2rem; padding:0; color:#94A3B8;">
                        <li><code>SimulatedECUAdapter</code> / in-process simulated ECU is the default regression engine.</li>
                        <li><code>VirtualCANBusAdapter</code> / python-can virtual bus is optional integration support where required.</li>
                    </ul>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Section F: Recent Workspace Activity
    st.markdown("<div class='section-heading' style='margin-top:1.2rem;'>Recent Activity</div>", unsafe_allow_html=True)
    recent_events = activity_store.get_events(project_id=active_ws.project_id, limit=8)
    if not recent_events:
        st.markdown(
            """
            <div class="empty-state-box">
                <div style="font-weight:600; color:#E2E8F0; font-size:0.9rem;">No activity recorded for this workspace yet.</div>
                <div style="color:#64748B; font-size:0.78rem; margin-top:0.25rem;">
                    Activity will appear here as documents, tests, reviews, and executions are performed.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        ev_rows = []
        for ev in recent_events:
            status_badge = "PASS" if ev.status == "SUCCESS" else ev.status
            ev_rows.append({
                "Timestamp (UTC)": ev.timestamp_utc[:19].replace("T", " "),
                "Action": ev.action,
                "Status": status_badge,
                "Latency (ms)": f"{ev.duration_ms:.1f}",
                "Session / User": ev.user_id if ev.is_authenticated else ev.session_id,
                "Details": str(ev.metadata) if ev.metadata else "-"
            })
        st.dataframe(ev_rows, use_container_width=True)
