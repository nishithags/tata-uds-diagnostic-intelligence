"""
Custom CSS Theme for Tata Technologies UDS Diagnostic Intelligence Platform.
Engineered dark engineering theme: deep navy surfaces, crisp typography,
refined status indicators, and compact information hierarchy.
"""

import streamlit as st


def inject_custom_theme():
    """Injects professional automotive engineering CSS styles into Streamlit."""
    theme_css = """
    <style>
    /* ==========================================================
       GLOBAL SURFACE & TYPOGRAPHY
       ========================================================== */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    code, pre, .stCode, [data-testid="stTable"] td, .mono-text {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Backgrounds */
    .stApp {
        background-color: #0B1120;
        color: #F8FAFC;
    }

    [data-testid="stSidebar"] {
        background-color: #0F172A !important;
        border-right: 1px solid #1E293B !important;
    }

    [data-testid="stSidebarNav"] {
        padding-top: 0.5rem;
    }

    /* Compact Main Container */
    .main .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        max-width: 96% !important;
    }

    /* ==========================================================
       GLOBAL APPLICATION HEADER
       ========================================================== */
    .app-global-header {
        background: linear-gradient(180deg, #131E33 0%, #0F172A 100%);
        border: 1px solid #1E293B;
        border-radius: 8px;
        padding: 0.9rem 1.4rem;
        margin-bottom: 1.2rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    }

    .app-header-left {
        display: flex;
        flex-direction: column;
    }

    .app-header-title {
        font-size: 1.15rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        color: #38BDF8;
        text-transform: uppercase;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .app-header-subtitle {
        font-size: 0.8rem;
        color: #94A3B8;
        margin-top: 0.15rem;
        letter-spacing: 0.02em;
    }

    .app-header-right {
        display: flex;
        align-items: center;
        gap: 1.2rem;
    }

    .workspace-pill {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 4px;
        padding: 0.25rem 0.65rem;
        font-size: 0.75rem;
        color: #E2E8F0;
        font-weight: 500;
    }

    .status-indicators {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

    .status-dot {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        font-size: 0.72rem;
        color: #CBD5E1;
        font-weight: 500;
    }

    .dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        display: inline-block;
    }

    .dot-green { background-color: #10B981; box-shadow: 0 0 6px #10B98188; }
    .dot-amber { background-color: #F59E0B; box-shadow: 0 0 6px #F59E0B88; }
    .dot-red   { background-color: #EF4444; box-shadow: 0 0 6px #EF444488; }
    .dot-blue  { background-color: #38BDF8; box-shadow: 0 0 6px #38BDF888; }

    /* ==========================================================
       SIDEBAR BRANDING
       ========================================================== */
    .sidebar-brand-box {
        padding: 0.75rem 0.5rem 1rem 0.5rem;
        border-bottom: 1px solid #1E293B;
        margin-bottom: 0.75rem;
    }

    .sidebar-brand-title {
        font-size: 0.95rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        color: #38BDF8;
        text-transform: uppercase;
        margin: 0;
    }

    .sidebar-brand-sub {
        font-size: 0.72rem;
        color: #64748B;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-top: 0.2rem;
    }

    .sidebar-section-label {
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #64748B;
        margin-top: 0.5rem;
        margin-bottom: 0.35rem;
    }

    .sidebar-context-card {
        background-color: #131E33;
        border: 1px solid #1E293B;
        border-radius: 6px;
        padding: 0.65rem 0.75rem;
        margin-top: 0.65rem;
        margin-bottom: 0.75rem;
        font-size: 0.73rem;
        color: #94A3B8;
        line-height: 1.45;
    }

    .ctx-label {
        color: #64748B;
        font-weight: 600;
    }

    .ctx-val {
        color: #E2E8F0;
        font-weight: 500;
    }

    .sidebar-footer-box {
        margin-top: 1.5rem;
        padding: 0.65rem 0.75rem;
        background-color: #0B1120;
        border: 1px solid #1E293B;
        border-radius: 6px;
    }

    /* ==========================================================
       OVERVIEW & SECTION HEADINGS
       ========================================================== */
    .overview-header-box {
        background: linear-gradient(180deg, #131E33 0%, #0F172A 100%);
        border: 1px solid #1E293B;
        border-radius: 8px;
        padding: 1.1rem 1.4rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }

    .ov-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #38BDF8;
        letter-spacing: 0.02em;
        margin-bottom: 0.35rem;
    }

    .ov-meta {
        font-size: 0.8rem;
        color: #94A3B8;
        display: flex;
        align-items: center;
        gap: 0.6rem;
        flex-wrap: wrap;
        margin-bottom: 0.5rem;
    }

    .ov-sep {
        color: #475569;
    }

    .ov-desc {
        font-size: 0.82rem;
        color: #CBD5E1;
        line-height: 1.5;
    }

    .section-heading {
        font-size: 0.85rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #94A3B8;
        margin-bottom: 0.65rem;
        padding-bottom: 0.35rem;
        border-bottom: 1px solid #1E293B;
    }

    /* ==========================================================
       ENGINEERING CARDS & METRICS
       ========================================================== */
    .eng-card {
        background-color: #131E33;
        border: 1px solid #1E293B;
        border-radius: 6px;
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
    }

    .eng-card-header {
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94A3B8;
        margin-bottom: 0.75rem;
        border-bottom: 1px solid #1E293B;
        padding-bottom: 0.4rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .kpi-metric-box {
        background: #111B2E;
        border: 1px solid #1E293B;
        border-radius: 6px;
        padding: 0.8rem 1rem;
        text-align: left;
    }

    .kpi-metric-label {
        font-size: 0.72rem;
        font-weight: 600;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.25rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .kpi-metric-val {
        font-size: 1.45rem;
        font-weight: 700;
        color: #F8FAFC;
        line-height: 1.2;
        white-space: nowrap;
    }

    .kpi-metric-sub {
        font-size: 0.7rem;
        color: #64748B;
        margin-top: 0.25rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .health-card {
        background: #111B2E;
        border: 1px solid #1E293B;
        border-radius: 6px;
        padding: 0.75rem 0.9rem;
        text-align: left;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 84px;
    }

    .health-card-label {
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94A3B8;
        margin-bottom: 0.2rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .health-status {
        font-size: 0.78rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 0.35rem;
        margin: 0.2rem 0;
        white-space: nowrap;
    }

    .health-status.operational {
        color: #34D399;
    }

    .health-status.warning {
        color: #FBBF24;
    }

    .health-sub {
        font-size: 0.68rem;
        color: #64748B;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .empty-state-box {
        background: #111B2E;
        border: 1px dashed #334155;
        border-radius: 6px;
        padding: 1.5rem;
        text-align: center;
        margin: 0.75rem 0;
    }

    /* ==========================================================
       BADGES & STATUS
       ========================================================== */
    .badge-pass {
        background-color: #064E3B;
        color: #34D399;
        border: 1px solid #059669;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        display: inline-block;
    }

    .badge-fail {
        background-color: #450A0A;
        color: #F87171;
        border: 1px solid #DC2626;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        display: inline-block;
    }

    .badge-warn {
        background-color: #451A03;
        color: #FBBF24;
        border: 1px solid #D97706;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        display: inline-block;
    }

    .badge-info {
        background-color: #082F49;
        color: #38BDF8;
        border: 1px solid #0284C7;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        display: inline-block;
    }

    .badge-draft {
        background-color: #1E293B;
        color: #94A3B8;
        border: 1px solid #334155;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        display: inline-block;
    }

    /* Workflow Pipeline step cards */
    .pipeline-container {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        flex-wrap: wrap;
        margin: 1rem 0;
    }

    .pipeline-step {
        background-color: #131E33;
        border: 1px solid #1E293B;
        border-radius: 6px;
        padding: 0.5rem 0.75rem;
        font-size: 0.75rem;
        font-weight: 600;
        color: #E2E8F0;
        display: flex;
        align-items: center;
        gap: 0.4rem;
        white-space: nowrap;
    }

    .pipeline-arrow {
        color: #475569;
        font-size: 0.8rem;
    }

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        border-bottom: 1px solid #1E293B;
        padding-bottom: 0.25rem;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: transparent !important;
        border: 1px solid transparent !important;
        border-radius: 4px !important;
        padding: 0.4rem 0.9rem !important;
        color: #94A3B8 !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
    }

    .stTabs [aria-selected="true"] {
        background-color: #1E293B !important;
        border: 1px solid #334155 !important;
        color: #38BDF8 !important;
    }

    /* Streamlit widget tweaks */
    div[data-baseweb="select"] > div {
        background-color: #0F172A !important;
        border-color: #334155 !important;
        color: #F8FAFC !important;
        border-radius: 4px !important;
    }

    input, textarea {
        background-color: #0F172A !important;
        border-color: #334155 !important;
        color: #F8FAFC !important;
        border-radius: 4px !important;
    }

    /* Button Styling */
    .stButton > button {
        border-radius: 4px !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em !important;
        font-size: 0.85rem !important;
        transition: all 0.15s ease-in-out !important;
    }

    .stButton > button[kind="primary"] {
        background-color: #0284C7 !important;
        border: 1px solid #0369A1 !important;
        color: #FFFFFF !important;
    }

    .stButton > button[kind="primary"]:hover {
        background-color: #0369A1 !important;
        border-color: #075985 !important;
        box-shadow: 0 0 10px rgba(2, 132, 199, 0.4) !important;
    }

    .stButton > button[kind="secondary"] {
        background-color: #1E293B !important;
        border: 1px solid #334155 !important;
        color: #E2E8F0 !important;
    }

    /* Table styling */
    div[data-testid="stTable"] table {
        border: 1px solid #1E293B !important;
        border-radius: 6px !important;
    }

    div[data-testid="stTable"] th {
        background-color: #111B2E !important;
        color: #94A3B8 !important;
        font-weight: 600 !important;
        font-size: 0.75rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
        border-bottom: 1px solid #1E293B !important;
    }

    div[data-testid="stTable"] td {
        background-color: #0B1120 !important;
        color: #F1F5F9 !important;
        font-size: 0.8rem !important;
        border-bottom: 1px solid #131E33 !important;
    }

    /* Expander styling */
    div[data-testid="stExpander"] {
        background-color: #131E33 !important;
        border: 1px solid #1E293B !important;
        border-radius: 6px !important;
        margin-bottom: 0.75rem !important;
    }

    div[data-testid="stExpander"] details summary {
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        color: #E2E8F0 !important;
    }

    /* Metric cards default override */
    div[data-testid="stMetric"] {
        background-color: #131E33;
        border: 1px solid #1E293B;
        border-radius: 6px;
        padding: 0.75rem 1rem;
    }

    div[data-testid="stMetricLabel"] {
        color: #94A3B8 !important;
        font-size: 0.75rem !important;
        text-transform: uppercase !important;
        font-weight: 600 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    div[data-testid="stMetricValue"] {
        color: #F8FAFC !important;
        font-size: 1.35rem !important;
        font-weight: 700 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    </style>
    """
    st.markdown(theme_css, unsafe_allow_html=True)
