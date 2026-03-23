"""Headers & Footers Tool – stamp custom text in header and footer zones on every page.

PySide6. Loaded by main.py when the user clicks "Headers & Footers".
"""

import datetime
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
    QSpinBox,
)
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPixmap,
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

PREVIEW_SCALE = 1.2


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


def _spinbox(min_v: int, max_v: int, val: int, suffix: str = "") -> QSpinBox:
    s = QSpinBox()
    s.setRange(min_v, max_v)
    s.setValue(val)
    s.setFixedHeight(36)
    if suffix:
        s.setSuffix(suffix)
    s.setStyleSheet(
        f"border: 1px solid {G200}; border-radius: 6px; padding: 0 8px;"
        f" font: 13px; color: {G900}; background: {WHITE};"
    )
    return s


def _text_input() -> QLineEdit:
    e = QLineEdit()
    e.setFixedHeight(32)
    e.setStyleSheet(
        f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
        f" font: 13px; color: {G900}; background: {WHITE}; height: 32px;"
    )
    return e


def _resolve(template: str, page_num: int, total: int, filename: str) -> str:
    return (
        template.replace("{page}", str(page_num))
        .replace("{total}", str(total))
        .replace("{date}", datetime.date.today().strftime("%Y-%m-%d"))
        .replace("{filename}", filename)
    )


def _apply_zones(
    page,
    header_inputs: dict,
    footer_inputs: dict,
    page_num: int,
    total: int,
    filename: str,
    font_size: float,
    margin: int,
):
    w = page.rect.width
    h = page.rect.height

    header_zones = {
        "left": fitz.Rect(margin, margin, w / 3, margin + font_size + 4),
        "center": fitz.Rect(w / 3, margin, 2 * w / 3, margin + font_size + 4),
        "right": fitz.Rect(2 * w / 3, margin, w - margin, margin + font_size + 4),
    }
    footer_zones = {
        "left": fitz.Rect(margin, h - margin - font_size - 4, w / 3, h - margin),
        "center": fitz.Rect(w / 3, h - margin - font_size - 4, 2 * w / 3, h - margin),
        "right": fitz.Rect(
            2 * w / 3, h - margin - font_size - 4, w - margin, h - margin
        ),
    }
    align_map = {
        "left": fitz.TEXT_ALIGN_LEFT,
        "center": fitz.TEXT_ALIGN_CENTER,
        "right": fitz.TEXT_ALIGN_RIGHT,
    }

    for zone_name, rect in {**header_zones, **footer_zones}.items():
        if zone_name in header_zones:
            text_template = header_inputs[zone_name]
        else:
            text_template = footer_inputs[zone_name]

        text = _resolve(text_template, page_num, total, filename)
        if not text:
            continue

        page.insert_textbox(
            rect,
            text,
            fontsize=font_size,
            align=align_map[zone_name],
            color=(0, 0, 0),
        )


# ===========================================================================
# Preview Canvas
# ===========================================================================


class _PreviewCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_pixmap(self, pm: QPixmap | None):
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
                "Load a PDF to see\nthe header/footer preview",
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


# ===========================================================================
# HeadersFootersTool
# ===========================================================================


class _HeadersFootersWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        pdf_path,
        out_path,
        total_pages,
        skip,
        font_size,
        margin,
        filename,
        header_inputs,
        footer_inputs,
    ):
        super().__init__()
        self._pdf_path = pdf_path
        self._out_path = out_path
        self._total_pages = total_pages
        self._skip = skip
        self._font_size = font_size
        self._margin = margin
        self._filename = filename
        self._header_inputs = header_inputs
        self._footer_inputs = footer_inputs

    def run(self):
        try:
            assert_file_writable(Path(self._out_path))
            backup_original(Path(self._pdf_path))
            doc = fitz.open(self._pdf_path)
            for i in range(self._total_pages):
                if i < self._skip:
                    continue
                page = doc[i]
                page_num = i + 1
                _apply_zones(
                    page,
                    self._header_inputs,
                    self._footer_inputs,
                    page_num,
                    self._total_pages,
                    self._filename,
                    self._font_size,
                    self._margin,
                )
            doc.save(self._out_path, garbage=3, deflate=True)
            doc.close()
            self.finished.emit(self._out_path)
        except PermissionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            logger.exception("worker failed")
            self.failed.emit(str(exc))


