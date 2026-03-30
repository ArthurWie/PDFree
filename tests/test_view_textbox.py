"""Tests for text box drag handle and inline editor in ViewTool."""

import sys
import pytest


def _get_or_create_app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="module")
def qapp():
    return _get_or_create_app()


@pytest.fixture
def pdf_with_freetext(tmp_path):
    """PDF with a FREE_TEXT annotation at a known position."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    annot = page.add_freetext_annot(
        fitz.Rect(50, 50, 200, 80),
        "Hello",
        fontsize=12,
    )
    annot.update()
    p = tmp_path / "freetext.pdf"
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


def test_tb_handle_exists_on_canvas(qapp, pdf_with_freetext):
    vt = _open_and_render(qapp, pdf_with_freetext)
    assert hasattr(vt._canvas, "_tb_handle")
    vt.cleanup()


def test_tb_handle_visible_when_hovering_freetext(qapp, pdf_with_freetext):
    from PySide6.QtWidgets import QApplication
    vt = _open_and_render(qapp, pdf_with_freetext)
    # Hover over center of annotation (PDF coords 125, 65)
    cx, cy = vt._pdf_to_canvas(125.0, 65.0)
    vt._on_mouse_move(cx, cy)
    QApplication.processEvents()
    assert vt._canvas._tb_handle.isVisible()
    vt.cleanup()


def test_tb_handle_hidden_when_not_hovering(qapp, pdf_with_freetext):
    from PySide6.QtWidgets import QApplication
    vt = _open_and_render(qapp, pdf_with_freetext)
    # Move to an empty area (PDF coords 300, 300)
    cx, cy = vt._pdf_to_canvas(300.0, 300.0)
    vt._on_mouse_move(cx, cy)
    QApplication.processEvents()
    assert not vt._canvas._tb_handle.isVisible()
    vt.cleanup()
