"""
Export & Optimization Page for UDS Diagnostic Intelligence Platform.
Provides diagnostic coverage analysis, deterministic test suite deduplication,
and production script generation (Python udsoncan and Vector CANoe CAPL).
"""

import streamlit as st
from src.core.activity_store import ActivityAction, activity_store
from src.core.exporter import script_exporter
from src.core.governance import GovernanceError
from src.core.optimizer import test_optimizer
from src.core.test_case_store import test_case_store


def render_export_opt_page(active_ws):
    """Renders the Coverage, Optimization, and Script Export workspace."""
    st.markdown("### 📦 Export & Optimization Studio")
    st.caption(
        f"Workspace: **`{active_ws.name}`** (`{active_ws.project_id}`). "
        "Deterministic coverage matrix analysis, test deduplication engine, and production script exporter. "
        "Enforces the mandatory governance guard: unapproved test cases cannot be exported."
    )

    all_tests = test_case_store.list_test_cases(active_ws.project_id)
    approved_tests = [t for t in all_tests if t.review_status == "APPROVED"]

    opt_tab1, opt_tab2, opt_tab3 = st.tabs([
        "📊 Coverage Matrix",
        "⚡ Suite Optimization",
        "🚀 Script Exporter (Approved Only)"
    ])

    # 1. Coverage Matrix
    with opt_tab1:
        st.markdown("##### ISO 14229 Service & Diagnostic Dimension Coverage")
        cov_matrix = test_optimizer.calculate_coverage(all_tests, project_id=active_ws.project_id)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Services With Tests", f"{cov_matrix.services_with_tests} / {cov_matrix.total_services_in_scope}", f"{cov_matrix.service_coverage_pct}%")
        c2.metric("Full Coverage (Pos + Neg)", cov_matrix.services_full_coverage)
        c3.metric("Partial Coverage", cov_matrix.services_partial_coverage)
        c4.metric("Total Tests in Suite", cov_matrix.total_tests, f"{cov_matrix.positive_tests_count} Pos / {cov_matrix.negative_tests_count} Neg")

        st.markdown("###### Service-by-Service Coverage Breakdown")
        table_rows = []
        for s in cov_matrix.service_breakdown:
            status_icon = "✅ Full" if s.status == "FULL" else ("⚠️ Partial" if s.status == "PARTIAL" else "❌ Uncovered")
            table_rows.append({
                "Service Hex": s.service_hex,
                "Service Name": s.service_name,
                "Pos Tests": s.positive_count,
                "Neg Tests": s.negative_count,
                "Total Tests": s.total_tests,
                "Sessions Tested": ", ".join(s.tested_sessions) if s.tested_sessions else "None",
                "Security Tested": ", ".join([f"L{sec}" for sec in s.tested_security_levels]) if s.tested_security_levels else "None",
                "Coverage Status": status_icon,
                "Missing Aspects": "; ".join(s.missing_aspects) if s.missing_aspects else "Complete"
            })
        st.dataframe(table_rows, use_container_width=True)

        if cov_matrix.uncovered_combinations:
            with st.expander(f"⚠️ Uncovered Combinations & Gaps ({len(cov_matrix.uncovered_combinations)} identified)"):
                for gap in cov_matrix.uncovered_combinations:
                    st.warning(f"**[{gap['service_hex']} - {gap['service_name']}]** {gap['description']}")

    # 2. Suite Optimization & Deduplication
    with opt_tab2:
        st.markdown("##### Deterministic Deduplication & Redundancy Analysis")
        st.caption(
            "Analyzes test cases across service, scenario, preconditions, and request sequences. "
            "Eliminates functional redundancy while preserving coverage variants."
        )

        col_opt_btn, _ = st.columns([1, 3])
        run_opt = col_opt_btn.button("⚡ Run Deduplication Analysis", type="primary")

        if run_opt or "optimization_result" in st.session_state:
            if run_opt:
                st.session_state.optimization_result = test_optimizer.optimize_test_suite(all_tests)
                activity_store.log_activity(
                    session_id=st.session_state.session_id,
                    user_id=st.session_state.user_id,
                    project_id=active_ws.project_id,
                    action=ActivityAction.TEST_OPTIMIZED,
                    endpoint="UI",
                    http_method="UI",
                    status="SUCCESS",
                    metadata={
                        "original_count": st.session_state.optimization_result.original_count,
                        "retained_count": st.session_state.optimization_result.retained_count,
                        "duplicates_removed": st.session_state.optimization_result.removed_duplicates_count
                    }
                )
            opt_rep = st.session_state.optimization_result

            st.markdown("###### Optimization Results")
            o1, o2, o3, o4 = st.columns(4)
            o1.metric("Original Tests", opt_rep.original_count)
            o2.metric("Retained Unique Tests", opt_rep.retained_count)
            o3.metric("Removed Duplicates", opt_rep.removed_duplicates_count)
            o4.metric("Deduplication Ratio", f"{opt_rep.deduplication_ratio_pct}%")

            st.info(f"**Coverage Impact Analysis:** {opt_rep.coverage_impact}")

            if opt_rep.removed_test_details:
                st.markdown("###### Removed Redundant Tests")
                rem_rows = []
                for rem in opt_rep.removed_test_details:
                    rem_rows.append({
                        "Test ID": rem.test_case_id,
                        "Duplicate Of": rem.duplicate_of_id,
                        "Service": rem.service_hex,
                        "Type": rem.test_type,
                        "Reason": rem.reason
                    })
                st.dataframe(rem_rows, use_container_width=True)
            else:
                st.success("All test cases in the workspace are functional unique variants. Zero redundancy detected.")

    # 3. Script Exporter (Approved Only)
    with opt_tab3:
        st.markdown("##### Production Automation Script Exporter")
        st.caption(
            "Translate formally approved test cases into production-grade executable test scripts. "
            "Unapproved tests cannot be exported under any circumstance."
        )

        e1, e2 = st.columns([2, 1])
        target_format = e1.selectbox(
            "Target Automation Platform",
            options=["python_can_udsoncan", "canoe_capl"],
            format_func=lambda x: "Python (python-can / udsoncan)" if x == "python_can_udsoncan" else "Vector CANoe CAPL (.can)"
        )
        operator_name = e2.text_input("Exporting Engineer", value="Validation Lead")

        st.markdown("###### Select Approved Test Cases")
        if not approved_tests:
            st.warning("⚠️ No APPROVED test cases found in this workspace. Review and approve test cases in Test Studio before exporting.")
        else:
            select_all = st.checkbox("Select All Approved Tests", value=True)
            tc_choices = {t.test_case_id: f"[{t.test_case_id}] 0x{t.service_id:02X} {t.service_name} ({t.test_type}) - {t.title}" for t in approved_tests}

            selected_ids = st.multiselect(
                "Approved Test Cases",
                options=list(tc_choices.keys()),
                default=list(tc_choices.keys()) if select_all else [],
                format_func=lambda x: tc_choices.get(x, x)
            )

            custom_file_name = st.text_input("Custom Artifact Name (Optional)", placeholder="e.g. BCM_Diagnostic_Suite_Approved")

            exp_btn = st.button("🚀 Export Script", type="primary", disabled=(len(selected_ids) == 0))

            if exp_btn and selected_ids:
                with st.spinner("Generating production script with cryptographic provenance hash..."):
                    selected_cases = [t for t in approved_tests if t.test_case_id in selected_ids]
                    try:
                        artifact = script_exporter.export_test_suite(
                            test_cases=selected_cases,
                            export_format=target_format,
                            operator_name=operator_name,
                            file_name=custom_file_name if custom_file_name.strip() else None,
                            suite_title=f"UDS Suite - {active_ws.name}"
                        )

                        activity_store.log_activity(
                            session_id=st.session_state.session_id,
                            user_id=st.session_state.user_id or operator_name,
                            project_id=active_ws.project_id,
                            action=ActivityAction.TEST_EXPORTED,
                            endpoint="UI",
                            http_method="UI",
                            status="SUCCESS",
                            metadata={
                                "format": target_format,
                                "count": len(selected_cases),
                                "file_name": artifact.artifact_name
                            }
                        )

                        st.success(f"✅ Generated `{artifact.artifact_name}` ({len(artifact.test_case_ids)} tests, {artifact.total_steps} steps)")

                        m1, m2 = st.columns(2)
                        m1.caption(f"**SHA-256 Checksum:** `{artifact.sha256_hash}`")
                        m2.caption(f"**Audit ID:** `{artifact.audit_id}`")

                        lang = "python" if artifact.file_extension == ".py" else "c"
                        st.code(artifact.code_content, language=lang)

                        st.download_button(
                            label=f"📥 Download {artifact.artifact_name}",
                            data=artifact.code_content,
                            file_name=artifact.artifact_name,
                            mime="text/plain"
                        )
                    except GovernanceError as ge:
                        st.error(f"Governance Enforcement Error: {ge}")
                    except Exception as ex:
                        st.error(f"Export Error: {ex}")
