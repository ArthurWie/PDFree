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


def test_card_wrap_returns_qwidget(qtbot):
    from PySide6.QtWidgets import QTreeWidget
    from widgets import card_wrap

    inner = QTreeWidget()
    qtbot.addWidget(inner)
    wrapper = card_wrap(inner)
    qtbot.addWidget(wrapper)
    assert isinstance(wrapper, QWidget)


def test_card_wrap_contains_inner_widget(qtbot):
    from PySide6.QtWidgets import QTreeWidget
    from widgets import card_wrap

    inner = QTreeWidget()
    qtbot.addWidget(inner)
    wrapper = card_wrap(inner)
    qtbot.addWidget(wrapper)
    assert inner.parent() == wrapper


def test_card_wrap_applies_border_stylesheet(qtbot):
    from PySide6.QtWidgets import QTreeWidget
    from widgets import card_wrap

    inner = QTreeWidget()
    qtbot.addWidget(inner)
    wrapper = card_wrap(inner)
    qtbot.addWidget(wrapper)
    assert "border-radius: 8px" in wrapper.styleSheet()
    assert "border:" in wrapper.styleSheet()
