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


def test_drag_handle_moves_freetext_annotation(qapp, pdf_with_freetext):
    """Verify that releasing the drag handle at a new position updates the PDF annotation.

    mapTo() is unreliable in headless Qt tests (no real window), so we skip the
    full event-driven drag and instead directly prime the handle's internal state
    (as press/move would have set it), then call mouseReleaseEvent with a minimal
    synthetic event. This tests the rect-update logic in mouseReleaseEvent, which
    is the non-trivial part of the drag implementation.
    """
    import fitz
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    vt = _open_and_render(qapp, pdf_with_freetext)

    # Capture orig rect as a tuple right after open. We must not hold the
    # Annot object — PyMuPDF invalidates it once the page/annots iterator
    # goes out of scope, causing a segfault on .rect access.
    page = vt.doc[0]
    annot = next(page.annots())
    orig_rect = fitz.Rect(annot.rect)
    del annot

    # Hover to show handle and populate _tb_hover_annot
    cx, cy = vt._pdf_to_canvas(125.0, 65.0)
    vt._on_mouse_move(cx, cy)
    QApplication.processEvents()

    handle = vt._canvas._tb_handle
    assert handle.isVisible()

    # Prime the handle state as mousePressEvent would have done, bypassing
    # mapTo() which returns (0,0) in a headless environment.
    handle._drag_active = True
    handle._annot_orig_rect = fitz.Rect(orig_rect)

    # Move the handle widget 30 canvas pixels to the right, as mouseMoveEvent
    # would have done via self.move().
    orig_hx = handle.x()
    orig_hy = handle.y()
    handle.move(orig_hx + 30, orig_hy)

    # Synthesise a release event (button value is what matters for the guard).
    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPoint(5, 5).toPointF(),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    handle.mouseReleaseEvent(release_event)
    QApplication.processEvents()
    QApplication.processEvents()

    new_page = vt.doc[0]
    new_annot = next(new_page.annots())
    new_rect = fitz.Rect(new_annot.rect)
    del new_annot
    assert new_rect.x0 != orig_rect.x0, "Annotation x0 should have moved"
    vt.cleanup()


@pytest.fixture
def empty_pdf(tmp_path):
    import fitz

    doc = fitz.open()
    doc.new_page(width=400, height=400)
    p = tmp_path / "empty.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


def test_tb_editor_exists_on_canvas(qapp, empty_pdf):
    vt = _open_and_render(qapp, empty_pdf)
    assert hasattr(vt._canvas, "_tb_editor")
    vt.cleanup()


def test_clicking_with_textbox_tool_opens_inline_editor(qapp, empty_pdf):
    from view_tool import Tool
    from PySide6.QtWidgets import QApplication

    vt = _open_and_render(qapp, empty_pdf)
    vt._set_tool(Tool.TEXT_BOX)
    # Click on empty area (PDF coords 100, 100)
    cx, cy = vt._pdf_to_canvas(100.0, 100.0)
    vt._on_mouse_down(cx, cy)
    QApplication.processEvents()
    assert vt._canvas._tb_editor.isVisible()
    assert vt._canvas._tb_editor.toPlainText() == ""
    vt.cleanup()


def test_double_click_freetext_opens_editor_with_existing_text(qapp, pdf_with_freetext):
    from PySide6.QtWidgets import QApplication

    vt = _open_and_render(qapp, pdf_with_freetext)
    # Double-click at annotation center (PDF 125, 65)
    cx, cy = vt._pdf_to_canvas(125.0, 65.0)
    vt._on_double_click(cx, cy)
    QApplication.processEvents()
    assert vt._canvas._tb_editor.isVisible()
    assert vt._canvas._tb_editor.toPlainText() == "Hello"
    vt.cleanup()


def test_commit_tb_editor_saves_multiline_text(qapp, pdf_with_freetext):
    from PySide6.QtWidgets import QApplication

    vt = _open_and_render(qapp, pdf_with_freetext)
    cx, cy = vt._pdf_to_canvas(125.0, 65.0)
    vt._on_double_click(cx, cy)
    QApplication.processEvents()

    editor = vt._canvas._tb_editor
    editor.setPlainText("Line one\nLine two")
    vt._commit_tb_editor()
    QApplication.processEvents()
    QApplication.processEvents()

    assert not editor.isVisible()
    page = vt.doc[0]
    annots = list(page.annots())
    assert len(annots) == 1
    content = annots[0].info.get("content", "")
    assert "Line one" in content
    assert "Line two" in content
    vt.cleanup()


def test_commit_empty_new_textbox_discards(qapp, empty_pdf):
    from PySide6.QtWidgets import QApplication
    from view_tool import Tool

    vt = _open_and_render(qapp, empty_pdf)
    vt._set_tool(Tool.TEXT_BOX)
    cx, cy = vt._pdf_to_canvas(100.0, 100.0)
    vt._on_mouse_down(cx, cy)
    QApplication.processEvents()

    # Commit with empty text
    vt._canvas._tb_editor.setPlainText("")
    vt._commit_tb_editor()
    QApplication.processEvents()
    QApplication.processEvents()

    page = vt.doc[0]
    assert len(list(page.annots())) == 0
    vt.cleanup()


def test_commit_existing_textbox_with_empty_text_deletes_annotation(
    qapp, pdf_with_freetext
):
    from PySide6.QtWidgets import QApplication

    vt = _open_and_render(qapp, pdf_with_freetext)
    page = vt.doc[0]
    assert len(list(page.annots())) == 1

    # Open editor on existing annotation
    cx, cy = vt._pdf_to_canvas(125.0, 65.0)
    vt._on_double_click(cx, cy)
    QApplication.processEvents()

    # Clear text and commit
    vt._canvas._tb_editor.setPlainText("")
    vt._commit_tb_editor()
    QApplication.processEvents()
    QApplication.processEvents()

    page = vt.doc[0]
    assert len(list(page.annots())) == 0
    assert vt._modified
    vt.cleanup()
