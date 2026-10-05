"""
Traceability Page for UDS Diagnostic Intelligence Platform.
Provides bidirectional relational graph lineage across specifications, rules,
test cases, reviews, execution runs, and export artifacts using a split layout.
"""

import streamlit as st
from src.core.execution_store import execution_store
from src.core.governance import governance_manager
from src.core.graph_store import graph_store
from src.core.test_case_store import test_case_store


def render_traceability_page(active_ws):
    """Renders the Relational Graph Traceability workspace."""
    st.markdown("### 🔗 Relational Graph Traceability & Lineage")
    st.caption(
        f"Workspace: **`{active_ws.name}`** (`{active_ws.project_id}`). "
        "Bidirectional artifact lineage mapping specifications, rules, tests, reviews, executions, and exports. "
        "Powered by serverless SQLite + NetworkX directed relational graph."
    )

    # Sync workspace artifacts
    test_cases = test_case_store.list_test_cases(active_ws.project_id)
    runs = execution_store.list_execution_results(active_ws.project_id)
    audit_trail = governance_manager.get_audit_trail(active_ws.project_id)
    graph_store.sync_workspace_artifacts(active_ws.project_id, test_cases, runs, audit_trail)

    full_graph = graph_store.get_full_workspace_graph(active_ws.project_id)

    # Top stats
    g_c1, g_c2, g_c3 = st.columns(3)
    g_c1.metric("Indexed Graph Nodes", full_graph.total_nodes)
    g_c2.metric("Directed Relationships", full_graph.total_edges)
    g_c3.caption(f"**Storage Engine:** SQLite (`graph_store.db`) + NetworkX DiGraph\n**Isolation:** Workspace `{active_ws.project_id}`")

    st.markdown("---")

    # Lifecycle flow diagram
    st.markdown(
        """
        <div class="pipeline-container" style="justify-content: center;">
            <div class="pipeline-step"><span>📄</span> SPECIFICATION</div>
            <div class="pipeline-arrow">➔</div>
            <div class="pipeline-step"><span>🛡️</span> RULE</div>
            <div class="pipeline-arrow">➔</div>
            <div class="pipeline-step"><span>🧪</span> TEST CASE</div>
            <div class="pipeline-arrow">➔</div>
            <div class="pipeline-step"><span>🔍</span> VERIFICATION</div>
            <div class="pipeline-arrow">➔</div>
            <div class="pipeline-step"><span>✍️</span> REVIEW</div>
            <div class="pipeline-arrow">➔</div>
            <div class="pipeline-step"><span>⚡</span> EXECUTION</div>
            <div class="pipeline-arrow">➔</div>
            <div class="pipeline-step"><span>📦</span> EXPORT</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")

    all_node_choices = {n.node_id: f"[{n.node_type}] {n.label} ({n.node_id})" for n in full_graph.nodes}

    if not all_node_choices:
        st.info("No artifacts currently indexed in this workspace graph. Ingest documents or generate test cases to populate the graph.")
        return

    # Split Layout: LEFT = Graph traversal & table, RIGHT = Selected artifact details
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("##### 🧭 Graph Traversal Controls")
        selected_node_id = st.selectbox(
            "Focus Artifact Node",
            options=list(all_node_choices.keys()),
            format_func=lambda nid: all_node_choices.get(nid, nid)
        )
        direction_choice = st.selectbox(
            "Lineage Traversal Direction",
            options=["BIDIRECTIONAL", "UPSTREAM", "DOWNSTREAM"],
            format_func=lambda d: {
                "BIDIRECTIONAL": "↔️ Bidirectional (Full Context)",
                "UPSTREAM": "⬆️ Upstream (Originating Rules & Specs)",
                "DOWNSTREAM": "⬇️ Downstream (Affected Tests & Runs)"
            }.get(d, d)
        )

        lineage_result = graph_store.get_lineage(selected_node_id, active_ws.project_id, direction=direction_choice)

        st.caption(f"Connected: **{lineage_result.total_nodes}** node(s), **{lineage_result.total_edges}** edge(s)")

        if lineage_result.nodes:
            st.markdown("###### Connected Nodes")
            node_rows = [
                {
                    "Node ID": n.node_id,
                    "Type": n.node_type,
                    "Label": n.label,
                    "Created At": n.created_at[:19].replace("T", " ") if n.created_at else ""
                }
                for n in lineage_result.nodes
            ]
            st.dataframe(node_rows, use_container_width=True)

        if lineage_result.edges:
            st.markdown("###### Relationship Edges")
            edge_rows = [
                {
                    "Source Node": e.source_id,
                    "Relation": f"—[{e.relation_type}]—>",
                    "Target Node": e.target_id
                }
                for e in lineage_result.edges
            ]
            st.dataframe(edge_rows, use_container_width=True)

    with col_right:
        st.markdown("##### 🔎 Selected Artifact Details")
        target_node = next((n for n in full_graph.nodes if n.node_id == selected_node_id), None)
        if target_node:
            st.markdown(
                f"""
                <div class="eng-card">
                    <div class="eng-card-header">
                        <span>Node Properties</span>
                        <span class="badge-info">{target_node.node_type}</span>
                    </div>
                    <div style="font-size:0.85rem; line-height:1.6;">
                        <div><b>Node ID:</b> <code>{target_node.node_id}</code></div>
                        <div><b>Label:</b> {target_node.label}</div>
                        <div><b>Created At:</b> {target_node.created_at[:19].replace('T', ' ') if target_node.created_at else '-'}</div>
                        <div><b>Workspace:</b> <code>{target_node.project_id}</code></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            with st.expander("📄 Raw Node Attributes & Metadata"):
                st.json(target_node.attributes)

            with st.expander("🔍 Complete Lineage JSON Payload"):
                st.json(lineage_result.model_dump())
