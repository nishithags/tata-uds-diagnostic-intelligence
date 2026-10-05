"""
Unit and integration tests for Relational Graph Traceability Store (SQLite + NetworkX).
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
Implements Architectural Decision AD-02 (Option 2A).
"""

import tempfile
from pathlib import Path
import pytest

from src.core.generator import TestCase, TestStep
from src.core.graph_store import GraphEdge, GraphNode, SQLiteNetworkXGraphStore
from src.core.rules import DiagnosticSession, SecurityLevel


@pytest.fixture
def temp_graph_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_graph.db"
        store = SQLiteNetworkXGraphStore(db_path=db_file)
        yield store


def test_node_and_edge_persistence(temp_graph_store):
    store = temp_graph_store
    proj = "proj_test_01"

    n1 = store.add_node(
        node_id="spec_uds_14229",
        node_type="SPECIFICATION",
        label="ISO 14229-1 Specification",
        project_id=proj,
        metadata={"section": "Session Control"}
    )
    assert n1.node_id == "spec_uds_14229"
    assert n1.node_type == "SPECIFICATION"

    n2 = store.add_node(
        node_id="rule_0x10",
        node_type="RULE",
        label="Rule 0x10 Session Control",
        project_id=proj
    )
    assert n2.node_id == "rule_0x10"

    edge = store.add_edge(
        source_id="spec_uds_14229",
        target_id="rule_0x10",
        relation_type="GOVERNS",
        project_id=proj
    )
    assert edge.source_id == "spec_uds_14229"
    assert edge.target_id == "rule_0x10"
    assert edge.relation_type == "GOVERNS"

    # Verify SQLite persistence directly
    with store._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM traceability_nodes WHERE project_id = ?", (proj,))
        assert cursor.fetchone()[0] == 2
        cursor.execute("SELECT COUNT(*) FROM traceability_edges WHERE project_id = ?", (proj,))
        assert cursor.fetchone()[0] == 1


def test_upstream_and_downstream_traversal(temp_graph_store):
    store = temp_graph_store
    proj = "proj_traversal"

    # Build chain: Spec -> Rule -> Test Case -> Review -> Run
    store.add_node("spec_01", "SPECIFICATION", "Spec Root", proj)
    store.add_node("rule_01", "RULE", "Rule 0x22", proj)
    store.add_node("tc_01", "TEST_CASE", "Test Case 01", proj)
    store.add_node("rev_01", "REVIEW", "Review Approved", proj)
    store.add_node("run_01", "EXECUTION_RUN", "Run Pass", proj)

    store.add_edge("spec_01", "rule_01", "GOVERNS", proj)
    store.add_edge("rule_01", "tc_01", "VERIFIES", proj)
    store.add_edge("tc_01", "rev_01", "REVIEWED_AS", proj)
    store.add_edge("tc_01", "run_01", "EXECUTED_IN", proj)

    # 1. Upstream from Run: should reach TC, Rule, Spec
    up_report = store.get_upstream_lineage("run_01", proj)
    assert up_report.root_node_id == "run_01"
    assert up_report.direction == "UPSTREAM"
    up_ids = {n.node_id for n in up_report.nodes}
    assert "run_01" in up_ids
    assert "tc_01" in up_ids
    assert "rule_01" in up_ids
    assert "spec_01" in up_ids
    assert "rev_01" not in up_ids  # Review is a sibling branch, not ancestor

    # 2. Downstream from Spec: should reach Rule, TC, Review, Run
    down_report = store.get_downstream_impact("spec_01", proj)
    assert down_report.root_node_id == "spec_01"
    assert down_report.direction == "DOWNSTREAM"
    down_ids = {n.node_id for n in down_report.nodes}
    assert down_ids == {"spec_01", "rule_01", "tc_01", "rev_01", "run_01"}

    # 3. Unified get_lineage BIDIRECTIONAL from tc_01
    bi_report = store.get_lineage("tc_01", proj, direction="BIDIRECTIONAL")
    assert bi_report.root_node_id == "tc_01"
    assert bi_report.direction == "BIDIRECTIONAL"
    bi_ids = {n.node_id for n in bi_report.nodes}
    assert bi_ids == {"spec_01", "rule_01", "tc_01", "rev_01", "run_01"}


def test_cross_workspace_isolation(temp_graph_store):
    store = temp_graph_store
    store.add_node("node_A", "TEST_CASE", "Test A", "workspace_A")
    store.add_node("node_B", "TEST_CASE", "Test B", "workspace_B")

    rep_a = store.get_full_workspace_graph("workspace_A")
    rep_b = store.get_full_workspace_graph("workspace_B")

    node_ids_a = {n.node_id for n in rep_a.nodes}
    node_ids_b = {n.node_id for n in rep_b.nodes}

    assert "node_A" in node_ids_a
    assert "node_B" not in node_ids_a
    assert "node_B" in node_ids_b
    assert "node_A" not in node_ids_b


def test_sync_workspace_artifacts(temp_graph_store):
    store = temp_graph_store
    proj = "sync_proj"

    # Create dummy test cases
    tc1 = TestCase(
        test_case_id="TC_SYNC_01",
        project_id=proj,
        service_id=0x10,
        service_name="DiagnosticSessionControl",
        test_type="POSITIVE",
        title="Session Control Test",
        description="Verify default session",
        pass_fail_criteria="Positive response 0x50",
        preconditions={"session": "DEFAULT", "security": 0},
        steps=[TestStep(step_number=1, description="Req", request_hex="10 01", expected_response_type="POSITIVE", expected_response_hex="50 01")],
        citation_references=["ISO_14229_Section_9"],
        review_status="APPROVED",
        rule_verification_status="PASSED"
    )

    store.sync_workspace_artifacts(proj, [tc1])
    full_g = store.get_full_workspace_graph(proj)
    node_ids = {n.node_id for n in full_g.nodes}

    assert "TC_SYNC_01" in node_ids
    assert "rule_0x10" in node_ids
    assert "rev_TC_SYNC_01" in node_ids
    assert any("spec_ISO_14229" in nid for nid in node_ids)
