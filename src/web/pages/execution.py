"""
Execution Page for UDS Diagnostic Intelligence Platform.
Provides virtual simulated ECU execution, real-time diagnostic telemetry,
fault injection controls, step trace inspection, and execution history.
"""

import streamlit as st
from src.core.activity_store import ActivityAction, activity_store
from src.core.execution_engine import FaultProfile, execution_engine
from src.core.execution_store import execution_store
from src.core.governance import GovernanceError
from src.core.rules import STANDARD_NRCS
from src.core.simulator import simulated_ecu
from src.core.test_case_store import test_case_store


def render_execution_page(active_ws):
    """Renders the Simulated ECU Execution & Diagnostic dashboard."""
    st.markdown("### ⚡ Simulated ECU — Execution & Diagnostics")
    st.caption(
        f"Workspace: **`{active_ws.name}`** (`{active_ws.project_id}`) | "
        "Target ECU: **`Powertrain & Body Diagnostic Controller`** | "
        "Project Reference: **`Tata Technologies Case Study 5`**\n\n"
        "Executes formally APPROVED diagnostic tests against the Software-in-the-Loop Simulated ECU. "
        "Enforces ISO 14229 state transitions, P2/P2* timing, fault injection profiles, and immutable execution logs."
    )

    # 1. Real-Time ECU Status Cards
    st.markdown("##### 🖥️ Simulated ECU Real-Time Telemetry")
    ecu_snapshot = simulated_ecu.get_snapshot()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("ECU State", "ONLINE", "Simulated SIL")
    c2.metric("Active Session", ecu_snapshot.session)
    c3.metric("Security Level", f"Level {ecu_snapshot.security_level}", "Locked" if ecu_snapshot.security_locked else "Unlocked")
    c4.metric("S3 Timer", "Active" if ecu_snapshot.s3_timer_active else "Idle")
    c5.metric("DTC Count", ecu_snapshot.dtc_count)

    col_rst, _ = st.columns([2, 5])
    if col_rst.button("🔄 Reset ECU to Power-On State"):
        simulated_ecu.reset_state()
        activity_store.log_activity(
            session_id=st.session_state.session_id,
            user_id=st.session_state.user_id,
            project_id=active_ws.project_id,
            action=ActivityAction.ECU_RESET,
            endpoint="UI",
            http_method="UI",
            status="SUCCESS"
        )
        st.success("ECU reset to DEFAULT session, LOCKED security level, and nominal memory map.")
        st.rerun()

    st.markdown("---")

    # 2. Select Test Case & Execution Gating
    st.markdown("##### 🚀 Test Case Execution")
    workspace_test_cases = test_case_store.list_test_cases(active_ws.project_id)

    if not workspace_test_cases:
        st.info("No test cases found in this workspace. Generate test cases in the Test Studio first.")
        return

    tc_dict = {tc.test_case_id: tc for tc in workspace_test_cases}
    selected_tc_id = st.selectbox(
        "Select Diagnostic Test Case",
        options=list(tc_dict.keys()),
        format_func=lambda tid: f"[{tc_dict[tid].review_status}] {tid} — {tc_dict[tid].title}"
    )
    selected_tc = tc_dict[selected_tc_id]

    is_approved = (selected_tc.review_status == "APPROVED")

    if is_approved:
        st.success(f"✅ **GOVERNANCE STATUS: APPROVED** — Test case `{selected_tc.test_case_id}` is authorized for simulation execution.")
    else:
        st.error(
            f"⛔ **GOVERNANCE ENFORCEMENT: BLOCKED** — Test case `{selected_tc.test_case_id}` status is **`{selected_tc.review_status}`**.\n\n"
            "Human approval is strictly required before execution. Please review and approve this test in Test Studio."
        )

    # Fault Injection (collapsed by default)
    with st.expander("🛠️ Advanced / Fault Injection Profile", expanded=False):
        st.caption("Inject anomalies into the simulated bus to verify negative test handling and timing resilience.")
        f_col1, f_col2 = st.columns(2)
        forced_nrc_val = f_col1.selectbox(
            "Forced Negative Response Code (NRC)",
            options=[None, 0x12, 0x13, 0x22, 0x31, 0x33, 0x35, 0x7E, 0x7F],
            format_func=lambda x: "None (Nominal Behavior)" if x is None else f"0x{x:02X} ({STANDARD_NRCS.get(x, 'Custom')})"
        )
        resp_delay = f_col2.slider("Synthetic Response Delay (ms)", min_value=0, max_value=500, value=0, step=10)

        c_col1, c_col2 = st.columns(2)
        corrupt_len = c_col1.checkbox("Corrupt / Truncate Response Length")
        drop_resp = c_col2.checkbox("Simulate Dead ECU (Drop Response / Timeout)")

    fault_prof = None
    if forced_nrc_val is not None or resp_delay > 0 or corrupt_len or drop_resp:
        fault_prof = FaultProfile(
            forced_nrc=forced_nrc_val,
            response_delay_ms=resp_delay,
            corrupt_response_length=corrupt_len,
            drop_response=drop_resp
        )

    exec_col, _ = st.columns([1, 4])
    run_btn = exec_col.button(
        "⚡ Run Test",
        type="primary",
        disabled=(not is_approved)
    )

    if run_btn:
        with st.spinner(f"Transmitting diagnostic frames for '{selected_tc.test_case_id}' to Simulated ECU..."):
            try:
                exec_result = execution_engine.execute_test_case(
                    test_case=selected_tc,
                    fault_profile=fault_prof,
                    operator_name="Validation Engineer (UI)"
                )
                execution_store.save_execution_result(exec_result)

                activity_store.log_activity(
                    session_id=st.session_state.session_id,
                    user_id=st.session_state.user_id or "Validation Engineer (UI)",
                    project_id=active_ws.project_id,
                    action=ActivityAction.TEST_EXECUTED,
                    endpoint="UI",
                    http_method="UI",
                    test_case_id=selected_tc.test_case_id,
                    status="SUCCESS" if exec_result.overall_verdict == "PASS" else "FAILURE",
                    duration_ms=exec_result.total_elapsed_ms,
                    metadata={
                        "verdict": exec_result.overall_verdict,
                        "steps_total": exec_result.steps_total,
                        "steps_passed": exec_result.steps_passed
                    }
                )

                st.markdown("---")
                st.markdown("#### 🏁 Execution Result")

                r_col1, r_col2, r_col3 = st.columns(3)
                if exec_result.overall_verdict == "PASS":
                    r_col1.success(f"**OVERALL VERDICT:** {exec_result.overall_verdict}")
                else:
                    r_col1.error(f"**OVERALL VERDICT:** {exec_result.overall_verdict}")
                r_col2.metric("Turnaround Latency", f"{exec_result.total_elapsed_ms:.1f} ms")
                r_col3.metric("Steps Verdict", f"{exec_result.steps_passed} / {exec_result.steps_total} Passed")

                # Step CAN Trace Table
                st.markdown("##### 📡 CAN Trace & Frame Validation")
                trace_table = []
                for s in exec_result.step_results:
                    trace_table.append({
                        "Step #": s.step_number,
                        "Request (Hex)": s.request_hex,
                        "Actual Response (Hex)": s.actual_response_hex or "<EMPTY / SUPPRESSED>",
                        "Expected Response": s.expected_response_hex or (f"NRC {s.expected_nrc}" if s.expected_nrc else "-"),
                        "Latency (ms)": f"{s.elapsed_ms:.1f}",
                        "Timing": "✅ PASS" if s.timing_verdict == "PASS" else "❌ TIMEOUT",
                        "Verdict": "✅ PASS" if s.step_verdict == "PASS" else "❌ FAIL"
                    })
                st.table(trace_table)

                with st.expander("📋 ECU Internal State Transitions & Decision Log"):
                    for s in exec_result.step_results:
                        st.markdown(f"**Step {s.step_number}:** `{s.description}`")
                        for line in s.trace_logs:
                            st.text(f"  > {line}")
                        if s.error_message:
                            st.error(f"  Error: {s.error_message}")

                st.caption(f"Immutable Audit Record: `{exec_result.audit_id}`")

            except GovernanceError as ge:
                st.error(f"⛔ Governance Blocker: {str(ge)}")
            except Exception as e:
                st.error(f"Execution Error: {str(e)}")

    st.markdown("---")

    # 3. Workspace Execution History
    st.markdown(f"##### 📜 Execution History — {active_ws.name}")
    past_runs = execution_store.list_execution_results(active_ws.project_id)
    if not past_runs:
        st.info("No past execution runs recorded for this workspace yet.")
    else:
        st.caption(f"Total Execution Runs: **{len(past_runs)}**")
        history_rows = []
        for r in reversed(past_runs):
            history_rows.append({
                "Execution ID": r.execution_id,
                "Test Case ID": r.test_case_id,
                "Title": r.title,
                "Type": r.test_type,
                "Verdict": "✅ PASS" if r.overall_verdict == "PASS" else "❌ FAIL",
                "Steps": f"{r.steps_passed}/{r.steps_total}",
                "Turnaround (ms)": f"{r.total_elapsed_ms:.1f}",
                "Executed At": r.executed_at[:19].replace("T", " ")
            })
        st.dataframe(history_rows, use_container_width=True)
