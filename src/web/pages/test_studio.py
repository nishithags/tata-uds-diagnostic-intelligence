"""
Test Studio Page for UDS Diagnostic Intelligence Platform.
Provides deterministic UDS diagnostic test generation, rule verification,
Human-in-the-Loop review sign-off, and ad-hoc custom frame checking.
"""

import streamlit as st
from src.core.activity_store import ActivityAction, activity_store
from src.core.generator import test_generator
from src.core.governance import GovernanceError, governance_manager
from src.core.rules import SERVICE_RULES, DiagnosticSession, SecurityLevel, rule_engine
from src.core.test_case_store import test_case_store


def render_test_studio_page(active_ws):
    """Renders the Test Studio & Rule Verification workspace."""
    st.markdown("### 🧪 UDS Test Studio & Rule Verification")
    st.caption(
        f"Generate and verify structured UDS diagnostic test cases for workspace **`{active_ws.name}`** (`{active_ws.project_id}`). "
        "Enforces deterministic ISO 14229 constraints (subfunctions, lengths, SPRMIB, session prerequisites, security gating, and NRCs)."
    )

    tab_gen, tab_custom = st.tabs([
        "⚙️ Automated Test Generator",
        "🔍 Custom Hex Frame Validator"
    ])

    with tab_gen:
        # Input Section
        st.markdown("##### Test Design Parameters")
        c1, c2, c3 = st.columns(3)

        with c1:
            service_options = list(SERVICE_RULES.keys())
            selected_sid = st.selectbox(
                "UDS Service (ISO 14229)",
                options=service_options,
                format_func=lambda s: f"0x{s:02X} — {SERVICE_RULES[s].service_name}"
            )
            rule_info = SERVICE_RULES[selected_sid]

        with c2:
            scenario_options = [
                ("POSITIVE", "Positive (Nominal Compliant Request)"),
                ("NEGATIVE_SUBFUNCTION", "Negative: Unsupported Subfunction (NRC 0x12)"),
                ("NEGATIVE_LENGTH", "Negative: Incorrect Message Length (NRC 0x13)"),
                ("NEGATIVE_SESSION", "Negative: Prohibited Session (NRC 0x7E/0x7F/0x22)"),
                ("NEGATIVE_SECURITY", "Negative: Security Access Denied (NRC 0x33)"),
                ("SUITE", "Full Test Suite (Positive + All Negatives)")
            ]
            selected_scenario = st.selectbox(
                "Test Scenario",
                options=[s[0] for s in scenario_options],
                format_func=lambda code: next(label for c, label in scenario_options if c == code)
            )

        with c3:
            default_did = "F190" if selected_sid == 0x22 else ("2001" if selected_sid in (0x2E, 0x2F) else "0201")
            did_input = st.text_input(
                "Identifier / DID Hex (Optional)",
                value=default_did,
                key=f"did_input_{selected_sid}",
                help="Applies to 0x22, 0x2E, 0x2F, 0x31"
            )

        # Advanced options (collapsed by default)
        with st.expander("⚙️ Advanced Preconditions & Subfunction Overrides", expanded=False):
            adv_c1, adv_c2, adv_c3 = st.columns(3)
            with adv_c1:
                session_choice = st.selectbox(
                    "Diagnostic Session Precondition",
                    options=["DEFAULT", "EXTENDED", "PROGRAMMING"],
                    index=0
                )
            with adv_c2:
                security_choice = st.selectbox(
                    "Security Level Precondition",
                    options=[(0, "0 — Locked (Level 0)"), (1, "1 — Unlocked (Level 1)"), (2, "2 — Unlocked (Level 2)")],
                    format_func=lambda x: x[1]
                )[0]
            with adv_c3:
                subfn_val = None
                if rule_info.has_subfunction:
                    allowed_sf_list = sorted(list(rule_info.allowed_subfunctions))
                    sf_options = [None] + allowed_sf_list
                    subfn_choice = st.selectbox(
                        "Subfunction Override",
                        options=sf_options,
                        format_func=lambda x: "Default (First Allowed)" if x is None else f"0x{x:02X}"
                    )
                    subfn_val = subfn_choice
                else:
                    st.caption("*(Service does not use subfunctions)*")

        col_btn, _ = st.columns([1, 4])
        if col_btn.button("🚀 Generate & Verify Test", type="primary"):
            with st.spinner("Executing deterministic ISO 14229 rule validation and generating test case..."):
                try:
                    sess_enum = DiagnosticSession(session_choice)
                    sec_enum = SecurityLevel(security_choice)
                    new_cases = []

                    if selected_scenario == "SUITE":
                        new_cases = test_generator.generate_suite_for_service(
                            service_id=selected_sid,
                            project_id=active_ws.project_id
                        )
                    elif selected_scenario == "POSITIVE":
                        tc = test_generator.generate_positive_test(
                            service_id=selected_sid,
                            project_id=active_ws.project_id,
                            subfunction=subfn_val,
                            did_hex=did_input,
                            session=sess_enum,
                            security=sec_enum
                        )
                        new_cases = [tc]
                    else:
                        defect = selected_scenario.replace("NEGATIVE_", "")
                        if defect == "SUBFUNCTION":
                            defect = "INVALID_SUBFUNCTION"
                        elif defect == "LENGTH":
                            defect = "INCORRECT_LENGTH"
                        elif defect == "SESSION":
                            defect = "SESSION_VIOLATION"
                        elif defect == "SECURITY":
                            defect = "SECURITY_LOCKED"
                        tc = test_generator.generate_negative_test(
                            service_id=selected_sid,
                            defect_type=defect,
                            project_id=active_ws.project_id,
                            session=sess_enum,
                            security=sec_enum
                        )
                        new_cases = [tc]

                    for c in new_cases:
                        test_case_store.save_test_case(c)
                        governance_manager.log_audit(
                            project_id=active_ws.project_id,
                            event_type="TEST_GENERATED",
                            performed_by="AI Rule-Verified Generator (UI)",
                            details={
                                "test_case_id": c.test_case_id,
                                "service_id": f"0x{c.service_id:02X}",
                                "test_type": c.test_type,
                                "verdict": c.rule_verification_status
                            }
                        )

                    activity_store.log_activity(
                        session_id=st.session_state.session_id,
                        user_id=st.session_state.user_id,
                        project_id=active_ws.project_id,
                        action=ActivityAction.TEST_GENERATED,
                        endpoint="UI",
                        http_method="UI",
                        status="SUCCESS",
                        metadata={
                            "service_id": f"0x{selected_sid:02X}",
                            "test_scenario": selected_scenario,
                            "count": len(new_cases)
                        }
                    )

                    st.success(f"Generated {len(new_cases)} test case(s) with rule engine verification completed!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Generation error: {str(e)}")

        st.markdown("---")

        # Workspace Test Cases & Review
        st.markdown("##### 📋 Workspace Test Repository & Sign-off Lifecycle")
        stored_cases = test_case_store.list_test_cases(active_ws.project_id)

        if not stored_cases:
            st.info("No test cases generated yet in this workspace. Configure parameters above to generate tests.")
        else:
            st.caption(f"Total Test Cases: **{len(stored_cases)}**")
            for tc in reversed(stored_cases):
                v_class = "badge-pass" if tc.rule_verification_status == "PASSED" else "badge-fail"
                v_label = "RULE PASS" if tc.rule_verification_status == "PASSED" else "RULE FAIL"

                status_badge_map = {
                    "DRAFT": ("badge-draft", "DRAFT"),
                    "RULE_VERIFIED": ("badge-info", "RULE_VERIFIED"),
                    "PENDING_REVIEW": ("badge-warn", "PENDING_REVIEW"),
                    "APPROVED": ("badge-pass", "APPROVED"),
                    "REJECTED": ("badge-fail", "REJECTED")
                }
                b_class, b_text = status_badge_map.get(tc.review_status, ("badge-info", tc.review_status))

                with st.expander(f"[{v_label}] [{b_text}] {tc.test_case_id}: {tc.title}"):
                    c_a, c_b, c_c = st.columns(3)
                    c_a.markdown(f"**Service:** `0x{tc.service_id:02X}` ({tc.service_name})")
                    c_b.markdown(f"**Test Type:** `{tc.test_type}`")
                    c_c.markdown(f"**Preconditions:** Session=`{tc.preconditions.get('session')}`, Security=`{tc.preconditions.get('security')}`")

                    st.markdown(f"**Description:** {tc.description}")
                    st.markdown(f"**Pass/Fail Criteria:** `{tc.pass_fail_criteria}`")

                    # Step table
                    st.markdown("###### Test Steps")
                    step_data = []
                    for s in tc.steps:
                        step_data.append({
                            "Step #": s.step_number,
                            "Description": s.description,
                            "Request Hex": s.request_hex,
                            "Expected Type": s.expected_response_type,
                            "Expected Response / NRC": s.expected_nrc if s.expected_nrc else s.expected_response_hex,
                            "Timeout (ms)": s.timeout_ms
                        })
                    st.table(step_data)

                    # Rule Verification Breakdown
                    st.markdown("###### 🛡️ Rule Engine Verification Report")
                    if tc.rule_verification_report:
                        rep = tc.rule_verification_report
                        if rep.overall_verdict == "PASS":
                            st.success(f"RULE ENGINE VERDICT: {rep.overall_verdict}")
                        else:
                            st.error(f"RULE ENGINE VERDICT: {rep.overall_verdict}")

                        check_rows = []
                        for chk in rep.checks:
                            check_rows.append({
                                "Rule Code": chk.rule_code,
                                "Rule Name": chk.rule_name,
                                "Result": "✅ PASS" if chk.passed else "❌ FAIL",
                                "Detail": chk.message,
                                "Expected": chk.expected or "-",
                                "Actual": chk.actual or "-"
                            })
                        st.dataframe(check_rows, use_container_width=True)

                    st.markdown("---")
                    st.markdown("###### ✍️ Human-in-the-Loop Engineering Sign-Off")

                    with st.form(f"review_form_{tc.test_case_id}"):
                        rf1, rf2 = st.columns(2)
                        reviewer_name = rf1.text_input("Reviewer Name", placeholder="e.g. A. Sharma (Validation Lead)")
                        reviewer_role = rf2.text_input("Engineering Role", value="Diagnostic Validation Specialist")

                        rf_act, rf_notes = st.columns([1, 2])
                        review_action = rf_act.radio("Sign-off Action", ["APPROVE", "EDIT_AND_APPROVE", "REJECT"])
                        review_notes = rf_notes.text_area("Review Justification Notes (Mandatory)", placeholder="Verified against ISO 14229-1 specification.")

                        if st.form_submit_button("Submit Formal Sign-off"):
                            try:
                                updated_tc, _ = governance_manager.submit_review(
                                    test_case=tc,
                                    reviewer_name=reviewer_name,
                                    reviewer_role=reviewer_role,
                                    action=review_action,
                                    comments=review_notes
                                )
                                test_case_store.save_test_case(updated_tc)

                                activity_store.log_activity(
                                    session_id=st.session_state.session_id,
                                    user_id=st.session_state.user_id or reviewer_name,
                                    project_id=active_ws.project_id,
                                    action=ActivityAction.TEST_REVIEWED,
                                    endpoint="UI",
                                    http_method="UI",
                                    test_case_id=tc.test_case_id,
                                    status="SUCCESS",
                                    metadata={
                                        "action": review_action,
                                        "reviewer_name": reviewer_name,
                                        "verdict": updated_tc.review_status
                                    }
                                )
                                st.success(f"Review recorded! Status: '{updated_tc.review_status}'.")
                                st.rerun()
                            except GovernanceError as ge:
                                st.error(f"Governance Enforcement Error: {str(ge)}")
                            except Exception as ge:
                                st.error(f"Review Error: {str(ge)}")

                    # Execution guardrail check
                    if st.button(f"Verify Execution Readiness ({tc.test_case_id})", key=f"guard_{tc.test_case_id}"):
                        try:
                            governance_manager.assert_can_export_or_execute(tc)
                            st.success(f"✅ PASSED GOVERNANCE CHECK: Test case '{tc.test_case_id}' is formally APPROVED and authorized for execution.")
                        except GovernanceError as ge:
                            st.error(f"⛔ EXECUTION BLOCKED: {str(ge)}")

    with tab_custom:
        st.markdown("##### Ad-Hoc Hex Frame Validation against ISO 14229")
        st.caption("Validate arbitrary diagnostic request frames in real-time using the deterministic rule engine.")

        with st.form("custom_frame_form"):
            cf1, cf2 = st.columns([2, 1])
            custom_hex = cf1.text_input("Raw Diagnostic Request Hex", value="22 F1 90")
            custom_exp_type = cf2.selectbox("Expected Type", ["POSITIVE", "NEGATIVE"])

            cf3, cf4, cf5 = st.columns(3)
            custom_session = cf3.selectbox("Session Context", ["DEFAULT", "EXTENDED", "PROGRAMMING"])
            custom_security = cf4.selectbox("Security Context", [0, 1, 2], format_func=lambda x: f"Level {x} ({'Locked' if x == 0 else 'Unlocked'})")
            custom_nrc = cf5.text_input("Expected NRC (e.g. 0x12, 0x13)", value="")

            run_val = st.form_submit_button("Run Deterministic Validation", type="primary")

        if run_val:
            try:
                sess_enum = DiagnosticSession(custom_session)
                sec_enum = SecurityLevel(custom_security)
                v_report = rule_engine.validate_request(
                    request_hex=custom_hex,
                    current_session=sess_enum,
                    current_security=sec_enum,
                    expected_response_type=custom_exp_type,
                    expected_nrc=custom_nrc.strip() if custom_nrc.strip() else None
                )

                activity_store.log_activity(
                    session_id=st.session_state.session_id,
                    user_id=st.session_state.user_id,
                    project_id=active_ws.project_id,
                    action=ActivityAction.RULE_VERIFIED,
                    endpoint="UI",
                    http_method="UI",
                    status="SUCCESS",
                    metadata={"service_hex": v_report.service_hex, "verdict": v_report.overall_verdict}
                )

                if v_report.overall_verdict == "PASS":
                    st.success(f"VERDICT: {v_report.overall_verdict} — Service: 0x{v_report.service_id:02X} ({v_report.service_name})")
                else:
                    st.error(f"VERDICT: {v_report.overall_verdict} — Service: 0x{v_report.service_id:02X} ({v_report.service_name})")

                c_rows = []
                for chk in v_report.checks:
                    c_rows.append({
                        "Rule Code": chk.rule_code,
                        "Rule Name": chk.rule_name,
                        "Status": "✅ PASS" if chk.passed else "❌ FAIL",
                        "Message": chk.message,
                        "Expected": chk.expected or "-",
                        "Actual": chk.actual or "-"
                    })
                st.dataframe(c_rows, use_container_width=True)

                if v_report.errors:
                    st.error(f"Violations: {'; '.join(v_report.errors)}")
            except Exception as e:
                st.error(f"Validation error: {str(e)}")
