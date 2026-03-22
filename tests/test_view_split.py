"""Tests for split view in ViewTool."""
import sys
import pytest
from pathlib import Path


def _get_or_create_app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="module")
def qapp():
    return _get_or_create_app()


@pytest.fixture
def pdf_file(tmp_path):
    import fitz
    doc = fitz.open()
    doc.new_page()
    p = tmp_path / "test.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


def test_split_mode_activates(qapp, pdf_file):
    """Activating split mode shows splitter and hides tab widget."""
    from view_tool import ViewTool
    from PySide6.QtWidgets import QSplitter
    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.toggle_split()
    assert vt._split_mode is True
    assert isinstance(vt._splitter, QSplitter)
    assert not vt._tab_widget.isVisible()
    vt.cleanup()


def test_split_mode_has_two_panes(qapp, pdf_file):
    """Split mode creates left pane (from tab) and right pane (new)."""
    from view_tool import ViewTool
    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.toggle_split()
    assert vt._split_left_pane is not None
    assert vt._split_right_pane is not None
    assert vt._split_left_pane is not vt._split_right_pane
    vt.cleanup()


def test_split_right_pane_at_page_zero(qapp, pdf_file):
    """Right pane opens at page 0 regardless of last_page."""
    from view_tool import ViewTool
    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.toggle_split()
    assert vt._split_right_pane.active_page == 0
    vt.cleanup()


def test_split_panes_are_independent(qapp, pdf_file):
    """Left and right panes have different _RenderPane instances."""
    from view_tool import ViewTool
    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.toggle_split()
    assert vt._split_left_pane is not vt._split_right_pane
    vt.cleanup()


def test_collapse_split_restores_tab_widget(qapp, pdf_file):
    """Collapsing split mode re-inserts left pane into tab bar and shows tab widget."""
    from view_tool import ViewTool
    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.toggle_split()
    assert not vt._tab_widget.isVisible()
    vt.close_split()
    assert vt._split_mode is False
    assert vt._tab_widget.isVisible()
    assert vt._tab_widget.count() == 1
    vt.cleanup()


def test_split_mode_modified_aggregate(qapp, pdf_file):
    """_modified is True if right split pane is modified."""
    from view_tool import ViewTool
    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.toggle_split()
    assert vt._modified is False
    vt._split_right_pane._is_modified = True
    assert vt._modified is True
    vt.cleanup()


def test_cleanup_closes_right_split_pane(qapp, pdf_file):
    """cleanup() calls cleanup() on right split pane."""
    from view_tool import ViewTool
    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.toggle_split()
    right = vt._split_right_pane
    vt.cleanup()
    assert right._doc is None
    assert vt._split_right_pane is None
