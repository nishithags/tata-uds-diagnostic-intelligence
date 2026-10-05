"""
Administrator Activity Dashboard Page for UDS Diagnostic Intelligence Platform.
Provides privacy-conscious user activity logging, knowledge query telemetry,
identity classification, and security audit analytics protected by an admin key.
"""

import streamlit as st
from src.core.activity_store import ActivityAction, activity_store
from src.core.config import config
from src.core.workspace_manager import workspace_manager


def render_admin_activity_page(active_ws):
    """Renders the Administrator Activity Dashboard."""
    st.markdown("### 🛡️ Administrator Activity Dashboard")
    st.caption("Privacy-conscious user activity telemetry, query history, and security audit analytics.")

    # 1. Administrator Authentication Gate
    if not config.admin_api_key:
        st.error(
            "🔒 **Administrator Access Disabled**: No administrator access key has been configured on this system. "
            "Please configure the `UDS_ADMIN_KEY` environment variable to enable the administrator dashboard."
        )
        return

    if not st.session_state.get("admin_authenticated", False):
        st.warning("🔒 **Administrator Access Required**")
        st.markdown(
            "This dashboard contains system security telemetry and user activity records. "
            "Access is restricted to authorized administrators. Enter the administrator key to unlock."
        )

        with st.form("admin_login_form"):
            admin_input = st.text_input(
                "Administrator Access Key",
                type="password",
                placeholder="Enter administrator key (configured via UDS_ADMIN_KEY)"
            )
            login_btn = st.form_submit_button("Unlock Administrator Dashboard", type="primary")

            if login_btn:
                if admin_input.strip() == config.admin_api_key:
                    st.session_state.admin_authenticated = True
                    st.success("Access granted! Unlocking dashboard...")
                    st.rerun()
                else:
                    st.error("Access denied: Invalid administrator key.")
        return

    # Authenticated Admin View
    col_status, col_lock = st.columns([4, 1])
    col_status.success("🔓 **Administrator Session Active** | Identity Verification Confirmed")
    if col_lock.button("🔒 Lock Dashboard", use_container_width=True):
        st.session_state.admin_authenticated = False
        st.rerun()

    st.markdown("---")

    # 2. Key Telemetry Metrics
    summary = activity_store.get_summary_stats()

    st.markdown("##### 📈 High-Level Telemetry KPIs")
    r1_1, r1_2, r1_3, r1_4 = st.columns(4)
    r1_1.metric("Total Events", summary["total_events"])
    r1_2.metric("Unique Sessions", summary["unique_sessions"])
    r1_3.metric("Knowledge Queries", summary["knowledge_queries_count"])
    r1_4.metric("Tests Generated", summary["tests_generated_count"])

    r2_1, r2_2, r2_3, r2_4 = st.columns(4)
    r2_1.metric("Tests Executed", summary["tests_executed_count"])
    r2_2.metric("Script Exports", summary["exports_count"])
    r2_3.metric("Successful Actions", summary["success_count"])
    r2_4.metric("Errors / Failures", summary["failure_count"])

    # 3. Identity Classification Banner
    st.markdown("##### 👥 Identity Classification")
    id1, id2 = st.columns(2)
    with id1:
        st.info(
            f"👤 **Anonymous Sessions:** `{summary['unique_anonymous_sessions']}` unique browser sessions\n\n"
            "*Users operate via cryptographically random anonymous identifiers (`sess_<id>`). "
            "No PII or user behavioral profiles are collected.*"
        )
    with id2:
        st.info(
            f"🔑 **Authenticated Users:** `{summary['unique_authenticated_users']}` identified accounts\n\n"
            "*Pilot operates in unauthenticated mode. Architecture is forward-compatible with enterprise SSO / IAM.*"
        )

    st.markdown("---")

    # 4. Filterable Activity Log
    st.markdown("##### 🔍 Activity Event Explorer & Filters")
    workspaces = workspace_manager.list_workspaces()

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        ws_choices = ["All Workspaces"] + [ws.project_id for ws in workspaces]
        sel_ws = st.selectbox("Workspace Filter", options=ws_choices)
    with f2:
        act_choices = ["All Actions"] + ActivityAction.ALL_ACTIONS
        sel_act = st.selectbox("Action Filter", options=act_choices)
    with f3:
        status_choices = ["All Statuses", "SUCCESS", "FAILURE", "ERROR"]
        sel_status = st.selectbox("Status Filter", options=status_choices)
    with f4:
        search_box = st.text_input("Search (Query, Session, ID)", placeholder="e.g. sess_ or 0x22")

    filter_ws = None if sel_ws == "All Workspaces" else sel_ws
    filter_act = None if sel_act == "All Actions" else sel_act
    filter_stat = None if sel_status == "All Statuses" else sel_status

    events = activity_store.get_events(
        project_id=filter_ws,
        action=filter_act,
        status=filter_stat,
        search_query=search_box if search_box.strip() else None,
        limit=150
    )

    if not events:
        st.info("No activity records matching selected filters.")
    else:
        table_rows = []
        for ev in events:
            user_label = f"🔑 {ev.user_id} (Auth)" if ev.is_authenticated else f"👤 {ev.session_id} (Anon)"
            table_rows.append({
                "Event ID": ev.event_id,
                "Timestamp (UTC)": ev.timestamp_utc[:19].replace("T", " "),
                "Identity": user_label,
                "Action": ev.action,
                "Workspace": ev.project_id or "global",
                "Status": "✅ SUCCESS" if ev.status == "SUCCESS" else f"❌ {ev.status}",
                "Latency (ms)": f"{ev.duration_ms:.1f}",
                "Endpoint": ev.endpoint or "UI"
            })
        st.dataframe(table_rows, use_container_width=True)

        with st.expander("🔎 Activity Event Detail Inspector"):
            event_options = [ev.event_id for ev in events]
            selected_event_id = st.selectbox("Select Event ID to Inspect", options=event_options)
            inspected_record = activity_store.get_event_by_id(selected_event_id)
            if inspected_record:
                st.json(inspected_record.model_dump())

    st.markdown("---")

    # 5. Knowledge Query History
    st.markdown("##### 📖 Knowledge Query History")
    st.caption("Complete, transparent history of all cited diagnostic specification inquiries.")

    q_search = st.text_input("Filter Queries by Keyword", placeholder="Search query keywords...")
    query_history = activity_store.get_knowledge_query_history(
        project_id=filter_ws,
        search_term=q_search if q_search.strip() else None,
        limit=100
    )

    if not query_history:
        st.info("No knowledge queries recorded matching criteria.")
    else:
        q_rows = []
        for qh in query_history:
            q_rows.append({
                "Session": qh["session_id"],
                "Query": qh["query"],
                "Result": qh["result"],
                "Time": qh["time"],
                "Workspace": qh["project_id"]
            })
        st.table(q_rows)

    st.markdown("---")

    # 6. Privacy & Data Governance Compliance
    with st.expander("🛡️ Privacy Policy & Security Architecture Compliance"):
        ip_status = "Disabled (Zero IP Collection)" if not config.log_client_ip else ("Enabled (Anonymized / Masked)" if config.anonymize_ip else "Enabled")
        st.markdown(f"""
        ### Telemetry Collection Specification:
        - **Client IP Logging:** `{ip_status}`
        - **Session Tracking:** Browser-isolated anonymous tokens (`sess_<uuid>`), retaining zero device fingerprints.
        - **Credential Redaction:** Passwords, API keys, tokens, secrets, and raw Authorization headers are automatically redacted prior to persistence.
        - **No Surveillance:** Zero keystroke tracking, mouse tracking, screen recording, or behavioral analysis.
        - **Data Location:** Local embedded SQLite database (`data/activity/activity_store.db`), strictly air-gapped without cloud egress.
        """)