class HeadersFootersTool(QWidget):
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
        self._preview_timer.setInterval(300)
        self._preview_timer.timeout.connect(self._refresh_preview)

        self._build_ui()
        self.setAcceptDrops(True)

    # -----------------------------------------------------------------------
    # UI
    # -----------------------------------------------------------------------

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_left_panel())
        root.addWidget(self._build_right_panel(), 1)

    def _build_left_panel(self) -> QWidget:
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
        icon_box.setPixmap(svg_pixmap("pen-line", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)
        title_lbl = QLabel("Headers & Footers")
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

        # Header section
        lay.addWidget(_section("HEADER"))
        lay.addSpacing(8)
        self._header_left = self._zone_row(lay, "Left")
        self._header_center = self._zone_row(lay, "Center")
        self._header_right = self._zone_row(lay, "Right")
        lay.addSpacing(16)

        # Footer section
        lay.addWidget(_section("FOOTER"))
        lay.addSpacing(8)
        self._footer_left = self._zone_row(lay, "Left")
        self._footer_center = self._zone_row(lay, "Center")
        self._footer_right = self._zone_row(lay, "Right")
        lay.addSpacing(8)

        # Variables hint
        hint = QLabel("{page} · {total} · {date} · {filename}")
        hint.setStyleSheet(
            f"color: {G400}; font: 11px; background: transparent; border: none;"
        )
        lay.addWidget(hint)
        lay.addSpacing(16)

        # Appearance
        lay.addWidget(_section("APPEARANCE"))
        lay.addSpacing(8)

        appear_row = QHBoxLayout()
        appear_row.setSpacing(12)
        appear_row.setContentsMargins(0, 0, 0, 0)

        fs_col = QVBoxLayout()
        fs_col.setSpacing(4)
        fs_col.setContentsMargins(0, 0, 0, 0)
        fs_lbl = QLabel("Font size")
        fs_lbl.setStyleSheet(
            f"color: {G700}; font: 12px; background: transparent; border: none;"
        )
        fs_col.addWidget(fs_lbl)
        self._font_spin = _spinbox(6, 36, 10)
        self._font_spin.valueChanged.connect(self._queue_preview)
        fs_col.addWidget(self._font_spin)
        appear_row.addLayout(fs_col)

        mg_col = QVBoxLayout()
        mg_col.setSpacing(4)
        mg_col.setContentsMargins(0, 0, 0, 0)
        mg_lbl = QLabel("Margin")
        mg_lbl.setStyleSheet(
            f"color: {G700}; font: 12px; background: transparent; border: none;"
        )
        mg_col.addWidget(mg_lbl)
        self._margin_spin = _spinbox(4, 80, 20, suffix=" pt")
        self._margin_spin.valueChanged.connect(self._queue_preview)
        mg_col.addWidget(self._margin_spin)
        appear_row.addLayout(mg_col)

        lay.addLayout(appear_row)
        lay.addSpacing(16)

        # Skip pages
        lay.addWidget(_section("SKIP PAGES"))
        lay.addSpacing(8)

        skip_row = QHBoxLayout()
        skip_row.setSpacing(8)
        skip_row.setContentsMargins(0, 0, 0, 0)
        skip_lbl = QLabel("Skip first N pages")
        skip_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        skip_row.addWidget(skip_lbl)
        self._skip_spin = _spinbox(0, 100, 0)
        self._skip_spin.setFixedWidth(80)
        self._skip_spin.valueChanged.connect(self._queue_preview)
        skip_row.addWidget(self._skip_spin)
        skip_row.addStretch()
        lay.addLayout(skip_row)

        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # Bottom action bar
        bottom = QWidget()
        bottom.setStyleSheet(f"background: {WHITE}; border-top: 1px solid {G200};")
        bot = QVBoxLayout(bottom)
        bot.setContentsMargins(24, 16, 24, 20)
        bot.setSpacing(10)

        bot.addWidget(_section("OUTPUT FILE"))
        self._out_entry = QLineEdit()
        self._out_entry.setPlaceholderText("output_hf.pdf")
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

        self._save_btn = _btn("Apply Headers & Footers", GREEN, GREEN_HOVER, h=42)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save)
        bot.addWidget(self._save_btn)

        outer.addWidget(bottom)
        return left

    def _zone_row(self, parent_lay: QVBoxLayout, label: str) -> QLineEdit:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.setContentsMargins(0, 0, 0, 4)
        lbl = QLabel(label)
        lbl.setFixedWidth(50)
        lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        row.addWidget(lbl)
        field = _text_input()
        field.textChanged.connect(self._queue_preview)
        row.addWidget(field, 1)
        parent_lay.addLayout(row)
        return field

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
        tb.setSpacing(12)
        self._toolbar_lbl = QLabel("Preview")
        self._toolbar_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._toolbar_lbl)
        tb.addStretch()

        prev_btn = QPushButton()
        prev_btn.setFixedSize(32, 32)
        prev_btn.setIcon(svg_pixmap("chevron-left", G700, 16))
        prev_btn.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; background: {WHITE};"
        )
        prev_btn.clicked.connect(self._prev_page)
        tb.addWidget(prev_btn)

        self._page_lbl = QLabel("")
        self._page_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        tb.addWidget(self._page_lbl)

        next_btn = QPushButton()
        next_btn.setFixedSize(32, 32)
        next_btn.setIcon(svg_pixmap("chevron-right", G700, 16))
        next_btn.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; background: {WHITE};"
        )
        next_btn.clicked.connect(self._next_page)
        tb.addWidget(next_btn)

        refresh_btn = QPushButton()
        refresh_btn.setFixedSize(32, 32)
        refresh_btn.setIcon(svg_pixmap("refresh-cw", G700, 16))
        refresh_btn.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; background: {WHITE};"
        )
        refresh_btn.clicked.connect(self._refresh_preview)
        tb.addWidget(refresh_btn)

        v.addWidget(toolbar)

        self._canvas = _PreviewCanvas()
        v.addWidget(self._canvas, 1)
        return right

    # -----------------------------------------------------------------------
    # File loading
    # -----------------------------------------------------------------------

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
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
        self._out_entry.setText(f"{Path(path).stem}_hf.pdf")
        self._save_btn.setEnabled(True)
        self._refresh_preview()

    # -----------------------------------------------------------------------
    # Preview
    # -----------------------------------------------------------------------

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

    def _gather_inputs(self) -> tuple[dict, dict]:
        header_inputs = {
            "left": self._header_left.text(),
            "center": self._header_center.text(),
            "right": self._header_right.text(),
        }
        footer_inputs = {
            "left": self._footer_left.text(),
            "center": self._footer_center.text(),
            "right": self._footer_right.text(),
        }
        return header_inputs, footer_inputs

    def _refresh_preview(self):
        if not self._doc:
            return

        page_idx = self._preview_page
        skip = self._skip_spin.value()
        font_size = float(self._font_spin.value())
        margin = self._margin_spin.value()
        total = self._total_pages
        filename = Path(self._pdf_path).name if self._pdf_path else ""
        header_inputs, footer_inputs = self._gather_inputs()

        tmp_doc = fitz.open()
        tmp_doc.insert_pdf(self._doc, from_page=page_idx, to_page=page_idx)
        page = tmp_doc[0]

        if page_idx >= skip:
            page_num = page_idx + 1
            _apply_zones(
                page,
                header_inputs,
                footer_inputs,
                page_num,
                total,
                filename,
                font_size,
                margin,
            )

        mat = fitz.Matrix(PREVIEW_SCALE, PREVIEW_SCALE)
        pix = page.get_pixmap(matrix=mat)
        pm = _fitz_pix_to_qpixmap(pix)
        tmp_doc.close()

        self._canvas.set_pixmap(pm)
        self._page_lbl.setText(f"{page_idx + 1} / {self._total_pages}")
        self._toolbar_lbl.setText(
            f"Preview — {Path(self._pdf_path).name}" if self._pdf_path else "Preview"
        )

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------

    def _save(self):
        out_name = self._out_entry.text().strip() or "output_hf.pdf"
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

        skip = self._skip_spin.value()
        font_size = float(self._font_spin.value())
        margin = self._margin_spin.value()
        total = self._total_pages
        filename = Path(self._pdf_path).name
        header_inputs, footer_inputs = self._gather_inputs()

        self._save_btn.setEnabled(False)
        self._status_lbl.setText("Saving...")

        self._worker = _HeadersFootersWorker(
            self._pdf_path,
            out_path,
            total,
            skip,
            font_size,
            margin,
            filename,
            header_inputs,
            footer_inputs,
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
        self._preview_timer.stop()
        if self._doc:
            try:
                self._doc.close()
            except Exception:
                pass
            self._doc = None
