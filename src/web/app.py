"""
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
Automotive Diagnostic Intelligence Platform — Streamlit Entrypoint.

Approved Architectural Decisions:
- AD-01: LLM Model & Host Strategy — Local Llama 3.1 8B (or Qwen 2.5 7B) via Ollama, subject to hardware feasibility.
- AD-02: Traceability Graph Store — SQLite + NetworkX relational graph equivalent.
- AD-03: Bus / ECU Execution Architecture — Decoupled dual-tier architecture (SimulatedECUAdapter regression engine default, VirtualCANBusAdapter optional integration support).
"""

import sys
from pathlib import Path
import uuid

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st

from src.core.config import config
from src.core.llm_interface import LLMClientFactory
from src.core.vector_store import IsolatedVectorStore
from src.core.workspace_manager import workspace_manager
from src.web.components.header import render_global_header
from src.web.pages.admin_activity import render_admin_activity_page
from src.web.pages.documents import render_documents_page
from src.web.pages.execution import render_execution_page
from src.web.pages.export_opt import render_export_opt_page
from src.web.pages.knowledge import render_knowledge_page
from src.web.pages.metrics import render_metrics_page
from src.web.pages.overview import render_overview_page
from src.web.pages.test_studio import render_test_studio_page
from src.web.pages.traceability import render_traceability_page
from src.web.styles.theme import inject_custom_theme

# ==========================================================
# PAGE CONFIGURATION & THEME
# ==========================================================
st.set_page_config(
    page_title="Tata Technologies — UDS Diagnostic Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

inject_custom_theme()

# ==========================================================
# SESSION STATE INITIALIZATION
# ==========================================================
if "session_id" not in st.session_state:
    st.session_state.session_id = f"sess_{uuid.uuid4().hex[:12]}"
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

# ==========================================================
# SIDEBAR: PRODUCT BRANDING & ACTIVE WORKSPACE
# ==========================================================
workspaces = workspace_manager.list_workspaces()
ws_options = {ws.project_id: f"{ws.name} ({ws.project_id})" for ws in workspaces}

if "active_project_id" not in st.session_state:
    st.session_state.active_project_id = workspaces[0].project_id if workspaces else "tata_uds_pilot"

# Product identity in sidebar
st.sidebar.markdown(
    """
    <div class="sidebar-brand-box">
        <div class="sidebar-brand-title">UDS DIAGNOSTIC<br>INTELLIGENCE</div>
        <div class="sidebar-brand-sub">Automotive Engineering AI<br>Case Study 5</div>
    </div>
    """,
    unsafe_allow_html=True
)

# Compact Active Workspace selector
st.sidebar.markdown("<div class='sidebar-section-label'>Active Workspace</div>", unsafe_allow_html=True)
selected_ws_id = st.sidebar.selectbox(
    "Active Workspace",
    options=list(ws_options.keys()),
    format_func=lambda x: ws_options.get(x, x),
    index=list(ws_options.keys()).index(st.session_state.active_project_id) if st.session_state.active_project_id in ws_options else 0,
    label_visibility="collapsed"
)
st.session_state.active_project_id = selected_ws_id

active_ws = workspace_manager.get_workspace(st.session_state.active_project_id)
if active_ws:
    vstore = IsolatedVectorStore()
    total_docs = len(active_ws.documents)
    total_chunks = vstore.count_chunks(active_ws.project_id)
    st.sidebar.markdown(
        f"""
        <div class="sidebar-context-card">
            <div><span class="ctx-label">Target ECU:</span> <span class="ctx-val">Powertrain & Body Diagnostic Controller</span></div>
            <div><span class="ctx-label">Project Reference:</span> <span class="ctx-val">Tata Technologies Case Study 5</span></div>
            <div style="margin-top:0.3rem; padding-top:0.3rem; border-top:1px solid #1E293B; display:flex; justify-content:space-between;">
                <span><b>Docs:</b> {total_docs}</span>
                <span><b>Chunks:</b> {total_chunks}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# Compact sidebar footer status
st.sidebar.markdown(
    """
    <div class="sidebar-footer-box">
        <div style="font-size:0.68rem; font-weight:600; color:#94A3B8; text-transform:uppercase; letter-spacing:0.05em;">System Status</div>
        <div style="margin-top:0.25rem; font-size:0.72rem; color:#34D399; font-weight:600; display:flex; align-items:center; gap:0.4rem;">
            <span class="dot dot-green"></span> System Operational
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# ==========================================================
# PAGE DEFINITIONS & WRAPPERS
# ==========================================================
def page_overview():
    render_global_header(active_ws)
    render_overview_page(active_ws)


def page_knowledge():
    render_global_header(active_ws)
    render_knowledge_page(active_ws)


def page_documents():
    render_global_header(active_ws)
    render_documents_page(active_ws)


def page_test_studio():
    render_global_header(active_ws)
    render_test_studio_page(active_ws)


def page_execution():
    render_global_header(active_ws)
    render_execution_page(active_ws)


def page_export():
    render_global_header(active_ws)
    render_export_opt_page(active_ws)


def page_traceability():
    render_global_header(active_ws)
    render_traceability_page(active_ws)


def page_metrics():
    render_global_header(active_ws)
    render_metrics_page(active_ws)


def page_admin():
    render_global_header(active_ws)
    render_admin_activity_page(active_ws)


# ==========================================================
# NAVIGATION ARCHITECTURE (GROUPED SIDEBAR)
# ==========================================================
pages = {
    "WORKSPACE": [
        st.Page(page_overview, title="Overview", icon="🏠", default=True)
    ],
    "KNOWLEDGE": [
        st.Page(page_knowledge, title="Knowledge Q&A", icon="🔎"),
        st.Page(page_documents, title="Documents", icon="📄")
    ],
    "TESTING": [
        st.Page(page_test_studio, title="Test Studio", icon="🧪"),
        st.Page(page_execution, title="Execution", icon="⚡"),
        st.Page(page_export, title="Export & Optimization", icon="📦")
    ],
    "ANALYSIS": [
        st.Page(page_traceability, title="Traceability", icon="🔗"),
        st.Page(page_metrics, title="Coverage & Metrics", icon="📊")
    ],
    "ADMIN": [
        st.Page(page_admin, title="Activity Dashboard", icon="🛡")
    ]
}

router = st.navigation(pages, position="sidebar", expanded=True)
router.run()
