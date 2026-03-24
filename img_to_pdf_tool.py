"""Image to PDF Tool – combine one or more images into a single PDF.

PySide6. Loaded by main.py when the user clicks "Image to PDF".
"""

import logging
from pathlib import Path
from utils import assert_file_writable

from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QLineEdit,
    QScrollArea,
    QHBoxLayout,
    QVBoxLayout,
    QFileDialog,
    QMessageBox,
    QProgressBar,
    QComboBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import (
    QPixmap,
    QPainter,
    QColor,
    QPen,
    QDragEnterEvent,
    QDropEvent,
    QImageReader,
)

from colors import (
    BLUE,
    BLUE_HOVER,
    GREEN,
    GREEN_HOVER,
    RED,
    G100,
    G200,
    G300,
    G400,
    G500,
    G700,
    G900,
    WHITE,
    EMERALD,
    BLUE_MED,
)
from icons import svg_pixmap
from widgets import PreviewCanvas

try:
    import fitz
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)

SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif", ".webp"}

PAGE_SIZES = {
    "A4 Portrait": (595, 842),
    "A4 Landscape": (842, 595),
    "Letter Portrait": (612, 792),
    "Letter Landscape": (792, 612),
    "Fit to Image": None,
}

MARGINS = {
    "None": 0,
    "Small": 18,
    "Medium": 36,
    "Large": 72,
}

THUMB_W = 64
THUMB_H = 80


def _btn(text, bg, hover, text_color=WHITE, border=False, h=36, w=None) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(h)
    if w:
        b.setFixedWidth(w)
    border_s = f"border: 1px solid {G300};" if border else "border: none;"
    b.setStyleSheet(f"""
        QPushButton {{
            background: {bg}; color: {text_color};
            {border_s} border-radius: 6px;
            font: {"bold " if bg in (BLUE, GREEN) else ""}13px;
            padding: 0 12px;
        }}
        QPushButton:hover {{ background: {hover}; }}
        QPushButton:disabled {{ color: {G300}; background: {G100}; border-color: {G200}; }}
    """)
    return b


def _section(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
        " background: transparent; border: none;"
    )
    return lbl


def _combo(options: list[str]) -> QComboBox:
    c = QComboBox()
    c.addItems(options)
    c.setFixedHeight(36)
    c.setStyleSheet(f"""
        QComboBox {{
            border: 1px solid {G200}; border-radius: 6px;
            padding: 0 10px; font: 13px; color: {G900}; background: {WHITE};
        }}
        QComboBox::drop-down {{ border: none; width: 24px; }}
        QComboBox QAbstractItemView {{ border: 1px solid {G200}; background: {WHITE}; }}
    """)
    return c


# ===========================================================================
# Image Row
# ===========================================================================


