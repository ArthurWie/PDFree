"""PDF to Image Tool – export PDF pages as PNG or JPEG files.

PySide6. Loaded by main.py when the user clicks "PDF to Image".
"""

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QLineEdit,
    QScrollArea,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QFileDialog,
    QMessageBox,
    QProgressBar,
    QComboBox,
    QSlider,
)
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPixmap,
    QFont,
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
    EMERALD,
    BLUE_MED,)
from icons import svg_pixmap
from utils import _fitz_pix_to_qpixmap, assert_file_writable

try:
    import fitz
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)

DPI_OPTIONS = ["72", "96", "150", "200", "300"]


class _ExportImagesWorker(QThread):
    finished = Signal(str, int)   # out_dir, count
    failed = Signal(str)
    progress = Signal(int)

    def __init__(self, pdf_path, out_dir, pages, dpi, fmt, quality, stem, parent=None):
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._out_dir = out_dir
        self._pages = pages
        self._dpi = dpi
        self._fmt = fmt
        self._quality = quality
        self._stem = stem

    def run(self):
        try:
            Path(self._out_dir).mkdir(parents=True, exist_ok=True)
            assert_file_writable(Path(self._out_dir) / "_probe")
            mat = fitz.Matrix(self._dpi / 72, self._dpi / 72)
            total = len(self._pages)
            exported = 0
            for i, page_idx in enumerate(self._pages):
                doc = fitz.open(self._pdf_path)
                page = doc.load_page(page_idx)
                pix = page.get_pixmap(matrix=mat)
                ext = "jpg" if self._fmt == "jpeg" else "png"
                out_path = str(
                    Path(self._out_dir) / f"{self._stem}_page{page_idx + 1:04d}.{ext}"
                )
                if self._fmt == "jpeg":
                    pix.save(out_path, jpg_quality=self._quality)
                else:
                    pix.save(out_path)
                doc.close()
                exported += 1
                self.progress.emit(int((i + 1) / total * 100))
            self.finished.emit(self._out_dir, exported)
        except PermissionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))
FORMAT_OPTIONS = ["PNG", "JPEG"]
THUMB_SCALE = 0.2
GRID_COLS = 4
THUMB_W = 110
THUMB_H = 140


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
# Page Cell (identical role to remove_tool/_PageCell but for selection only)
# ===========================================================================


