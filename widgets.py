"""Shared reusable Qt widgets for PDFree tool panels."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from colors import BLUE_DIM, G100, G200, G400, G700, G900, WHITE


class PreviewCanvas(QWidget):
    """Shared PDF page preview canvas used across tool panels.

    Renders a pixmap centred and scaled inside the widget with a drop shadow.
    Call set_pixmap() to update the displayed image.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_pixmap(self, pm: QPixmap | None) -> None:
        self._pixmap = pm
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(G100))

        if self._pixmap is None or self._pixmap.isNull():
            p.setPen(QColor(G400))
            p.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Load a PDF to see\na preview here",
            )
            return

        pw, ph = self._pixmap.width(), self._pixmap.height()
        cw, ch = self.width(), self.height()
        scale = min((cw - 48) / pw, (ch - 48) / ph, 1.0)
        dw, dh = int(pw * scale), int(ph * scale)
        x = (cw - dw) // 2
        y = (ch - dh) // 2

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 28))
        p.drawRoundedRect(x + 4, y + 4, dw, dh, 4, 4)

        scaled = self._pixmap.scaled(
            dw,
            dh,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        p.drawPixmap(x, y, scaled)


def card_wrap(widget, parent=None):
    from PySide6.QtWidgets import QVBoxLayout

    container = QWidget(parent)
    container.setObjectName("cardWrap")
    container.setStyleSheet(
        "#cardWrap { background: " + WHITE + "; border: 1px solid " + G200 + ";"
        " border-radius: 8px; }"
    )
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    widget.setStyleSheet(
        "QTreeWidget, QTableWidget { border: none; background: " + WHITE + ";"
        " alternate-background-color: " + G100 + "; font: 13px; }"
        "QTreeWidget::item, QTableWidget::item { padding: 4px 8px; color: "
        + G900
        + "; }"
        "QTreeWidget::item:selected, QTableWidget::item:selected"
        " { background: " + BLUE_DIM + "; color: " + G900 + "; }"
        "QHeaderView::section { background: " + G100 + "; color: " + G700 + ";"
        " font: bold 11px; padding: 6px 8px; border: none;"
        " border-bottom: 1px solid " + G200 + "; }"
    )
    layout.addWidget(widget)
    return container