class _ImgRow(QFrame):
    def __init__(self, path: str, thumb: QPixmap, parent=None):
        super().__init__(parent)
        self.path = path
        self._selected = False
        self.setFixedHeight(60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"background: {WHITE}; border: 1px solid {G200}; border-radius: 8px;"
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(10)

        thumb_lbl = QLabel()
        thumb_lbl.setFixedSize(36, 44)
        thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_lbl.setStyleSheet("border: none; background: transparent;")
        if thumb and not thumb.isNull():
            scaled = thumb.scaled(
                36,
                44,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            thumb_lbl.setPixmap(scaled)
        else:
            thumb_lbl.setPixmap(svg_pixmap("image", G400, 22))
        lay.addWidget(thumb_lbl)

        info = QVBoxLayout()
        info.setSpacing(2)
        info.setContentsMargins(0, 0, 0, 0)
        name = Path(path).name
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color: {G900}; font: 13px; border: none; background: transparent;"
        )
        name_lbl.setMinimumWidth(0)
        name_lbl.setMaximumWidth(140)
        fm = name_lbl.fontMetrics()
        name_lbl.setText(fm.elidedText(name, Qt.TextElideMode.ElideMiddle, 140))
        name_lbl.setToolTip(name)
        info.addWidget(name_lbl)

        ext_lbl = QLabel(Path(path).suffix.upper().lstrip("."))
        ext_lbl.setStyleSheet(
            f"color: {G500}; font: 11px; border: none; background: transparent;"
        )
        info.addWidget(ext_lbl)
        lay.addLayout(info, 1)

        _arrow_ss = (
            f"QPushButton {{ border: 1px solid {G200}; border-radius: 5px;"
            f" background: {WHITE}; color: {G700}; font: bold 13px; }}"
            f"QPushButton:hover {{ background: {G100}; }}"
            f"QPushButton:disabled {{ color: {G300}; background: {G100}; }}"
        )

        self._up_btn = QPushButton("↑")
        self._up_btn.setFixedSize(26, 26)
        self._up_btn.setStyleSheet(_arrow_ss)
        self._up_btn.setToolTip("Move up")
        lay.addWidget(self._up_btn)

        self._down_btn = QPushButton("↓")
        self._down_btn.setFixedSize(26, 26)
        self._down_btn.setStyleSheet(_arrow_ss)
        self._down_btn.setToolTip("Move down")
        lay.addWidget(self._down_btn)

        self._del_btn = QPushButton("✕")
        self._del_btn.setFixedSize(26, 26)
        self._del_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid {G200}; border-radius: 5px;"
            f" background: {WHITE}; color: {RED}; font: bold 11px; }}"
            f"QPushButton:hover {{ background: #FEF2F2; border-color: {RED}; }}"
        )
        self._del_btn.setToolTip("Remove")
        lay.addWidget(self._del_btn)

    def set_selected(self, v: bool):
        self._selected = v
        if v:
            self.setStyleSheet(
                f"background: #EFF6FF; border: 1.5px solid {BLUE}; border-radius: 8px;"
            )
        else:
            self.setStyleSheet(
                f"background: {WHITE}; border: 1px solid {G200}; border-radius: 8px;"
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            tool = self._find_tool()
            if tool:
                tool._on_row_clicked(self)

    def _find_tool(self):
        w = self.parent()
        while w:
            if isinstance(w, ImgToPDFTool):
                return w
            w = w.parent()
        return None


# ===========================================================================
# Preview Canvas
# ===========================================================================


class _PreviewCanvas(PreviewCanvas):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._page_w: float = 595  # A4 portrait default (points)
        self._page_h: float = 842
        self._margin: int = 18  # Small default

    def set_page_size(self, w: float, h: float):
        self._page_w = w
        self._page_h = h
        self.update()

    def set_margin(self, m: int):
        self._margin = m
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
                "Add images to see\na preview here",
            )
            return

        cw, ch = self.width(), self.height()
        pad = 36

        # Scale the page rectangle to fit the canvas
        scale = min((cw - pad * 2) / self._page_w, (ch - pad * 2) / self._page_h)
        pw = int(self._page_w * scale)
        ph = int(self._page_h * scale)
        px = (cw - pw) // 2
        py = (ch - ph) // 2

        # Drop shadow
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 30))
        p.drawRoundedRect(px + 4, py + 4, pw, ph, 4, 4)

        # White page background
        p.setBrush(QColor(WHITE))
        p.setPen(QPen(QColor(G200), 1))
        p.drawRect(px, py, pw, ph)

        # Margin area
        m = int(self._margin * scale)
        ix, iy = px + m, py + m
        iw, ih = pw - 2 * m, ph - 2 * m

        if self._margin > 0 and iw > 0 and ih > 0:
            p.setBrush(Qt.BrushStyle.NoBrush)
            pen = QPen(QColor(BLUE_MED), 1, Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.drawRect(ix, iy, iw, ih)

        # Image inside margin rect, keeping aspect ratio
        if iw > 0 and ih > 0:
            img_scale = min(iw / self._pixmap.width(), ih / self._pixmap.height())
            dw = int(self._pixmap.width() * img_scale)
            dh = int(self._pixmap.height() * img_scale)
            dx = ix + (iw - dw) // 2
            dy = iy + (ih - dh) // 2
            scaled = self._pixmap.scaled(
                dw,
                dh,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            p.drawPixmap(dx, dy, scaled)


# ===========================================================================
# ImgToPDFTool
# ===========================================================================


class _ImgToPdfWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, entries, out_path, page_size, margin):
        super().__init__()
        self._entries = entries
        self._out_path = out_path
        self._page_size = page_size
        self._margin = margin

    def run(self):
        try:
            assert_file_writable(Path(self._out_path))
            doc = fitz.open()
            for entry in self._entries:
                path = entry["path"]
                if self._page_size is None:
                    reader = QImageReader(path)
                    sz = reader.size()
                    w_pt = sz.width() * 72 / 96
                    h_pt = sz.height() * 72 / 96
                    pw, ph = max(w_pt, 72), max(h_pt, 72)
                else:
                    pw, ph = self._page_size
                page = doc.new_page(width=pw, height=ph)
                rect = fitz.Rect(
                    self._margin, self._margin, pw - self._margin, ph - self._margin
                )
                page.insert_image(rect, filename=path, keep_proportion=True)
            doc.save(self._out_path, garbage=3, deflate=True)
            doc.close()
            self.finished.emit(self._out_path)
        except PermissionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            logger.exception("worker failed")
            self.failed.emit(str(exc))


class ImgToPDFTool(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._modified = False

        if fitz is None:
            lay = QVBoxLayout(self)
            lbl = QLabel("Missing dependency.\n\nInstall with:\n  pip install pymupdf")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {G500}; font: 16px;")
            lay.addWidget(lbl)
            return

        self._entries: list[dict] = []  # {path, thumb}
        self._rows: list[_ImgRow] = []
        self._selected_idx: int = -1
        self._worker = None

        self._build_ui()
        self.setAcceptDrops(True)

    # -----------------------------------------------------------------------
    # UI
    # -----------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)
        body_lay.addWidget(self._build_left_panel())
        body_lay.addWidget(self._build_right_panel(), 1)
        root.addWidget(body, 1)

    def _build_left_panel(self) -> QWidget:
        left = QWidget()
        left.setFixedWidth(380)
        left.setStyleSheet(f"background: {WHITE}; border-right: 1px solid {G200};")
        outer = QVBoxLayout(left)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("border: none; background: transparent;")

        inner = QWidget()
        inner.setStyleSheet(f"background: {WHITE};")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(24, 24, 24, 12)
        lay.setSpacing(0)

        # Title
        title_row = QHBoxLayout()
        title_row.setSpacing(12)
        title_row.setContentsMargins(0, 0, 0, 0)
        icon_box = QLabel()
        icon_box.setFixedSize(40, 40)
        icon_box.setPixmap(svg_pixmap("image", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)
        title_lbl = QLabel("Image to PDF")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 20px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        # Images section
        lay.addWidget(_section("IMAGES"))
        lay.addSpacing(8)

        dz = QFrame()
        dz.setFixedHeight(52)
        dz.setStyleSheet(
            f"background: {G100}; border: 2px dashed {G200}; border-radius: 12px;"
        )
        dz_h = QHBoxLayout(dz)
        dz_h.setContentsMargins(10, 0, 10, 0)
        dz_h.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(svg_pixmap("image", G400, 18))
        ic.setStyleSheet("border: none; background: transparent;")
        dz_h.addWidget(ic)
        dz_lbl = QLabel("Drop images here or")
        dz_lbl.setStyleSheet(
            f"color: {G500}; font: 13px; border: none; background: transparent;"
        )
        dz_h.addWidget(dz_lbl)
        add_btn = _btn("Add", BLUE, BLUE_HOVER, h=30, w=60)
        add_btn.clicked.connect(self._browse_images)
        dz_h.addWidget(add_btn)
        dz_h.addStretch()
        lay.addWidget(dz)
        lay.addSpacing(10)

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet(f"background: {WHITE};")
        self._list_lay = QVBoxLayout(self._list_widget)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(5)
        self._list_lay.addStretch()
        lay.addWidget(self._list_widget)
        lay.addSpacing(20)

        # Page size
        lay.addWidget(_section("PAGE SIZE"))
        lay.addSpacing(8)
        self._size_combo = _combo(list(PAGE_SIZES.keys()))
        self._size_combo.currentIndexChanged.connect(self._update_canvas_settings)
        lay.addWidget(self._size_combo)
        lay.addSpacing(16)

        # Margin
        lay.addWidget(_section("MARGIN"))
        lay.addSpacing(8)
        self._margin_combo = _combo(list(MARGINS.keys()))
        self._margin_combo.setCurrentText("Small")
        self._margin_combo.currentIndexChanged.connect(self._update_canvas_settings)
        lay.addWidget(self._margin_combo)

        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # Bottom
        bottom = QWidget()
        bottom.setStyleSheet(f"background: {WHITE}; border-top: 1px solid {G200};")
        bot = QVBoxLayout(bottom)
        bot.setContentsMargins(24, 16, 24, 20)
        bot.setSpacing(10)

        bot.addWidget(_section("OUTPUT FILE"))
        self._out_entry = QLineEdit("images.pdf")
        self._out_entry.setFixedHeight(36)
        self._out_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        bot.addWidget(self._out_entry)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )
        bot.addWidget(self._status_lbl)

        self._progress = QProgressBar()
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 100)
        self._progress.setStyleSheet(
            f"QProgressBar {{ background: {G200}; border-radius: 3px; border: none; }}"
            f"QProgressBar::chunk {{ background: {GREEN}; border-radius: 3px; }}"
        )
        self._progress.hide()
        bot.addWidget(self._progress)

        self._convert_btn = _btn("Convert to PDF", GREEN, GREEN_HOVER, h=42)
        self._convert_btn.setEnabled(False)
        self._convert_btn.clicked.connect(self._convert)
        bot.addWidget(self._convert_btn)

        outer.addWidget(bottom)
        return left

    def _build_right_panel(self) -> QWidget:
        right = QWidget()
        right.setStyleSheet(f"background: {G100};")
        v = QVBoxLayout(right)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        toolbar = QWidget()
        toolbar.setFixedHeight(48)
        toolbar.setStyleSheet(f"background: {WHITE}; border-bottom: 1px solid {G200};")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(16, 0, 16, 0)
        self._toolbar_lbl = QLabel("No images added")
        self._toolbar_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._toolbar_lbl)
        tb.addStretch()
        v.addWidget(toolbar)

        self._canvas = _PreviewCanvas()
        v.addWidget(self._canvas, 1)
        return right

    # -----------------------------------------------------------------------
    # File management
    # -----------------------------------------------------------------------

    def _browse_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Images",
            "",
            "Images (*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.tif *.webp)",
        )
        for p in paths:
            self._add_image(p)

    def _add_image(self, path: str):
        if Path(path).suffix.lower() not in SUPPORTED_EXT:
            return
        if any(e["path"] == path for e in self._entries):
            return

        pm = QPixmap(path)
        if pm.isNull():
            return

        thumb = pm.scaled(
            THUMB_W,
            THUMB_H,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._entries.append({"path": path, "thumb": thumb, "pixmap": pm})
        self._rebuild_list()

        if self._selected_idx == -1:
            self._select(0)
        self._update_btn()

    def _rebuild_list(self):
        for row in self._rows:
            self._list_lay.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        self._list_lay.takeAt(self._list_lay.count() - 1)

        for i, entry in enumerate(self._entries):
            row = _ImgRow(entry["path"], entry["thumb"], self._list_widget)
            row.set_selected(i == self._selected_idx)
            row._up_btn.clicked.connect(lambda _=False, idx=i: self._move_up(idx))
            row._down_btn.clicked.connect(lambda _=False, idx=i: self._move_down(idx))
            row._del_btn.clicked.connect(lambda _=False, idx=i: self._remove(idx))
            self._list_lay.addWidget(row)
            self._rows.append(row)

        self._list_lay.addStretch()

        for i, row in enumerate(self._rows):
            row._up_btn.setEnabled(i > 0)
            row._down_btn.setEnabled(i < len(self._rows) - 1)

        n = len(self._entries)
        self._toolbar_lbl.setText(
            f"{n} image{'s' if n != 1 else ''}" if n else "No images added"
        )

    def _move_up(self, idx: int):
        if idx <= 0:
            return
        self._entries[idx], self._entries[idx - 1] = (
            self._entries[idx - 1],
            self._entries[idx],
        )
        if self._selected_idx == idx:
            self._selected_idx = idx - 1
        elif self._selected_idx == idx - 1:
            self._selected_idx = idx
        self._rebuild_list()

    def _move_down(self, idx: int):
        if idx >= len(self._entries) - 1:
            return
        self._entries[idx], self._entries[idx + 1] = (
            self._entries[idx + 1],
            self._entries[idx],
        )
        if self._selected_idx == idx:
            self._selected_idx = idx + 1
        elif self._selected_idx == idx + 1:
            self._selected_idx = idx
        self._rebuild_list()

    def _remove(self, idx: int):
        self._entries.pop(idx)
        if self._selected_idx >= len(self._entries):
            self._selected_idx = len(self._entries) - 1
        self._rebuild_list()
        if self._selected_idx >= 0:
            self._select(self._selected_idx)
        else:
            self._canvas.set_pixmap(None)
        self._update_btn()

    def _on_row_clicked(self, row: _ImgRow):
        idx = self._rows.index(row) if row in self._rows else -1
        if idx != -1:
            self._select(idx)

    def _select(self, idx: int):
        self._selected_idx = idx
        for i, row in enumerate(self._rows):
            row.set_selected(i == idx)
        if 0 <= idx < len(self._entries):
            self._canvas.set_pixmap(self._entries[idx]["pixmap"])
            self._update_canvas_settings()

    def _update_canvas_settings(self):
        margin = MARGINS[self._margin_combo.currentText()]
        self._canvas.set_margin(margin)

        size_key = self._size_combo.currentText()
        page_size = PAGE_SIZES[size_key]
        if page_size is not None:
            self._canvas.set_page_size(page_size[0], page_size[1])
        elif 0 <= self._selected_idx < len(self._entries):
            # Fit to Image: derive page size from actual image dimensions
            pm = self._entries[self._selected_idx]["pixmap"]
            # pixels → points at 96 DPI
            w_pt = pm.width() * 72 / 96
            h_pt = pm.height() * 72 / 96
            self._canvas.set_page_size(max(w_pt, 72), max(h_pt, 72))

    def _update_btn(self):
        self._convert_btn.setEnabled(len(self._entries) > 0)

    # -----------------------------------------------------------------------
    # Convert
    # -----------------------------------------------------------------------

    def _convert(self):
        if not self._entries:
            return

        out_name = self._out_entry.text().strip() or "images.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF", out_name, "PDF Files (*.pdf)"
        )
        if not out_path:
            return

        size_key = self._size_combo.currentText()
        page_size = PAGE_SIZES[size_key]
        margin = MARGINS[self._margin_combo.currentText()]
        self._progress.setValue(0)
        self._progress.show()
        self._convert_btn.setEnabled(False)
        self._status_lbl.setText("Converting...")

        self._worker = _ImgToPdfWorker(list(self._entries), out_path, page_size, margin)
        self._worker.finished.connect(self._on_save_done)
        self._worker.failed.connect(self._on_save_failed)
        self._worker.start()

    def _on_save_done(self, out_path: str):
        self._status_lbl.setText(f"Saved: {Path(out_path).name}")
        self._status_lbl.setStyleSheet(
            f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
        )
        self._convert_btn.setEnabled(len(self._entries) > 0)
        self._progress.hide()

    def _on_save_failed(self, msg: str):
        QMessageBox.critical(self, "Save failed", msg)
        self._status_lbl.setText("Conversion failed.")
        self._convert_btn.setEnabled(len(self._entries) > 0)
        self._progress.hide()

    # -----------------------------------------------------------------------
    # Drag and drop
    # -----------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if Path(path).suffix.lower() in SUPPORTED_EXT:
                self._add_image(path)

    def cleanup(self):
        pass
