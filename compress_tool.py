"""Compress Tool – reduce PDF file size with selectable quality presets.

PySide6. Loaded by main.py when the user clicks "Compress".

Presets
-------
Lossless  – garbage-collect, deflate streams/images/fonts. No quality loss.
Screen    – re-render pages at 72 DPI. Smallest file; text becomes raster.
eBook     – re-render at 96 DPI. Good balance for digital reading.
Print     – re-render at 150 DPI. Near-print quality with size savings.
"""

import logging
from pathlib import Path
from base_tool import BaseTool
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
    QProgressBar,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import (
    QDragEnterEvent,
    QDropEvent,
)

from colors import (
    BLUE,
    BLUE_HOVER,
    BLUE_DIM,
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
    TEAL,
    EMERALD,
    BLUE_MED,
)
from icons import svg_pixmap

try:
    import fitz
except ImportError:
    fitz = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Preset definitions
# ---------------------------------------------------------------------------

PRESETS = [
    {
        "id": "lossless",
        "label": "Lossless",
        "desc": "Remove unused data, compress streams.\nNo quality loss.",
        "badge": "Safe",
        "badge_color": EMERALD,
        "dpi": None,
    },
    {
        "id": "print",
        "label": "Print",
        "desc": "Re-render pages at 150 DPI.\nHigh quality, moderate savings.",
        "badge": "150 DPI",
        "badge_color": BLUE,
        "dpi": 150,
    },
    {
        "id": "ebook",
        "label": "eBook",
        "desc": "Re-render pages at 96 DPI.\nGood balance for screen reading.",
        "badge": "96 DPI",
        "badge_color": TEAL,
        "dpi": 96,
    },
    {
        "id": "screen",
        "label": "Screen",
        "desc": "Re-render pages at 72 DPI.\nSmallest file; text becomes raster.",
        "badge": "72 DPI",
        "badge_color": G500,
        "dpi": 72,
    },
]


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024**2:.2f} MB"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ===========================================================================
# Preset Card
# ===========================================================================


