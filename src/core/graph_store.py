"""
Relational Graph Traceability Store (SQLite + NetworkX) for Phase 5.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Implements approved Architectural Decision AD-02 (Option 2A):
- Embedded SQLite relational adjacency tables (traceability_nodes, traceability_edges).
- NetworkX directed graph (DiGraph) for fast in-memory bidirectional lineage traversal.
- Upstream lineage: Trace from Test Case / Execution back to Rule, Chunk, and Requirement Document.
- Downstream impact: Trace from Document / Rule forward to affected Test Cases, Reviews, Runs, and Exports.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Set, Tuple
import networkx as nx
from pydantic import BaseModel, Field

from src.core.config import config


class GraphNode(BaseModel):
    """Represents a node in the diagnostic traceability graph."""
    __test__ = False
    node_id: str
    node_type: str  # "DOCUMENT", "CHUNK", "RULE", "TEST_CASE", "REVIEW", "EXECUTION_RUN", "EXPORT_ARTIFACT"
    label: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    project_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GraphEdge(BaseModel):
    """Represents a directed relationship between two traceability nodes."""
    __test__ = False
    edge_id: str
    source_id: str
    target_id: str
    relation_type: str  # "EXTRACTED_FROM", "VERIFIED_BY", "APPROVED_BY", "EXECUTED_AS", "EXPORTED_TO"
    project_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LineageReport(BaseModel):
    """Bidirectional graph traversal result for a specific artifact."""
    __test__ = False
    root_node_id: str
    direction: str  # "UPSTREAM", "DOWNSTREAM", "BIDIRECTIONAL"
    total_nodes: int
    total_edges: int
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class SQLiteNetworkXGraphStore:
    """
    Serverless relational graph store persisting graph topology in SQLite
    and loading into NetworkX DiGraph for rapid in-memory path and lineage traversals.
    """
    __test__ = False

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (config.data_dir / "traceability" / "graph_store.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._graphs: Dict[str, nx.DiGraph] = {}

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes relational adjacency tables in SQLite."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS traceability_nodes (
                    node_id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    label TEXT NOT NULL,
                    metadata_json TEXT,
                    project_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS traceability_edges (
                    edge_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES traceability_nodes(node_id),
                    FOREIGN KEY(target_id) REFERENCES traceability_nodes(node_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_proj ON traceability_nodes(project_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_proj ON traceability_edges(project_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_src ON traceability_edges(source_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_tgt ON traceability_edges(target_id)")
            conn.commit()

    def _get_or_load_graph(self, project_id: str) -> nx.DiGraph:
        """Retrieves or populates in-memory NetworkX DiGraph for a specific project workspace."""
        if project_id in self._graphs:
            return self._graphs[project_id]

        g = nx.DiGraph()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT node_id, node_type, label, metadata_json, created_at FROM traceability_nodes WHERE project_id = ?",
                (project_id,)
            )
            for row in cursor.fetchall():
                meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
                g.add_node(
                    row["node_id"],
                    node_type=row["node_type"],
                    label=row["label"],
                    metadata=meta,
                    created_at=row["created_at"]
                )

            cursor.execute(
                "SELECT edge_id, source_id, target_id, relation_type, created_at FROM traceability_edges WHERE project_id = ?",
                (project_id,)
            )
            for row in cursor.fetchall():
                g.add_edge(
                    row["source_id"],
                    row["target_id"],
                    edge_id=row["edge_id"],
                    relation_type=row["relation_type"],
                    created_at=row["created_at"]
                )

        self._graphs[project_id] = g
        return g

    def add_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        project_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[str] = None
    ) -> GraphNode:
        """Inserts or updates a node in SQLite and in-memory NetworkX graph."""
        now_str = created_at or datetime.now(timezone.utc).isoformat()
        meta = metadata or {}
        meta_json = json.dumps(meta)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO traceability_nodes (node_id, node_type, label, metadata_json, project_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    node_type=excluded.node_type,
                    label=excluded.label,
                    metadata_json=excluded.metadata_json
            """, (node_id, node_type, label, meta_json, project_id, now_str))
            conn.commit()

        g = self._get_or_load_graph(project_id)
        g.add_node(node_id, node_type=node_type, label=label, metadata=meta, created_at=now_str)

        return GraphNode(
            node_id=node_id,
            node_type=node_type,
            label=label,
            metadata=meta,
            project_id=project_id,
            created_at=now_str
        )

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        project_id: str,
        created_at: Optional[str] = None
    ) -> GraphEdge:
        """Inserts a directed relationship in SQLite and in-memory NetworkX graph."""
        now_str = created_at or datetime.now(timezone.utc).isoformat()
        edge_id = f"edge_{source_id}_{target_id}_{relation_type}"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO traceability_edges (edge_id, source_id, target_id, relation_type, project_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (edge_id, source_id, target_id, relation_type, project_id, now_str))
            conn.commit()

        g = self._get_or_load_graph(project_id)
        g.add_edge(source_id, target_id, edge_id=edge_id, relation_type=relation_type, created_at=now_str)

        return GraphEdge(
            edge_id=edge_id,
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            project_id=project_id,
            created_at=now_str
        )

    def get_upstream_lineage(self, node_id: str, project_id: str) -> LineageReport:
        """
        Traverses backward from node_id to all ancestors (predecessors).
        Example: Test Case -> Rule -> Specification Chunk -> Source Document.
        """
        g = self._get_or_load_graph(project_id)
        if node_id not in g:
            return LineageReport(
                root_node_id=node_id,
                direction="UPSTREAM",
                total_nodes=0,
                total_edges=0,
                nodes=[],
                edges=[]
            )

        # Reverse graph to use standard BFS/DFS for predecessor reachability
        reversed_g = g.reverse(copy=False)
        ancestor_nodes = nx.descendants(reversed_g, node_id) | {node_id}
        subgraph = g.subgraph(ancestor_nodes)

        nodes = [
            GraphNode(
                node_id=n,
                node_type=subgraph.nodes[n].get("node_type", "UNKNOWN"),
                label=subgraph.nodes[n].get("label", n),
                metadata=subgraph.nodes[n].get("metadata", {}),
                project_id=project_id,
                created_at=subgraph.nodes[n].get("created_at", "")
            )
            for n in subgraph.nodes()
        ]

        edges = [
            GraphEdge(
                edge_id=subgraph.edges[u, v].get("edge_id", f"{u}_{v}"),
                source_id=u,
                target_id=v,
                relation_type=subgraph.edges[u, v].get("relation_type", "RELATED_TO"),
                project_id=project_id,
                created_at=subgraph.edges[u, v].get("created_at", "")
            )
            for u, v in subgraph.edges()
        ]

        return LineageReport(
            root_node_id=node_id,
            direction="UPSTREAM",
            total_nodes=len(nodes),
            total_edges=len(edges),
            nodes=nodes,
            edges=edges
        )

    def get_downstream_impact(self, node_id: str, project_id: str) -> LineageReport:
        """
        Traverses forward from node_id to all descendants (successors).
        Example: Document Chunk -> Rule -> Test Case -> Review -> Run -> Export.
        """
        g = self._get_or_load_graph(project_id)
        if node_id not in g:
            return LineageReport(
                root_node_id=node_id,
                direction="DOWNSTREAM",
                total_nodes=0,
                total_edges=0,
                nodes=[],
                edges=[]
            )

        descendant_nodes = nx.descendants(g, node_id) | {node_id}
        subgraph = g.subgraph(descendant_nodes)

        nodes = [
            GraphNode(
                node_id=n,
                node_type=subgraph.nodes[n].get("node_type", "UNKNOWN"),
                label=subgraph.nodes[n].get("label", n),
                metadata=subgraph.nodes[n].get("metadata", {}),
                project_id=project_id,
                created_at=subgraph.nodes[n].get("created_at", "")
            )
            for n in subgraph.nodes()
        ]

        edges = [
            GraphEdge(
                edge_id=subgraph.edges[u, v].get("edge_id", f"{u}_{v}"),
                source_id=u,
                target_id=v,
                relation_type=subgraph.edges[u, v].get("relation_type", "RELATED_TO"),
                project_id=project_id,
                created_at=subgraph.edges[u, v].get("created_at", "")
            )
            for u, v in subgraph.edges()
        ]

        return LineageReport(
            root_node_id=node_id,
            direction="DOWNSTREAM",
            total_nodes=len(nodes),
            total_edges=len(edges),
            nodes=nodes,
            edges=edges
        )

    def get_lineage(self, node_id: str, project_id: str, direction: str = "BIDIRECTIONAL") -> LineageReport:
        """
        Unified lineage query supporting UPSTREAM, DOWNSTREAM, or BIDIRECTIONAL traversal.
        """
        dir_upper = direction.upper()
        if dir_upper == "UPSTREAM":
            return self.get_upstream_lineage(node_id, project_id)
        elif dir_upper == "DOWNSTREAM":
            return self.get_downstream_impact(node_id, project_id)

        # BIDIRECTIONAL: combine upstream and downstream
        up = self.get_upstream_lineage(node_id, project_id)
        down = self.get_downstream_impact(node_id, project_id)

        seen_nodes: Dict[str, GraphNode] = {n.node_id: n for n in up.nodes}
        for n in down.nodes:
            seen_nodes[n.node_id] = n

        seen_edges: Dict[str, GraphEdge] = {e.edge_id: e for e in up.edges}
        for e in down.edges:
            seen_edges[e.edge_id] = e

        return LineageReport(
            root_node_id=node_id,
            direction="BIDIRECTIONAL",
            total_nodes=len(seen_nodes),
            total_edges=len(seen_edges),
            nodes=list(seen_nodes.values()),
            edges=list(seen_edges.values())
        )

    def get_full_workspace_graph(self, project_id: str) -> LineageReport:
        """Returns the complete directed graph for a workspace."""
        g = self._get_or_load_graph(project_id)
        nodes = [
            GraphNode(
                node_id=n,
                node_type=g.nodes[n].get("node_type", "UNKNOWN"),
                label=g.nodes[n].get("label", n),
                metadata=g.nodes[n].get("metadata", {}),
                project_id=project_id,
                created_at=g.nodes[n].get("created_at", "")
            )
            for n in g.nodes()
        ]

        edges = [
            GraphEdge(
                edge_id=g.edges[u, v].get("edge_id", f"{u}_{v}"),
                source_id=u,
                target_id=v,
                relation_type=g.edges[u, v].get("relation_type", "RELATED_TO"),
                project_id=project_id,
                created_at=g.edges[u, v].get("created_at", "")
            )
            for u, v in g.edges()
        ]

        return LineageReport(
            root_node_id=f"workspace_{project_id}",
            direction="BIDIRECTIONAL",
            total_nodes=len(nodes),
            total_edges=len(edges),
            nodes=nodes,
            edges=edges
        )

    def sync_workspace_artifacts(
        self,
        project_id: str,
        test_cases: List[Any],
        execution_runs: Optional[List[Any]] = None,
        audit_events: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Synchronizes existing workspace test cases, execution runs, and reviews
        into the relational graph store, creating rich cross-artifact linkages.
        """
        for tc in test_cases:
            tc_id = tc.test_case_id
            sid_hex = f"0x{tc.service_id:02X}"
            rule_node_id = f"rule_{sid_hex}"

            # 1. Rule Node
            self.add_node(
                node_id=rule_node_id,
                node_type="RULE",
                label=f"Rule: {tc.service_name} ({sid_hex})",
                project_id=project_id,
                metadata={"service_id": tc.service_id, "service_name": tc.service_name}
            )

            # 2. Test Case Node
            self.add_node(
                node_id=tc_id,
                node_type="TEST_CASE",
                label=f"[{sid_hex}] {tc.title}",
                project_id=project_id,
                metadata={
                    "test_type": tc.test_type,
                    "review_status": tc.review_status,
                    "rule_status": tc.rule_verification_status
                },
                created_at=tc.created_at
            )
            self.add_edge(rule_node_id, tc_id, "VERIFIES", project_id)

            # 3. Citation / Specification Nodes
            for cit in getattr(tc, "citation_references", []):
                cit_clean = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in cit)
                cit_node_id = f"spec_{cit_clean[:32]}"
                self.add_node(
                    node_id=cit_node_id,
                    node_type="SPECIFICATION",
                    label=f"Spec: {cit}",
                    project_id=project_id
                )
                self.add_edge(cit_node_id, rule_node_id, "GOVERNS", project_id)

            # 4. Review Node (if reviewed)
            if tc.review_status in ("APPROVED", "REJECTED"):
                rev_id = f"rev_{tc_id}"
                self.add_node(
                    node_id=rev_id,
                    node_type="REVIEW",
                    label=f"Review: {tc.review_status}",
                    project_id=project_id,
                    metadata={"status": tc.review_status}
                )
                self.add_edge(tc_id, rev_id, "REVIEWED_AS", project_id)

        # 5. Execution Runs
        if execution_runs:
            for run in execution_runs:
                run_node_id = run.execution_id
                self.add_node(
                    node_id=run_node_id,
                    node_type="EXECUTION_RUN",
                    label=f"Run: {run.overall_verdict} ({run.total_elapsed_ms:.1f}ms)",
                    project_id=project_id,
                    metadata={"verdict": run.overall_verdict, "elapsed_ms": run.total_elapsed_ms},
                    created_at=run.executed_at
                )
                if run.test_case_id in self._get_or_load_graph(project_id):
                    self.add_edge(run.test_case_id, run_node_id, "EXECUTED_IN", project_id)

        # 6. Audit Export Events
        if audit_events:
            for ev in audit_events:
                if ev.get("event_type") == "TEST_EXPORTED":
                    det = ev.get("details", {})
                    exp_id = f"export_{ev.get('audit_id', 'unknown')}"
                    self.add_node(
                        node_id=exp_id,
                        node_type="EXPORT_ARTIFACT",
                        label=f"Export: {det.get('file_name', 'script')}",
                        project_id=project_id,
                        metadata=det,
                        created_at=ev.get("created_at")
                    )
                    for t_id in det.get("test_case_ids", []):
                        if t_id in self._get_or_load_graph(project_id):
                            self.add_edge(t_id, exp_id, "EXPORTED_AS", project_id)


graph_store = SQLiteNetworkXGraphStore()
