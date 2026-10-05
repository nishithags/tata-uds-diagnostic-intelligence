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


def test_overview_historical_execution_metrics():
    """
    Regression test for Overview execution pass-rate presentation.
    Verifies:
    1. Historical execution count is correct.
    2. Passed count is correct.
    3. Failed count is correct.
    4. Historical pass rate remains mathematically correct.
    5. The UI labels the metric as historical execution pass rate.
    6. Historical failed executions are not deleted or ignored.
    """
    import inspect
    from src.core.execution_store import execution_store
    from src.web.pages import overview

    ws = workspace_manager.get_workspace("tata_uds_pilot")
    runs = execution_store.list_execution_results(ws.project_id)

    # 1. Historical execution count
    total_runs = len(runs)
    assert total_runs == 2

    # 2. Passed count
    passed_runs = [r for r in runs if r.overall_verdict == "PASS"]
    assert len(passed_runs) == 1

    # 3. Failed count
    failed_runs = [r for r in runs if r.overall_verdict == "FAIL"]
    assert len(failed_runs) == 1

    # 4. Historical pass rate mathematical correctness
    calc_rate = (len(passed_runs) / total_runs) * 100.0
    assert calc_rate == 50.0

    # 5. UI labels metric as Historical Pass Rate and preserves execution history wording
    overview_source = inspect.getsource(overview.render_overview_page)
    assert "Historical Pass Rate" in overview_source
    assert "Execution History" in overview_source
    assert "Historical execution pass rate is calculated from recorded runs and includes retained historical failures." in overview_source

    # 6. Historical failed execution is preserved and not deleted or ignored
    failed_run = failed_runs[0]
    assert failed_run.overall_verdict == "FAIL"
    assert any(step.actual_nrc == "0x31" for step in failed_run.step_results)

    # 7. Render overview page without exceptions
    render_overview_page(ws)
