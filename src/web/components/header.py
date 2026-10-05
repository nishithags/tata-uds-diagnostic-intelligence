"""
Global Application Header Component.
Provides a persistent engineering status banner across all pages.
Main header displays current workspace context and aligned system status indicators.
"""

import streamlit as st
from src.core.llm_interface import LLMClientFactory


def render_global_header(active_ws):
    """Renders the top application header with system telemetry and active workspace context."""
    # LLM status check
    try:
        client = LLMClientFactory.get_client()
        ollama_active = client.is_available()
    except Exception:
        ollama_active = False

    llm_dot = "dot-green" if ollama_active else "dot-amber"
    llm_label = "Ollama Active" if ollama_active else "Fallback Mock"

    ws_name = active_ws.name if active_ws else "Tata Technologies UDS Diagnostic Pilot"
    ws_id = active_ws.project_id if active_ws else "tata_uds_pilot"

    header_html = f"""
    <div class="app-global-header">
        <div class="app-header-left">
            <div class="app-header-title">
                {ws_name}
            </div>
            <div class="app-header-subtitle">
                Rule-Verified UDS Diagnostic Engineering Workspace
            </div>
        </div>
        <div class="app-header-right">
            <div class="workspace-pill">
                <span style="color:#64748B;">Workspace:</span> <b>{ws_id}</b>
            </div>
            <div class="status-indicators">
                <span class="status-dot"><span class="dot dot-green"></span> RAG</span>
                <span class="status-dot"><span class="dot dot-green"></span> Rules</span>
                <span class="status-dot"><span class="dot dot-green"></span> ECU</span>
                <span class="status-dot"><span class="dot dot-green"></span> Database</span>
                <span class="status-dot"><span class="dot {llm_dot}"></span> {llm_label}</span>
            </div>
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)
