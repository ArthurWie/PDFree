"""Tests for PDFreeApp.open_pdfs()."""

import sys
import pytest


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
    p = tmp_path / "a.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


@pytest.fixture
def pdf_file2(tmp_path):
    import fitz

    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    p = tmp_path / "b.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


def test_open_pdfs_opens_viewer(qapp, pdf_file):
    from main import PDFreeApp
    from view_tool import ViewTool

    w = PDFreeApp()
    w.open_pdfs([pdf_file])
    assert isinstance(w._current_tool, ViewTool)
    assert w._current_tool._tab_widget.count() == 1
    w._cleanup_tool()


def test_open_pdfs_multiple_creates_tabs(qapp, pdf_file, pdf_file2):
    from main import PDFreeApp

    w = PDFreeApp()
    w.open_pdfs([pdf_file, pdf_file2])
    assert w._current_tool._tab_widget.count() == 2
    w._cleanup_tool()


def test_open_pdfs_appends_to_existing_viewer(qapp, pdf_file, pdf_file2):
    from main import PDFreeApp

    w = PDFreeApp()
    w.show_tool("view", pdf_file)
    w.open_pdfs([pdf_file2])
    assert w._current_tool._tab_widget.count() == 2
    w._cleanup_tool()


def test_open_pdfs_deduplicates_same_file(qapp, pdf_file):
    from main import PDFreeApp

    w = PDFreeApp()
    w.open_pdfs([pdf_file, pdf_file])
    assert w._current_tool._tab_widget.count() == 1
    w._cleanup_tool()


def test_open_pdfs_empty_list_does_nothing(qapp):
    from main import PDFreeApp

    w = PDFreeApp()
    w.open_pdfs([])
    assert w._current_tool is None
    w._cleanup_tool()
