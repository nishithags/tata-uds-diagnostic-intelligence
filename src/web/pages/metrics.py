"""
Coverage & Metrics Page for UDS Diagnostic Intelligence Platform.
Displays Section 11 enterprise KPI scorecard telemetry and immutable governance audit records.
"""

import streamlit as st
from src.core.analytics import analytics_engine
from src.core.governance import governance_manager
from src.core.test_case_store import test_case_store


def render_metrics_page(active_ws):
    """Renders the Enterprise KPI Scorecard and Governance Audit Trail."""
    st.markdown("### 📊 Coverage & Enterprise Metrics")
    st.caption(
        f"Workspace: **`{active_ws.name}`** (`{active_ws.project_id}`). "
        "Empirical measurement telemetry aligned with Tata Technologies Case Study 5 (Section 11, p. 22)."
    )

    tab_kpi, tab_audit = st.tabs([
        "📈 Enterprise KPI Scorecard",
        "🛡️ Immutable Governance Audit Trail"
    ])

    with tab_kpi:
        st.markdown("##### Section 11 Success Metrics Telemetry")
        st.info(
            "🛡️ **STRICT MEASUREMENT TELEMETRY:** All metrics below display **measured empirical values** vs **company benchmark targets**. "
            "Company targets are benchmarks and are never presented as achieved values."
        )

        test_cases = test_case_store.list_test_cases(active_ws.project_id)
        metrics = analytics_engine.compute_metrics(active_ws.project_id, test_cases)

        ov1, ov2, ov3 = st.columns(3)
        ov1.metric("Total Test Cases", metrics.total_test_cases)
        ov2.metric("Total Execution Runs", metrics.total_execution_runs)
        ov3.metric("Telemetry Computed At", metrics.computed_at.split("T")[1][:8] if "T" in metrics.computed_at else metrics.computed_at)

        st.markdown("---")

        def render_kpi_card(metric_data, icon: str):
            status_map = {
                "ACHIEVED": ("badge-pass", "TARGET MET"),
                "BELOW_TARGET": ("badge-warn", "BELOW TARGET"),
                "NEEDS_DATA": ("badge-draft", "NEEDS DATA"),
                "METHODOLOGY_PENDING": ("badge-info", "METHODOLOGY PENDING")
            }
            badge_class, badge_label = status_map.get(metric_data.status, ("badge-info", metric_data.status))

            st.markdown(
                f"""
                <div class="eng-card">
                    <div class="eng-card-header">
                        <span>{icon} {metric_data.metric_name}</span>
                        <span class="{badge_class}">{badge_label}</span>
                    </div>
                    <div style="font-size:0.75rem; color:#94A3B8; margin-bottom:0.75rem;">
                        {metric_data.description}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            c1, c2, c3 = st.columns(3)
            c1.metric("Empirical Measured Value", f"{metric_data.measured_value} {metric_data.unit}")
            c2.metric("Company Benchmark Target", f"{metric_data.target_value} {metric_data.unit}")
            c3.markdown(f"**Target Objective:**\n{metric_data.target_label}")

            st.caption(f"**Analysis & Evidence:** {metric_data.analysis_note}")
            st.markdown("---")

        render_kpi_card(metrics.test_design_time, "⏱️")
        render_kpi_card(metrics.generation_accuracy, "🎯")
        render_kpi_card(metrics.coverage_improvement, "🔄")
        render_kpi_card(metrics.reuse_rate, "🧱")
        render_kpi_card(metrics.defect_detection, "🐞")

    with tab_audit:
        st.markdown("##### Immutable Governance Audit Trail")
        st.caption(
            "Records all test generation events, rule verification verdicts, review decisions, "
            "and blocked execution attempts with cryptographic timestamps and user identities."
        )

        audit_events = governance_manager.get_audit_trail(active_ws.project_id)
        if not audit_events:
            st.info("No audit events recorded for this workspace yet.")
        else:
            st.caption(f"Recorded Governance Events: **{len(audit_events)}**")
            audit_rows = []
            for ev in reversed(audit_events):
                audit_rows.append({
                    "Timestamp (UTC)": ev.get("created_at", "")[:19].replace("T", " "),
                    "Audit ID": ev.get("audit_id", ""),
                    "Event Type": ev.get("event_type", ""),
                    "Performed By": ev.get("performed_by", ""),
                    "Details": str(ev.get("details", {}))
                })
            st.dataframe(audit_rows, use_container_width=True)

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
