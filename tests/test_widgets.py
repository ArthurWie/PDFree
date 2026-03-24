from widgets import PreviewCanvas
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPixmap


def test_preview_canvas_importable():
    assert PreviewCanvas is not None


def test_preview_canvas_is_qwidget(qtbot):
    canvas = PreviewCanvas()
    qtbot.addWidget(canvas)
    assert isinstance(canvas, QWidget)


def test_preview_canvas_set_pixmap(qtbot):
    canvas = PreviewCanvas()
    qtbot.addWidget(canvas)
    pm = QPixmap(100, 100)
    canvas.set_pixmap(pm)
    assert canvas._pixmap is pm


def test_preview_canvas_set_pixmap_none(qtbot):
    canvas = PreviewCanvas()
    qtbot.addWidget(canvas)
    canvas.set_pixmap(None)
    assert canvas._pixmap is None


def test_preview_canvas_minimum_size(qtbot):
    canvas = PreviewCanvas()
    qtbot.addWidget(canvas)
    assert canvas.minimumWidth() > 0
    assert canvas.minimumHeight() > 0