class _PageCell(QFrame):
    def __init__(self, page_idx: int, parent=None):
        super().__init__(parent)
        self.page_idx = page_idx
        self._pixmap: QPixmap | None = None
        self._selected = True  # default: all selected for export
        self.setFixedSize(THUMB_W, THUMB_H + 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()

    def _apply_style(self):
        if self._selected:
            self.setStyleSheet(
                f"background: {BLUE_DIM}; border: 2px solid {BLUE}; border-radius: 6px;"
            )
        else:
            self.setStyleSheet(
                f"background: {WHITE}; border: 1px solid {G200}; border-radius: 6px;"
            )

    def set_selected(self, v: bool):
        self._selected = v
        self._apply_style()
        self.update()

    def set_pixmap(self, pm: QPixmap):
        self._pixmap = pm
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                THUMB_W - 8, THUMB_H - 8,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (THUMB_W - scaled.width()) // 2
            y = (THUMB_H - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
        else:
            p.setPen(QColor(G400))
            p.drawText(0, 0, THUMB_W, THUMB_H, Qt.AlignmentFlag.AlignCenter, "...")

        # Dim unselected pages
        if not self._selected:
            p.fillRect(0, 0, THUMB_W, THUMB_H, QColor(255, 255, 255, 140))

        color = BLUE if self._selected else G400
        p.setPen(QColor(color))
        f = QFont()
        f.setPointSize(8)
        p.setFont(f)
        p.drawText(0, THUMB_H, THUMB_W, 22, Qt.AlignmentFlag.AlignCenter,
                   str(self.page_idx + 1))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            tool = self._find_tool()
            if tool:
                tool._toggle_page(self.page_idx)

    def _find_tool(self):
        w = self.parent()
        while w:
            if isinstance(w, PDFToImgTool):
                return w
            w = w.parent()
        return None


# ===========================================================================
# PDFToImgTool
# ===========================================================================


class PDFToImgTool(QWidget):
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
        self._selected: set[int] = set()
        self._cells: list[_PageCell] = []
        self._worker = None
        self._thumb_timer = QTimer(self)
        self._thumb_timer.setSingleShot(True)
        self._thumb_timer.timeout.connect(self._render_thumbs_deferred)
        self._thumb_queue: list[int] = []

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
        left.setFixedWidth(300)
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
        title_lbl = QLabel("PDF to Image")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 20px; background: transparent; border: none;"
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
            f"background: {G100};"
            f" border: 2px dashed {G200}; border-radius: 12px;"
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

        # Format
        lay.addWidget(_section("FORMAT"))
        lay.addSpacing(8)
        self._fmt_combo = _combo(FORMAT_OPTIONS)
        self._fmt_combo.currentTextChanged.connect(self._on_format_change)
        lay.addWidget(self._fmt_combo)
        lay.addSpacing(16)

        # DPI
        lay.addWidget(_section("RESOLUTION"))
        lay.addSpacing(8)
        self._dpi_combo = _combo(DPI_OPTIONS)
        self._dpi_combo.setCurrentText("150")
        lay.addWidget(self._dpi_combo)
        lay.addSpacing(16)

        # JPEG quality
        self._quality_section = _section("JPEG QUALITY")
        lay.addWidget(self._quality_section)
        lay.addSpacing(8)

        quality_row = QHBoxLayout()
        quality_row.setContentsMargins(0, 0, 0, 0)
        quality_row.setSpacing(10)
        self._quality_slider = QSlider(Qt.Orientation.Horizontal)
        self._quality_slider.setRange(20, 100)
        self._quality_slider.setValue(85)
        self._quality_slider.setStyleSheet(
            f"QSlider::groove:horizontal {{ height: 4px; background: {G200}; border-radius: 2px; }}"
            f"QSlider::handle:horizontal {{ width: 16px; height: 16px; margin: -6px 0;"
            f" background: {BLUE}; border-radius: 8px; }}"
            f"QSlider::sub-page:horizontal {{ background: {BLUE}; border-radius: 2px; }}"
        )
        self._quality_slider.valueChanged.connect(self._on_quality_change)
        quality_row.addWidget(self._quality_slider, 1)
        self._quality_lbl = QLabel("85")
        self._quality_lbl.setFixedWidth(28)
        self._quality_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        quality_row.addWidget(self._quality_lbl)
        lay.addLayout(quality_row)
        lay.addSpacing(16)

        # Page selection
        lay.addWidget(_section("PAGES"))
        lay.addSpacing(8)
        sel_row = QHBoxLayout()
        sel_row.setSpacing(8)
        self._sel_all_btn = _btn("All", G100, G200, G700, border=True, h=30, w=60)
        self._sel_all_btn.setEnabled(False)
        self._sel_all_btn.clicked.connect(self._select_all)
        sel_row.addWidget(self._sel_all_btn)
        self._desel_btn = _btn("None", G100, G200, G700, border=True, h=30, w=60)
        self._desel_btn.setEnabled(False)
        self._desel_btn.clicked.connect(self._deselect_all)
        sel_row.addWidget(self._desel_btn)
        sel_row.addStretch()
        lay.addLayout(sel_row)
        lay.addSpacing(6)
        self._sel_lbl = QLabel("")
        self._sel_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        lay.addWidget(self._sel_lbl)

        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # Bottom
        bottom = QWidget()
        bottom.setStyleSheet(f"background: {WHITE}; border-top: 1px solid {G200};")
        bot = QVBoxLayout(bottom)
        bot.setContentsMargins(24, 16, 24, 20)
        bot.setSpacing(10)

        bot.addWidget(_section("OUTPUT FOLDER"))
        out_row = QHBoxLayout()
        out_row.setSpacing(6)
        self._out_entry = QLineEdit()
        self._out_entry.setPlaceholderText("Same as PDF")
        self._out_entry.setFixedHeight(36)
        self._out_entry.setReadOnly(True)
        self._out_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
            f" font: 12px; color: {G700}; background: {G100};"
        )
        out_row.addWidget(self._out_entry, 1)
        folder_btn = _btn("…", G100, G200, G700, border=True, h=36, w=36)
        folder_btn.clicked.connect(self._browse_folder)
        out_row.addWidget(folder_btn)
        bot.addLayout(out_row)

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

        self._export_btn = _btn("Export Images", GREEN, GREEN_HOVER, h=42)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export)
        bot.addWidget(self._export_btn)

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
        tb.setSpacing(12)
        self._page_count_lbl = QLabel("Load a PDF to begin")
        self._page_count_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._page_count_lbl)
        tb.addStretch()
        hint = QLabel("Click pages to toggle export")
        hint.setStyleSheet(
            f"color: {G400}; font: 12px; background: transparent; border: none;"
        )
        tb.addWidget(hint)
        v.addWidget(toolbar)

        self._grid_scroll = QScrollArea()
        self._grid_scroll.setWidgetResizable(True)
        self._grid_scroll.setStyleSheet("border: none; background: transparent;")
        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet(f"background: {G100};")
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setContentsMargins(20, 20, 20, 20)
        self._grid_layout.setSpacing(12)
        self._grid_scroll.setWidget(self._grid_widget)
        v.addWidget(self._grid_scroll, 1)
        return right

    # -----------------------------------------------------------------------
    # File loading
    # -----------------------------------------------------------------------

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if path:
            self._load_file(path)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self._out_entry.setText(folder)

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
        self._selected = set(range(self._total_pages))
        self._cells.clear()

        self._file_lbl.setText(Path(path).name)
        self._page_count_lbl.setText(f"{self._total_pages} pages")
        self._sel_all_btn.setEnabled(True)
        self._desel_btn.setEnabled(True)
        self._update_sel_label()
        self._export_btn.setEnabled(True)
        self._build_grid()

    def _build_grid(self):
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cells.clear()

        for i in range(self._total_pages):
            cell = _PageCell(i, self._grid_widget)
            cell.set_selected(i in self._selected)
            row, col = divmod(i, GRID_COLS)
            self._grid_layout.addWidget(cell, row, col)
            self._cells.append(cell)

        self._thumb_queue = list(range(self._total_pages))
        self._thumb_timer.start(0)

    def _render_thumbs_deferred(self):
        if not self._thumb_queue or not self._doc:
            return
        batch = self._thumb_queue[:8]
        self._thumb_queue = self._thumb_queue[8:]
        for i in batch:
            if i < len(self._cells):
                try:
                    page = self._doc.load_page(i)
                    mat = fitz.Matrix(THUMB_SCALE, THUMB_SCALE)
                    pix = page.get_pixmap(matrix=mat)
                    pm = _fitz_pix_to_qpixmap(pix)
                    self._cells[i].set_pixmap(pm)
                except Exception:
                    pass
        if self._thumb_queue:
            self._thumb_timer.start(0)

    # -----------------------------------------------------------------------
    # Selection
    # -----------------------------------------------------------------------

    def _toggle_page(self, idx: int):
        if idx in self._selected:
            self._selected.discard(idx)
        else:
            self._selected.add(idx)
        if idx < len(self._cells):
            self._cells[idx].set_selected(idx in self._selected)
        self._update_sel_label()
        self._export_btn.setEnabled(len(self._selected) > 0)

    def _select_all(self):
        self._selected = set(range(self._total_pages))
        for cell in self._cells:
            cell.set_selected(True)
        self._update_sel_label()
        self._export_btn.setEnabled(True)

    def _deselect_all(self):
        self._selected.clear()
        for cell in self._cells:
            cell.set_selected(False)
        self._update_sel_label()
        self._export_btn.setEnabled(False)

    def _update_sel_label(self):
        n = len(self._selected)
        self._sel_lbl.setText(
            f"{n} of {self._total_pages} pages selected" if self._total_pages else ""
        )

    # -----------------------------------------------------------------------
    # Format / quality
    # -----------------------------------------------------------------------

    def _on_format_change(self, fmt: str):
        is_jpeg = fmt == "JPEG"
        self._quality_section.setVisible(is_jpeg)
        self._quality_slider.setVisible(is_jpeg)
        self._quality_lbl.setVisible(is_jpeg)

    def _on_quality_change(self, v: int):
        self._quality_lbl.setText(str(v))

    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------

    def _export(self):
        if not self._selected:
            return

        out_dir = self._out_entry.text().strip()
        if not out_dir:
            out_dir = str(Path(self._pdf_path).parent)

        dpi = int(self._dpi_combo.currentText())
        fmt = self._fmt_combo.currentText().lower()
        quality = self._quality_slider.value()
        stem = Path(self._pdf_path).stem
        pages = sorted(self._selected)

        self._progress.setValue(0)
        self._progress.show()
        self._export_btn.setEnabled(False)
        self._status_lbl.setText("Exporting...")

        self._worker = _ExportImagesWorker(
            self._pdf_path, out_dir, pages, dpi, fmt, quality, stem
        )
        self._worker.progress.connect(self._progress.setValue)
        self._worker.finished.connect(self._on_export_done)
        self._worker.failed.connect(self._on_export_failed)
        self._worker.start()

    def _on_export_done(self, out_dir: str, count: int):
        self._status_lbl.setText(
            f"Exported {count} image{'s' if count != 1 else ''} → {out_dir}"
        )
        self._status_lbl.setStyleSheet(
            f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
        )
        self._export_btn.setEnabled(len(self._selected) > 0)
        self._progress.hide()

    def _on_export_failed(self, msg: str):
        logger.error("export failed: %s", msg)
        QMessageBox.critical(self, "Export failed", msg)
        self._status_lbl.setText("Export failed.")
        self._export_btn.setEnabled(len(self._selected) > 0)
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

    def cleanup(self):
        self._thumb_timer.stop()
        if self._doc:
            try:
                self._doc.close()
            except Exception:
                pass
            self._doc = None
