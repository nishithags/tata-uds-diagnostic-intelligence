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
