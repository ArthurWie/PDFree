"""Tests for the eraser tool in ViewTool."""

import sys
import pytest


def _get_or_create_app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="module")
def qapp():
    return _get_or_create_app()


@pytest.fixture
def pdf_with_rect_annot(tmp_path):
    """PDF with a single rect annotation at a known position."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    annot = page.add_rect_annot(fitz.Rect(50, 50, 100, 100))
    annot.update()
    p = tmp_path / "annot.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


def _open_and_render(qapp, pdf_path):
    from view_tool import ViewTool
    from PySide6.QtWidgets import QApplication
    vt = ViewTool()
    vt.show()
    vt.open_file(pdf_path)
    QApplication.processEvents()
    QApplication.processEvents()
    return vt


def test_eraser_click_deletes_annotation(qapp, pdf_with_rect_annot):
    from view_tool import Tool
    vt = _open_and_render(qapp, pdf_with_rect_annot)
    page = vt.doc[0]
    assert len(list(page.annots())) == 1

    # Get canvas coords of annotation center (PDF coords 75, 75)
    cx, cy = vt._pdf_to_canvas(75.0, 75.0)
    vt._set_tool(Tool.ERASER)
    vt._on_mouse_down(cx, cy)

    page = vt.doc[0]
    assert len(list(page.annots())) == 0
    assert vt._modified
    vt.cleanup()


def test_eraser_click_empty_area_does_nothing(qapp, pdf_with_rect_annot):
    from view_tool import Tool
    vt = _open_and_render(qapp, pdf_with_rect_annot)
    page = vt.doc[0]
    assert len(list(page.annots())) == 1

    # Canvas coords far from annotation (PDF coords 5, 5)
    cx, cy = vt._pdf_to_canvas(5.0, 5.0)
    vt._set_tool(Tool.ERASER)
    vt._on_mouse_down(cx, cy)

    page = vt.doc[0]
    assert len(list(page.annots())) == 1
    vt.cleanup()
