"""
Tests for Redesigned Automotive Engineering UI/UX Modules.
Verifies page modules, theme styling, and component integrity.
"""

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


def test_ui_page_modules_importable():
    """Verify all 9 redesigned page modules and renderers are importable and callable."""
    renderers = [
        render_overview_page,
        render_knowledge_page,
        render_documents_page,
        render_test_studio_page,
        render_execution_page,
        render_export_opt_page,
        render_traceability_page,
        render_metrics_page,
        render_admin_activity_page,
    ]
    for r in renderers:
        assert callable(r), f"Expected {r.__name__} to be callable"


def test_theme_injection():
    """Verify theme injection runs without errors."""
    inject_custom_theme()


def test_global_header_rendering():
    """Verify global header renders for active workspace."""
    ws = workspace_manager.get_workspace("tata_uds_pilot")
    render_global_header(ws)
    render_global_header(None)


def test_traceability_page_rendering_and_graph_node_metadata():
    """
    Regression test for Traceability page GraphNode rendering defect.
    Verifies render_traceability_page executes without AttributeError on GraphNode,
    and validates both populated and empty metadata conditions.
    """
    from src.core.graph_store import GraphNode

    # 1. Verify GraphNode model attributes and empty/populated metadata access
    node_with_meta = GraphNode(
        node_id="test_node_01",
        node_type="RULE",
        label="Rule 0x27",
        project_id="tata_uds_pilot",
        metadata={"spec": "ISO 14229-1", "level": 1}
    )
    assert hasattr(node_with_meta, "metadata")
    assert node_with_meta.metadata.get("spec") == "ISO 14229-1"

    node_empty_meta = GraphNode(
        node_id="test_node_02",
        node_type="TEST_CASE",
        label="TC 0x10",
        project_id="tata_uds_pilot",
        metadata={}
    )
    assert hasattr(node_empty_meta, "metadata")
    assert not node_empty_meta.metadata

    # 2. Verify render_traceability_page executes cleanly on active workspace
    ws = workspace_manager.get_workspace("tata_uds_pilot")
    render_traceability_page(ws)

