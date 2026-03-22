"""Tests for QTabWidget multi-document support in ViewTool."""
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
    """Create a minimal valid PDF for testing."""
    import fitz
    doc = fitz.open()
    doc.new_page()
    p = tmp_path / "test.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


@pytest.fixture
def pdf_file2(tmp_path):
    """Create a second minimal PDF."""
    import fitz
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    p = tmp_path / "test2.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


def test_tab_widget_exists(qapp):
    from view_tool import ViewTool
    vt = ViewTool()
    from PySide6.QtWidgets import QTabWidget
    assert hasattr(vt, "_tab_widget")
    assert isinstance(vt._tab_widget, QTabWidget)
    vt.cleanup()


def test_open_file_creates_tab(qapp, pdf_file):
    from view_tool import ViewTool
    vt = ViewTool()
    vt.open_file(pdf_file)
    assert vt._tab_widget.count() == 1
    vt.cleanup()


def test_open_two_files_creates_two_tabs(qapp, pdf_file, pdf_file2):
    from view_tool import ViewTool
    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.open_file(pdf_file2)
    assert vt._tab_widget.count() == 2
    vt.cleanup()


def test_open_duplicate_focuses_existing_tab(qapp, pdf_file):
    from view_tool import ViewTool
    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.open_file(pdf_file)  # same file again
    assert vt._tab_widget.count() == 1  # still 1, not 2
    vt.cleanup()


def test_active_pane_matches_current_tab(qapp, pdf_file, pdf_file2):
    from view_tool import ViewTool
    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.open_file(pdf_file2)
    # Switch to first tab
    vt._tab_widget.setCurrentIndex(0)
    pane0 = vt.active_pane
    # Switch to second tab
    vt._tab_widget.setCurrentIndex(1)
    pane1 = vt.active_pane
    assert pane0 is not pane1
    vt.cleanup()


def test_modified_aggregate(qapp, pdf_file, pdf_file2):
    from view_tool import ViewTool
    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.open_file(pdf_file2)
    assert vt._modified is False
    # Mark only the second pane as modified
    vt._tab_widget.widget(1)._is_modified = True
    assert vt._modified is True
    vt._tab_widget.widget(1)._is_modified = False
    assert vt._modified is False
    vt.cleanup()


def test_close_tab_removes_pane(qapp, pdf_file, pdf_file2):
    from view_tool import ViewTool
    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.open_file(pdf_file2)
    assert vt._tab_widget.count() == 2
    vt._close_tab(0)
    assert vt._tab_widget.count() == 1
    vt.cleanup()


def test_cleanup_closes_all_panes(qapp, pdf_file, pdf_file2):
    from view_tool import ViewTool
    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.open_file(pdf_file2)
    pane0 = vt._tab_widget.widget(0)
    pane1 = vt._tab_widget.widget(1)
    vt.cleanup()
    # Docs should be closed
    assert pane0._doc is None
    assert pane1._doc is None
