"""Watermark Tool – stamp a text watermark onto every page of a PDF.

PySide6. Loaded by main.py when the user clicks "Add Watermark".
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
    QSlider,
)
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QPainter,
    QColor,
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
from widgets import PreviewCanvas

try:
    import fitz
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)

POSITIONS = ["Diagonal", "Center", "Top", "Bottom"]


class _WatermarkWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(
        self, pdf_path, out_path, text, fontsize, rgb, opacity, position, parent=None
    ):
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._out_path = out_path
        self._text = text
        self._fontsize = fontsize
        self._rgb = rgb
        self._opacity = opacity
        self._position = position

    def run(self):
        try:
            assert_file_writable(Path(self._out_path))
            backup_original(Path(self._pdf_path))
            doc = fitz.open(self._pdf_path)
            for page in doc:
                _stamp_watermark(
                    page,
                    self._text,
                    self._fontsize,
                    self._rgb,
                    self._opacity,
                    self._position,
                )
            doc.save(self._out_path, garbage=3, deflate=True)
            doc.close()
            self.finished.emit(self._out_path)
        except PermissionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            logger.exception("worker failed")
            self.failed.emit(str(exc))


COLOR_PRESETS = {
    "Gray": (0.50, 0.50, 0.50),
    "Red": (0.80, 0.10, 0.10),
    "Blue": (0.10, 0.30, 0.85),
    "Green": (0.10, 0.55, 0.20),
    "Black": (0.00, 0.00, 0.00),
}

PREVIEW_SCALE = 1.2


def _stamp_watermark(page, text, fontsize, rgb, opacity, position):
    font = fitz.Font("helv")
    tw = fitz.TextWriter(page.rect)
    w, h = page.rect.width, page.rect.height
    text_len = font.text_length(text, fontsize)

    if position == "Diagonal":
        cx = w / 2 - text_len / 2
        cy = h / 2 + fontsize * 0.35
        tw.append(fitz.Point(cx, cy), text, fontsize=fontsize, font=font)
        mat = fitz.Matrix(-45)
        pivot = fitz.Point(w / 2, h / 2)
        tw.write_text(page, color=rgb, opacity=opacity, morph=(pivot, mat))
    elif position == "Center":
        cx = max(0.0, w / 2 - text_len / 2)
        cy = h / 2 + fontsize * 0.35
        tw.append(fitz.Point(cx, cy), text, fontsize=fontsize, font=font)
        tw.write_text(page, color=rgb, opacity=opacity)
    elif position == "Top":
        cx = max(0.0, w / 2 - text_len / 2)
        cy = 40.0 + fontsize
        tw.append(fitz.Point(cx, cy), text, fontsize=fontsize, font=font)
        tw.write_text(page, color=rgb, opacity=opacity)
    else:  # Bottom
        cx = max(0.0, w / 2 - text_len / 2)
        cy = h - 36.0
        tw.append(fitz.Point(cx, cy), text, fontsize=fontsize, font=font)
        tw.write_text(page, color=rgb, opacity=opacity)


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


def _slider(min_v, max_v, val):
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(min_v, max_v)
    s.setValue(val)
    s.setStyleSheet(
        f"QSlider::groove:horizontal {{ background: {G200}; height: 4px; border-radius: 2px; }}"
        f"QSlider::handle:horizontal {{ background: {BLUE}; width: 16px; height: 16px;"
        f" margin: -6px 0; border-radius: 8px; }}"
        f"QSlider::sub-page:horizontal {{ background: {BLUE}; border-radius: 2px; }}"
    )
    return s


# ===========================================================================
# WatermarkTool
# ===========================================================================


class WatermarkTool(QWidget):
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
        self._preview_page = 0
        self._worker = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(200)
        self._preview_timer.timeout.connect(self._refresh_preview)

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
        icon_box.setPixmap(svg_pixmap("droplets", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)
        title_lbl = QLabel("Add Watermark")
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

        # Text
        lay.addWidget(_section("WATERMARK TEXT"))
        lay.addSpacing(8)
        self._text_entry = QLineEdit()
        self._text_entry.setPlaceholderText("e.g. CONFIDENTIAL")
        self._text_entry.setText("CONFIDENTIAL")
        self._text_entry.setFixedHeight(36)
        self._text_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        self._text_entry.textChanged.connect(self._queue_preview)
        lay.addWidget(self._text_entry)
        lay.addSpacing(16)

        # Position
        lay.addWidget(_section("POSITION"))
        lay.addSpacing(8)
        self._pos_combo = _combo(POSITIONS)
        self._pos_combo.currentTextChanged.connect(self._queue_preview)
        lay.addWidget(self._pos_combo)
        lay.addSpacing(16)

        # Color
        lay.addWidget(_section("COLOR"))
        lay.addSpacing(8)
        self._color_combo = _combo(list(COLOR_PRESETS.keys()))
        self._color_combo.currentTextChanged.connect(self._queue_preview)
        lay.addWidget(self._color_combo)
        lay.addSpacing(16)

        # Font size
        lay.addWidget(_section("FONT SIZE"))
        lay.addSpacing(8)
        size_row = QHBoxLayout()
        size_row.setSpacing(12)
        size_row.setContentsMargins(0, 0, 0, 0)
        self._size_slider = _slider(12, 96, 48)
        self._size_lbl = QLabel("48 pt")
        self._size_lbl.setFixedWidth(44)
        self._size_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        self._size_slider.valueChanged.connect(self._on_size_changed)
        size_row.addWidget(self._size_slider, 1)
        size_row.addWidget(self._size_lbl)
        lay.addLayout(size_row)
        lay.addSpacing(16)

        # Opacity
        lay.addWidget(_section("OPACITY"))
        lay.addSpacing(8)
        op_row = QHBoxLayout()
        op_row.setSpacing(12)
        op_row.setContentsMargins(0, 0, 0, 0)
        self._opacity_slider = _slider(5, 100, 30)
        self._opacity_lbl = QLabel("30%")
        self._opacity_lbl.setFixedWidth(36)
        self._opacity_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        op_row.addWidget(self._opacity_slider, 1)
        op_row.addWidget(self._opacity_lbl)
        lay.addLayout(op_row)

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
        self._out_entry.setPlaceholderText("output_watermarked.pdf")
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

        self._save_btn = _btn("Apply Watermark", GREEN, GREEN_HOVER, h=42)
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

        self._toolbar_lbl = QLabel("Preview")
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
        self._canvas = PreviewCanvas()
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
        self._preview_page = 0
        self._file_lbl.setText(Path(path).name)
        self._out_entry.setText(f"{Path(path).stem}_watermarked.pdf")
        self._save_btn.setEnabled(True)
        self._refresh_preview()

    # -----------------------------------------------------------------------
    # Preview
    # -----------------------------------------------------------------------

    def _on_size_changed(self, v):
        self._size_lbl.setText(f"{v} pt")
        self._queue_preview()

    def _on_opacity_changed(self, v):
        self._opacity_lbl.setText(f"{v}%")
        self._queue_preview()

    def _queue_preview(self):
        self._preview_timer.start()

    def _prev_page(self):
        if self._doc and self._preview_page > 0:
            self._preview_page -= 1
            self._refresh_preview()

    def _next_page(self):
        if self._doc and self._preview_page < self._total_pages - 1:
            self._preview_page += 1
            self._refresh_preview()

    def _refresh_preview(self):
        if not self._doc:
            return
        text = self._text_entry.text().strip() or " "
        fontsize = float(self._size_slider.value())
        opacity = self._opacity_slider.value() / 100.0
        rgb = COLOR_PRESETS[self._color_combo.currentText()]
        position = self._pos_combo.currentText()

        tmp = fitz.open()
        tmp.insert_pdf(
            self._doc, from_page=self._preview_page, to_page=self._preview_page
        )
        page = tmp[0]
        try:
            _stamp_watermark(page, text, fontsize, rgb, opacity, position)
        except Exception:
            pass
        mat = fitz.Matrix(PREVIEW_SCALE, PREVIEW_SCALE)
        pix = page.get_pixmap(matrix=mat)
        pm = _fitz_pix_to_qpixmap(pix)
        tmp.close()

        self._canvas.set_pixmap(pm)
        self._page_lbl.setText(f"{self._preview_page + 1} / {self._total_pages}")
        self._toolbar_lbl.setText(
            f"Preview — {Path(self._pdf_path).name}" if self._pdf_path else "Preview"
        )

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------

    def _save(self):
        text = self._text_entry.text().strip()
        if not text:
            QMessageBox.warning(self, "No text", "Enter watermark text first.")
            return

        out_name = self._out_entry.text().strip() or "watermarked.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        default_dir = str(Path(self._pdf_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF",
            str(Path(default_dir) / out_name),
            "PDF Files (*.pdf)",
        )
        if not out_path:
            return

        fontsize = float(self._size_slider.value())
        opacity = self._opacity_slider.value() / 100.0
        rgb = COLOR_PRESETS[self._color_combo.currentText()]
        position = self._pos_combo.currentText()

        self._save_btn.setEnabled(False)
        self._status_lbl.setText("Applying watermark...")

        self._worker = _WatermarkWorker(
            self._pdf_path, out_path, text, fontsize, rgb, opacity, position
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
        logger.error("save failed: %s", msg)
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
        self._preview_timer.stop()
        if self._doc:
            try:
                self._doc.close()
            except Exception:
                pass
            self._doc = None