class _PresetCard(QFrame):
    """Selectable card representing one compression preset."""

    def __init__(self, preset: dict, parent=None):
        super().__init__(parent)
        self.preset_id = preset["id"]
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(76)
        self._apply_style()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        # Badge
        badge = QLabel(preset["badge"])
        badge.setFixedWidth(60)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: {preset['badge_color']}; color: {WHITE};"
            " border-radius: 4px; font: bold 11px; padding: 2px 0;"
            " border: none;"
        )
        lay.addWidget(badge)

        # Text block
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)

        name_lbl = QLabel(preset["label"])
        name_lbl.setStyleSheet(
            f"color: {G900}; font: bold 13px; background: transparent; border: none;"
        )
        text_col.addWidget(name_lbl)

        desc_lbl = QLabel(preset["desc"])
        desc_lbl.setStyleSheet(
            f"color: {G500}; font: 11px; background: transparent; border: none;"
        )
        text_col.addWidget(desc_lbl)
        lay.addLayout(text_col, 1)

        # Selection indicator
        self._indicator = QLabel()
        self._indicator.setFixedSize(18, 18)
        self._indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._indicator.setStyleSheet(
            f"border: 2px solid {G300}; border-radius: 9px; background: {WHITE};"
        )
        lay.addWidget(self._indicator)

    def _apply_style(self):
        if self._selected:
            self.setStyleSheet(
                f"background: {BLUE_DIM}; border: 2px solid {BLUE}; border-radius: 8px;"
            )
        else:
            self.setStyleSheet(
                f"background: {WHITE}; border: 1px solid {G200}; border-radius: 8px;"
            )

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_style()
        if selected:
            self._indicator.setStyleSheet(
                f"border: 2px solid {BLUE}; border-radius: 9px; background: {BLUE};"
            )
        else:
            self._indicator.setStyleSheet(
                f"border: 2px solid {G300}; border-radius: 9px; background: {WHITE};"
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            tool = self._find_tool()
            if tool:
                tool._select_preset(self.preset_id)

    def _find_tool(self):
        w = self.parent()
        while w:
            if isinstance(w, CompressTool):
                return w
            w = w.parent()
        return None


class _CompressWorker(QThread):
    progress = Signal(int)
    finished = Signal(str)  # out_path
    failed = Signal(str)

    def __init__(self, pdf_path: str, out_path: str, preset: dict):
        super().__init__()
        self._pdf_path = pdf_path
        self._out_path = out_path
        self._preset = preset

    def run(self):
        import worker_semaphore

        worker_semaphore.acquire()
        try:
            assert_file_writable(Path(self._out_path))
            backup_original(Path(self._pdf_path))
            if self._preset["dpi"] is None:
                self._lossless()
            else:
                self._lossy(self._preset["dpi"])
            self.finished.emit(self._out_path)
        except PermissionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            logger.exception("worker failed")
            self.failed.emit(str(exc))
        finally:
            worker_semaphore.release()

    def _lossless(self):
        doc = fitz.open(self._pdf_path)
        try:
            doc.save(
                self._out_path,
                garbage=4,
                deflate=True,
                deflate_images=True,
                deflate_fonts=True,
                clean=True,
                use_objstms=True,
            )
        finally:
            doc.close()
        self.progress.emit(100)

    def _lossy(self, dpi: int):
        src = fitz.open(self._pdf_path)
        out = fitz.open()
        scale = dpi / 72.0
        mat = fitz.Matrix(scale, scale)
        total = src.page_count
        try:
            for i in range(total):
                page = src.load_page(i)
                pix = page.get_pixmap(matrix=mat)
                w_pt = page.rect.width
                h_pt = page.rect.height
                new_page = out.new_page(width=w_pt, height=h_pt)
                new_page.insert_image(new_page.rect, pixmap=pix)
                self.progress.emit(int((i + 1) / total * 90))
            out.save(self._out_path, garbage=4, deflate=True, deflate_images=True)
        finally:
            src.close()
            out.close()
        self.progress.emit(100)


# ===========================================================================
# CompressTool
# ===========================================================================


class CompressTool(BaseTool):
    @property
    def _modified(self):
        return self.__modified

    def __init__(self, parent=None):
        super().__init__(parent)
        self.__modified = False
        self._worker = None

        if fitz is None:
            lay = QVBoxLayout(self)
            lbl = QLabel("Missing dependency.\n\nInstall with:\n  pip install pymupdf")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {G500}; font: 16px;")
            lay.addWidget(lbl)
            return

        self._pdf_path = ""
        self._original_size = 0
        self._preset_id = "lossless"
        self._preset_cards: dict[str, _PresetCard] = {}

        self._build_ui()
        self.setAcceptDrops(True)

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_left_panel())
        root.addWidget(self._build_right_panel(), 1)

    def _build_left_panel(self) -> QWidget:
        left = QWidget()
        left.setFixedWidth(360)
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
        icon_box.setPixmap(svg_pixmap("layers", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)

        title_lbl = QLabel("Compress PDF")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 20px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        # File section
        sec_file = QLabel("SOURCE FILE")
        sec_file.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_file)
        lay.addSpacing(8)

        drop_zone = QFrame()
        drop_zone.setFixedHeight(56)
        drop_zone.setStyleSheet(
            f"background: {G100}; border: 2px dashed {G200}; border-radius: 12px;"
        )
        dz_lay = QHBoxLayout(drop_zone)
        dz_lay.setContentsMargins(10, 0, 10, 0)
        dz_lay.setSpacing(8)

        dz_icon = QLabel()
        dz_icon.setPixmap(svg_pixmap("file-text", G400, 20))
        dz_icon.setStyleSheet("border: none; background: transparent;")
        dz_lay.addWidget(dz_icon)

        dz_lbl = QLabel("Drop PDF here or")
        dz_lbl.setStyleSheet(
            f"color: {G500}; font: 13px; border: none; background: transparent;"
        )
        dz_lay.addWidget(dz_lbl)

        browse_btn = _btn("Browse", BLUE, BLUE_HOVER, h=32, w=80)
        browse_btn.clicked.connect(self._browse_file)
        dz_lay.addWidget(browse_btn)
        dz_lay.addStretch()
        lay.addWidget(drop_zone)
        lay.addSpacing(24)

        # Preset section
        sec_preset = QLabel("COMPRESSION PRESET")
        sec_preset.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_preset)
        lay.addSpacing(8)

        for preset in PRESETS:
            card = _PresetCard(preset, inner)
            self._preset_cards[preset["id"]] = card
            lay.addWidget(card)
            lay.addSpacing(8)

        # Select default
        self._preset_cards["lossless"].set_selected(True)

        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # Bottom action area
        bottom = QWidget()
        bottom.setStyleSheet(f"background: {WHITE}; border-top: 1px solid {G200};")
        bot_lay = QVBoxLayout(bottom)
        bot_lay.setContentsMargins(24, 16, 24, 20)
        bot_lay.setSpacing(10)

        out_lbl = QLabel("OUTPUT FILE")
        out_lbl.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        bot_lay.addWidget(out_lbl)

        self._out_entry = QLineEdit()
        self._out_entry.setPlaceholderText("output_compressed.pdf")
        self._out_entry.setFixedHeight(36)
        self._out_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        bot_lay.addWidget(self._out_entry)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )
        bot_lay.addWidget(self._status_lbl)

        self._progress = QProgressBar()
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setStyleSheet(
            f"QProgressBar {{ background: {G200}; border-radius: 3px; border: none; }}"
            f"QProgressBar::chunk {{ background: {GREEN}; border-radius: 3px; }}"
        )
        self._progress.hide()
        bot_lay.addWidget(self._progress)

        self._compress_btn = _btn("Compress PDF", GREEN, GREEN_HOVER, h=42)
        self._compress_btn.setEnabled(False)
        self._compress_btn.clicked.connect(self._compress)
        bot_lay.addWidget(self._compress_btn)

        outer.addWidget(bottom)
        return left

    def _build_right_panel(self) -> QWidget:
        right = QWidget()
        right.setStyleSheet(f"background: {G100};")
        v = QVBoxLayout(right)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setFixedHeight(48)
        toolbar.setStyleSheet(f"background: {WHITE}; border-bottom: 1px solid {G200};")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(16, 0, 16, 0)
        tb.setSpacing(0)
        self._toolbar_lbl = QLabel("File details")
        self._toolbar_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._toolbar_lbl)
        tb.addStretch()
        v.addWidget(toolbar)

        # Content area
        content = QScrollArea()
        content.setWidgetResizable(True)
        content.setStyleSheet("border: none; background: transparent;")

        self._info_widget = QWidget()
        self._info_widget.setStyleSheet(f"background: {G100};")
        self._info_lay = QVBoxLayout(self._info_widget)
        self._info_lay.setContentsMargins(32, 32, 32, 32)
        self._info_lay.setSpacing(16)
        self._info_lay.addStretch()

        content.setWidget(self._info_widget)
        v.addWidget(content, 1)
        return right

    # -----------------------------------------------------------------------
    # File loading
    # -----------------------------------------------------------------------

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        try:
            doc = fitz.open(path)
            page_count = doc.page_count
            doc.close()
        except Exception as exc:
            logger.exception("could not open pdf")
            QMessageBox.warning(self, "Error", f"Could not open PDF:\n{exc}")
            return

        self._pdf_path = path
        self._original_size = Path(path).stat().st_size
        stem = Path(path).stem
        self._out_entry.setText(f"{stem}_compressed.pdf")
        self._compress_btn.setEnabled(True)
        self._status_lbl.setText("")

        self._toolbar_lbl.setText(Path(path).name)
        self._show_file_info(page_count)

    def _show_file_info(self, page_count: int):
        # Clear info layout
        while self._info_lay.count():
            item = self._info_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        card = QFrame()
        card.setStyleSheet(
            f"background: {WHITE}; border: 1px solid {G200}; border-radius: 12px;"
        )
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(24, 20, 24, 20)
        card_lay.setSpacing(12)

        title = QLabel("Original File")
        title.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1px;"
            " background: transparent; border: none;"
        )
        card_lay.addWidget(title)

        self._add_info_row(card_lay, "File", Path(self._pdf_path).name)
        self._add_info_row(card_lay, "Size", _fmt_size(self._original_size))
        self._add_info_row(card_lay, "Pages", str(page_count))

        self._info_lay.addWidget(card)
        self._result_card_placeholder = QWidget()
        self._info_lay.addWidget(self._result_card_placeholder)
        self._info_lay.addStretch()

    def _add_info_row(self, parent_lay: QVBoxLayout, label: str, value: str):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label)
        lbl.setFixedWidth(60)
        lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        val = QLabel(value)
        val.setStyleSheet(
            f"color: {G900}; font: 13px; background: transparent; border: none;"
        )
        row.addWidget(lbl)
        row.addWidget(val, 1)
        parent_lay.addLayout(row)

    def _show_result(self, compressed_size: int):
        # Replace placeholder with result card
        if hasattr(self, "_result_card_placeholder"):
            self._result_card_placeholder.deleteLater()

        card = QFrame()
        card.setStyleSheet(
            f"background: {WHITE}; border: 1px solid {G200}; border-radius: 12px;"
        )
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(24, 20, 24, 20)
        card_lay.setSpacing(12)

        title = QLabel("Compressed File")
        title.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1px;"
            " background: transparent; border: none;"
        )
        card_lay.addWidget(title)

        self._add_info_row(card_lay, "Size", _fmt_size(compressed_size))

        savings = self._original_size - compressed_size
        pct = (savings / self._original_size * 100) if self._original_size else 0

        if savings > 0:
            savings_lbl = QLabel(f"Saved {_fmt_size(savings)} ({pct:.1f}% smaller)")
            savings_lbl.setStyleSheet(
                f"color: {EMERALD}; font: bold 13px;"
                " background: transparent; border: none;"
            )
        else:
            savings_lbl = QLabel("File is already well-compressed.")
            savings_lbl.setStyleSheet(
                f"color: {G500}; font: 13px; background: transparent; border: none;"
            )
        card_lay.addWidget(savings_lbl)

        # Visual bar
        bar_bg = QFrame()
        bar_bg.setFixedHeight(8)
        bar_bg.setStyleSheet(f"background: {G200}; border-radius: 4px; border: none;")
        bar_outer = QVBoxLayout(bar_bg)
        bar_outer.setContentsMargins(0, 0, 0, 0)

        fill_w_pct = max(0, min(100, 100 - pct))
        bar_fill = QFrame(bar_bg)
        bar_fill.setFixedHeight(8)
        bar_fill.setStyleSheet(
            f"background: {EMERALD if savings > 0 else G400}; border-radius: 4px; border: none;"
        )
        bar_fill.setMaximumWidth(int(fill_w_pct))
        bar_fill.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bar_outer.addWidget(bar_fill)

        card_lay.addWidget(bar_bg)

        idx = self._info_lay.count() - 1  # before stretch
        self._info_lay.insertWidget(idx, card)

    # -----------------------------------------------------------------------
    # Preset selection
    # -----------------------------------------------------------------------

    def _select_preset(self, preset_id: str):
        self._preset_id = preset_id
        for pid, card in self._preset_cards.items():
            card.set_selected(pid == preset_id)

    # -----------------------------------------------------------------------
    # Compression
    # -----------------------------------------------------------------------

    def _compress(self):
        if not self._pdf_path:
            return

        out_name = self._out_entry.text().strip() or "compressed.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        default_dir = str(Path(self._pdf_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Compressed PDF",
            str(Path(default_dir) / out_name),
            "PDF Files (*.pdf)",
        )
        if not out_path:
            return

        self._progress.setValue(0)
        self._progress.show()
        self._compress_btn.setEnabled(False)
        self._status_lbl.setText("Compressing...")

        preset = next(p for p in PRESETS if p["id"] == self._preset_id)
        self._worker = _CompressWorker(self._pdf_path, out_path, preset)
        self._worker.progress.connect(self._progress.setValue)
        self._worker.finished.connect(self._on_compress_done)
        self._worker.failed.connect(self._on_compress_failed)
        self._worker.start()

    def _on_compress_done(self, out_path: str):
        compressed_size = Path(out_path).stat().st_size
        savings = self._original_size - compressed_size
        pct = (savings / self._original_size * 100) if self._original_size else 0

        if savings > 0:
            self._status_lbl.setText(f"Saved {_fmt_size(savings)} ({pct:.1f}% smaller)")
            self._status_lbl.setStyleSheet(
                f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
            )
        else:
            self._status_lbl.setText("File is already well-compressed.")
            self._status_lbl.setStyleSheet(
                f"color: {G500}; font: 12px; border: none; background: transparent;"
            )

        self._show_result(compressed_size)
        self._compress_btn.setEnabled(True)
        self._progress.hide()

    def _on_compress_failed(self, msg: str):
        QMessageBox.critical(self, "Compression failed", msg)
        self._status_lbl.setText("Compression failed.")
        self._status_lbl.setStyleSheet(
            "color: red; font: 12px; border: none; background: transparent;"
        )
        self._compress_btn.setEnabled(True)
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
            if path.lower().endswith(".pdf"):
                self._load_file(path)
                break

    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------

    def cleanup(self):
        pass
