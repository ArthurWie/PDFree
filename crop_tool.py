"""Crop Tool – interactively crop pages of a PDF by drawing a crop region.

PySide6. Loaded by main.py when the user clicks "Crop PDF".
"""

import logging
from pathlib import Path
from utils import assert_file_writable, backup_original

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
    QSizePolicy,
    QComboBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QCursor,
    QDragEnterEvent,
    QDropEvent,
)

from colors import (
    BLUE,
    BLUE_HOVER,
    GREEN,
    GREEN_HOVER,
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
from utils import _fitz_pix_to_qpixmap

try:
    import fitz
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)

APPLY_MODES = ["All pages", "Current page only"]
RENDER_SCALE = 1.5


def _btn(text, bg, hover, text_color=WHITE, border=False, h=36, w=None):
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


def _section(text):
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
        " background: transparent; border: none;"
    )
    return lbl


def _combo(options):
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
# Crop Canvas
# ===========================================================================


class _CropCanvas(QWidget):
    crop_changed = Signal(float, float, float, float)  # x0,y0,x1,y1 page coords

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = None
        self._page_w = 1.0
        self._page_h = 1.0
        # crop rect in page coords
        self._cx0 = 0.0
        self._cy0 = 0.0
        self._cx1 = 1.0
        self._cy1 = 1.0
        # drag state
        self._dragging = False
        self._drag_sx = 0
        self._drag_sy = 0
        self._drag_ex = 0
        self._drag_ey = 0
        # cached render geometry (set in paintEvent)
        self._ox = 0
        self._oy = 0
        self._dw = 1
        self._dh = 1

        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    def set_page(self, pixmap, page_w, page_h):
        self._pixmap = pixmap
        self._page_w = max(page_w, 1.0)
        self._page_h = max(page_h, 1.0)
        self._cx0 = 0.0
        self._cy0 = 0.0
        self._cx1 = self._page_w
        self._cy1 = self._page_h
        self.update()

    def reset(self):
        self._cx0 = 0.0
        self._cy0 = 0.0
        self._cx1 = self._page_w
        self._cy1 = self._page_h
        self.crop_changed.emit(self._cx0, self._cy0, self._cx1, self._cy1)
        self.update()

    def get_crop_rect(self):
        return self._cx0, self._cy0, self._cx1, self._cy1

    # -----------------------------------------------------------------------

    def _screen_to_page(self, sx, sy):
        px = (sx - self._ox) / self._dw * self._page_w
        py = (sy - self._oy) / self._dh * self._page_h
        return (
            max(0.0, min(self._page_w, px)),
            max(0.0, min(self._page_h, py)),
        )

    def _page_to_screen(self, px, py):
        return (
            self._ox + px / self._page_w * self._dw,
            self._oy + py / self._page_h * self._dh,
        )

    # -----------------------------------------------------------------------

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(G100))

        if self._pixmap is None or self._pixmap.isNull():
            p.setPen(QColor(G400))
            p.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Load a PDF, then drag to\nset the crop region",
            )
            return

        cw, ch = self.width(), self.height()
        pw, ph = self._pixmap.width(), self._pixmap.height()
        scale = min((cw - 48) / pw, (ch - 48) / ph, 1.0)
        dw, dh = int(pw * scale), int(ph * scale)
        ox = (cw - dw) // 2
        oy = (ch - dh) // 2

        self._ox, self._oy, self._dw, self._dh = ox, oy, dw, dh

        # Shadow
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 28))
        p.drawRoundedRect(ox + 4, oy + 4, dw, dh, 4, 4)

        # Page
        scaled = self._pixmap.scaled(
            dw,
            dh,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        p.drawPixmap(ox, oy, scaled)

        # Determine which crop rect to show
        if self._dragging:
            xs = sorted([self._drag_sx, self._drag_ex])
            ys = sorted([self._drag_sy, self._drag_ey])
            sx0, sy0, sx1, sy1 = xs[0], ys[0], xs[1], ys[1]
        else:
            sx0, sy0 = self._page_to_screen(self._cx0, self._cy0)
            sx1, sy1 = self._page_to_screen(self._cx1, self._cy1)

        rx = int(sx0)
        ry = int(sy0)
        rw = int(sx1) - rx
        rh = int(sy1) - ry

        # Dim outside crop rect
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 80))
        if ry > oy:
            p.drawRect(ox, oy, dw, ry - oy)
        if ry + rh < oy + dh:
            p.drawRect(ox, ry + rh, dw, (oy + dh) - (ry + rh))
        if rx > ox:
            p.drawRect(ox, ry, rx - ox, rh)
        if rx + rw < ox + dw:
            p.drawRect(rx + rw, ry, (ox + dw) - (rx + rw), rh)

        # Crop border
        pen = QPen(QColor(BLUE), 2, Qt.PenStyle.SolidLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(rx, ry, rw, rh)

        # Corner handles
        p.setBrush(QColor(WHITE))
        for hx, hy in [(rx, ry), (rx + rw, ry), (rx, ry + rh), (rx + rw, ry + rh)]:
            p.drawEllipse(hx - 5, hy - 5, 10, 10)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._pixmap:
            pos = event.position()
            self._dragging = True
            sx = max(self._ox, min(self._ox + self._dw, int(pos.x())))
            sy = max(self._oy, min(self._oy + self._dh, int(pos.y())))
            self._drag_sx = sx
            self._drag_sy = sy
            self._drag_ex = sx
            self._drag_ey = sy
            self.update()

    def mouseMoveEvent(self, event):
        if self._dragging:
            pos = event.position()
            self._drag_ex = max(self._ox, min(self._ox + self._dw, int(pos.x())))
            self._drag_ey = max(self._oy, min(self._oy + self._dh, int(pos.y())))
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            pos = event.position()
            self._drag_ex = max(self._ox, min(self._ox + self._dw, int(pos.x())))
            self._drag_ey = max(self._oy, min(self._oy + self._dh, int(pos.y())))

            xs = sorted([self._drag_sx, self._drag_ex])
            ys = sorted([self._drag_sy, self._drag_ey])

            if xs[1] - xs[0] < 4 or ys[1] - ys[0] < 4:
                self.update()
                return

            self._cx0, self._cy0 = self._screen_to_page(xs[0], ys[0])
            self._cx1, self._cy1 = self._screen_to_page(xs[1], ys[1])
            self.crop_changed.emit(self._cx0, self._cy0, self._cx1, self._cy1)
            self.update()


# ===========================================================================
# CropTool
# ===========================================================================


class _CropWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        pdf_path,
        out_path,
        apply_all,
        current_page,
        page_w,
        page_h,
        x0,
        y0,
        x1,
        y1,
    ):
        super().__init__()
        self._pdf_path = pdf_path
        self._out_path = out_path
        self._apply_all = apply_all
        self._current_page = current_page
        self._page_w = page_w
        self._page_h = page_h
        self._x0 = x0
        self._y0 = y0
        self._x1 = x1
        self._y1 = y1

    def run(self):
        try:
            assert_file_writable(Path(self._out_path))
            backup_original(Path(self._pdf_path))
            doc = fitz.open(self._pdf_path)
            for i, page in enumerate(doc):
                if not self._apply_all and i != self._current_page:
                    continue
                if self._apply_all:
                    fx0 = self._x0 / self._page_w * page.rect.width
                    fy0 = self._y0 / self._page_h * page.rect.height
                    fx1 = self._x1 / self._page_w * page.rect.width
                    fy1 = self._y1 / self._page_h * page.rect.height
                else:
                    fx0, fy0, fx1, fy1 = self._x0, self._y0, self._x1, self._y1
                crop = fitz.Rect(fx0, fy0, fx1, fy1)
                crop = crop & page.rect
                if not crop.is_empty:
                    page.set_cropbox(crop)
            doc.save(self._out_path, garbage=3, deflate=True)
            doc.close()
            self.finished.emit(self._out_path)
        except PermissionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            logger.exception("worker failed")
            self.failed.emit(str(exc))


class CropTool(QWidget):
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

        self._pdf_path = ""
        self._doc = None
        self._total_pages = 0
        self._current_page = 0
        self._worker = None
        self._build_ui()
        self.setAcceptDrops(True)

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_left_panel())
        root.addWidget(self._build_right_panel(), 1)

    def _build_left_panel(self):
        left = QWidget()
        left.setFixedWidth(320)
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
        icon_box.setPixmap(svg_pixmap("scan-line", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)
        title_lbl = QLabel("Crop PDF")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 18px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        # File
        lay.addWidget(_section("SOURCE FILE"))
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
        ic.setPixmap(svg_pixmap("file-text", G400, 18))
        ic.setStyleSheet("border: none; background: transparent;")
        dz_h.addWidget(ic)
        dz_lbl = QLabel("Drop PDF or")
        dz_lbl.setStyleSheet(
            f"color: {G500}; font: 13px; border: none; background: transparent;"
        )
        dz_h.addWidget(dz_lbl)
        browse_btn = _btn("Browse", BLUE, BLUE_HOVER, h=30, w=80)
        browse_btn.clicked.connect(self._browse)
        dz_h.addWidget(browse_btn)
        dz_h.addStretch()
        lay.addWidget(dz)
        lay.addSpacing(8)
        self._file_lbl = QLabel("No file loaded")
        self._file_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        self._file_lbl.setWordWrap(True)
        lay.addWidget(self._file_lbl)
        lay.addSpacing(24)

        # Apply mode
        lay.addWidget(_section("APPLY TO"))
        lay.addSpacing(8)
        self._apply_combo = _combo(APPLY_MODES)
        lay.addWidget(self._apply_combo)
        lay.addSpacing(24)

        # Crop info
        lay.addWidget(_section("CROP REGION"))
        lay.addSpacing(8)
        self._crop_lbl = QLabel(
            "Draw a rectangle on the page\nto define the crop area."
        )
        self._crop_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        self._crop_lbl.setWordWrap(True)
        lay.addWidget(self._crop_lbl)
        lay.addSpacing(12)

        self._reset_btn = _btn(
            "Reset to Full Page", WHITE, G100, G700, border=True, h=34
        )
        self._reset_btn.setEnabled(False)
        self._reset_btn.clicked.connect(self._reset_crop)
        lay.addWidget(self._reset_btn)

        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # Bottom bar
        bottom = QWidget()
        bottom.setStyleSheet(f"background: {WHITE}; border-top: 1px solid {G200};")
        bot = QVBoxLayout(bottom)
        bot.setContentsMargins(24, 16, 24, 20)
        bot.setSpacing(10)

        bot.addWidget(_section("OUTPUT FILE"))
        self._out_entry = QLineEdit()
        self._out_entry.setPlaceholderText("output_cropped.pdf")
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

        self._save_btn = _btn("Apply Crop & Save", GREEN, GREEN_HOVER, h=42)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save)
        bot.addWidget(self._save_btn)

        outer.addWidget(bottom)
        return left

    def _build_right_panel(self):
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
        tb.setSpacing(12)

        self._toolbar_lbl = QLabel("Draw a crop region on the page")
        self._toolbar_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._toolbar_lbl)
        tb.addStretch()

        _arrow_ss = (
            f"QPushButton {{ border: 1px solid {G200}; border-radius: 6px;"
            f" background: {WHITE}; color: {G700}; font: bold 15px; }}"
            f"QPushButton:hover {{ background: {G100}; }}"
            f"QPushButton:disabled {{ color: {G300}; background: {G100}; }}"
        )
        prev_btn = QPushButton("‹")
        prev_btn.setFixedSize(32, 32)
        prev_btn.setStyleSheet(_arrow_ss)
        prev_btn.clicked.connect(self._prev_page)
        tb.addWidget(prev_btn)

        self._page_lbl = QLabel("")
        self._page_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        tb.addWidget(self._page_lbl)

        next_btn = QPushButton("›")
        next_btn.setFixedSize(32, 32)
        next_btn.setStyleSheet(_arrow_ss)
        next_btn.clicked.connect(self._next_page)
        tb.addWidget(next_btn)

        v.addWidget(toolbar)

        self._canvas = _CropCanvas()
        self._canvas.crop_changed.connect(self._on_crop_changed)
        v.addWidget(self._canvas, 1)
        return right

    # -----------------------------------------------------------------------
    # File loading
    # -----------------------------------------------------------------------

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if path:
            self._load_file(path)

    def _load_file(self, path):
        if self._doc:
            try:
                self._doc.close()
            except Exception:
                pass
        try:
            self._doc = fitz.open(path)
        except Exception as exc:
            logger.exception("could not open pdf")
            QMessageBox.warning(self, "Error", f"Could not open PDF:\n{exc}")
            return

        self._pdf_path = path
        self._total_pages = self._doc.page_count
        self._current_page = 0
        self._file_lbl.setText(Path(path).name)
        self._out_entry.setText(f"{Path(path).stem}_cropped.pdf")
        self._save_btn.setEnabled(True)
        self._reset_btn.setEnabled(True)
        self._show_page()

    def _show_page(self):
        if not self._doc:
            return
        page = self._doc[self._current_page]
        mat = fitz.Matrix(RENDER_SCALE, RENDER_SCALE)
        pix = page.get_pixmap(matrix=mat)
        pm = _fitz_pix_to_qpixmap(pix)
        self._canvas.set_page(pm, page.rect.width, page.rect.height)
        self._page_lbl.setText(f"{self._current_page + 1} / {self._total_pages}")
        self._toolbar_lbl.setText(f"Drag to crop — {Path(self._pdf_path).name}")
        self._update_crop_label()

    def _prev_page(self):
        if self._doc and self._current_page > 0:
            self._current_page -= 1
            self._show_page()

    def _next_page(self):
        if self._doc and self._current_page < self._total_pages - 1:
            self._current_page += 1
            self._show_page()

    # -----------------------------------------------------------------------
    # Crop
    # -----------------------------------------------------------------------

    def _reset_crop(self):
        self._canvas.reset()

    def _on_crop_changed(self, x0, y0, x1, y1):
        self._update_crop_label()

    def _update_crop_label(self):
        x0, y0, x1, y1 = self._canvas.get_crop_rect()
        w = x1 - x0
        h = y1 - y0
        self._crop_lbl.setText(
            f"Left: {x0:.0f} pt    Top: {y0:.0f} pt\n"
            f"Width: {w:.0f} pt    Height: {h:.0f} pt"
        )

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------

    def _save(self):
        x0, y0, x1, y1 = self._canvas.get_crop_rect()
        if x1 - x0 < 4 or y1 - y0 < 4:
            QMessageBox.warning(
                self, "No crop region", "Draw a crop region on the page first."
            )
            return

        out_name = self._out_entry.text().strip() or "cropped.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        default_dir = str(Path(self._pdf_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Cropped PDF",
            str(Path(default_dir) / out_name),
            "PDF Files (*.pdf)",
        )
        if not out_path:
            return

        apply_all = self._apply_combo.currentText() == "All pages"
        page_w = self._doc[self._current_page].rect.width
        page_h = self._doc[self._current_page].rect.height

        self._save_btn.setEnabled(False)
        self._status_lbl.setText("Saving...")

        self._worker = _CropWorker(
            self._pdf_path,
            out_path,
            apply_all,
            self._current_page,
            page_w,
            page_h,
            x0,
            y0,
            x1,
            y1,
        )
        self._worker.finished.connect(self._on_save_done)
        self._worker.failed.connect(self._on_save_failed)
        self._worker.start()

    def _on_save_done(self, out_path: str):
        self._status_lbl.setText(f"Saved: {Path(out_path).name}")
        self._status_lbl.setStyleSheet(
            f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
        )
        self._save_btn.setEnabled(True)

    def _on_save_failed(self, msg: str):
        QMessageBox.critical(self, "Save failed", msg)
        self._status_lbl.setText("Save failed.")
        self._save_btn.setEnabled(True)

    # -----------------------------------------------------------------------
    # Drag and drop
    # -----------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pdf"):
                self._load_file(path)
                break

    def cleanup(self):
        if self._doc:
            try:
                self._doc.close()
            except Exception:
                pass
            self._doc = None
