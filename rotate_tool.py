"""Rotate Tool – rotate individual or all pages of a PDF.

PySide6. Loaded by main.py when the user clicks "Rotate".
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
    QGridLayout,
    QFileDialog,
    QMessageBox,
    QProgressBar,
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
    EMERALD,
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
    BLUE_MED,)
from icons import svg_pixmap, svg_icon
from utils import _fitz_pix_to_qpixmap

try:
    import fitz
except ImportError:
    fitz = None

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    PdfReader = PdfWriter = None

logger = logging.getLogger(__name__)

THUMB_W = 110


class _RotateWorker(QThread):
    finished = Signal(str, int)   # out_path, rotated_count
    failed = Signal(str)
    progress = Signal(int)

    def __init__(self, pdf_path, out_path, rotations, total_pages, parent=None):
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._out_path = out_path
        self._rotations = rotations
        self._total_pages = total_pages

    def run(self):
        try:
            assert_file_writable(Path(self._out_path))
            backup_original(Path(self._pdf_path))
            reader = PdfReader(self._pdf_path)
            writer = PdfWriter()
            for i, page in enumerate(reader.pages):
                extra = self._rotations.get(i, 0)
                if extra % 360 != 0:
                    page.rotate(extra)
                writer.add_page(page)
                self.progress.emit(int((i + 1) / self._total_pages * 90))
            with open(self._out_path, "wb") as f:
                writer.write(f)
            self.progress.emit(100)
            rotated_count = sum(1 for v in self._rotations.values() if v % 360 != 0)
            self.finished.emit(self._out_path, rotated_count)
        except PermissionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))
THUMB_H = 140
GRID_COLS = 4
THUMB_SCALE = 0.25


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


def _icon_btn(icon_name: str, tooltip: str, size: int = 36) -> QPushButton:
    b = QPushButton()
    b.setFixedSize(size, size)
    b.setIcon(svg_icon(icon_name, G700, 18))
    b.setToolTip(tooltip)
    b.setStyleSheet(f"""
        QPushButton {{
            background: {WHITE}; border: 1px solid {G200}; border-radius: 6px;
        }}
        QPushButton:hover {{ background: {G100}; border-color: {G300}; }}
        QPushButton:disabled {{ background: {G100}; border-color: {G200}; }}
    """)
    return b


# ===========================================================================
# Page Thumbnail Cell
# ===========================================================================


class _PageCell(QFrame):
    """Thumbnail cell showing the page at its current rotation with selection state."""

    def __init__(self, page_idx: int, parent=None):
        super().__init__(parent)
        self.page_idx = page_idx
        self._pixmap: QPixmap | None = None
        self._selected = False
        self._rotation = 0  # cumulative extra rotation in degrees (0/90/180/270)
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

    def set_selected(self, selected: bool):
        self._selected = selected
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

        # Page number + rotation badge
        rot = self._rotation % 360
        rot_str = f"  {rot}°" if rot != 0 else ""
        label = f"{self.page_idx + 1}{rot_str}"
        color = BLUE if self._selected else G500
        p.setPen(QColor(color))
        f = QFont()
        f.setPointSize(8)
        if rot != 0:
            f.setBold(True)
        p.setFont(f)
        p.drawText(0, THUMB_H, THUMB_W, 22, Qt.AlignmentFlag.AlignCenter, label)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            tool = self._find_tool()
            if tool:
                tool._toggle_select(self.page_idx)

    def _find_tool(self):
        w = self.parent()
        while w:
            if isinstance(w, RotateTool):
                return w
            w = w.parent()
        return None


# ===========================================================================
# RotateTool
# ===========================================================================


class RotateTool(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._modified = False

        if fitz is None or PdfReader is None:
            lay = QVBoxLayout(self)
            lbl = QLabel(
                "Missing dependencies.\n\n"
                "Install with:\n"
                "  pip install pymupdf pypdf"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {G500}; font: 16px;")
            lay.addWidget(lbl)
            return

        self._pdf_path = ""
        self._doc = None
        self._total_pages = 0
        self._selected: set[int] = set()
        self._rotations: dict[int, int] = {}
        self._cells: list[_PageCell] = []
        self._worker = None
        self._thumb_timer = QTimer(self)
        self._thumb_timer.setSingleShot(True)
        self._thumb_timer.timeout.connect(self._render_thumbs_deferred)
        self._thumb_queue: list[int] = []

        self._build_ui()
        self.setAcceptDrops(True)

    # -----------------------------------------------------------------------
    # UI construction
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
        icon_box.setPixmap(svg_pixmap("rotate-cw", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)

        title_lbl = QLabel("Rotate Pages")
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
            f"background: {G100};"
            f" border: 2px dashed {G200}; border-radius: 12px;"
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
        lay.addSpacing(10)

        self._file_lbl = QLabel("No file loaded")
        self._file_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        self._file_lbl.setWordWrap(True)
        lay.addWidget(self._file_lbl)
        lay.addSpacing(24)

        # Rotate selected section
        sec_rot = QLabel("ROTATE SELECTED")
        sec_rot.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_rot)
        lay.addSpacing(10)

        rot_row = QHBoxLayout()
        rot_row.setSpacing(8)
        rot_row.setContentsMargins(0, 0, 0, 0)

        self._ccw_btn = _icon_btn("rotate-ccw", "Rotate 90° counter-clockwise", 44)
        self._ccw_btn.setEnabled(False)
        self._ccw_btn.clicked.connect(lambda: self._rotate_selected(-90))
        rot_row.addWidget(self._ccw_btn)

        self._cw_btn = _icon_btn("rotate-cw", "Rotate 90° clockwise", 44)
        self._cw_btn.setEnabled(False)
        self._cw_btn.clicked.connect(lambda: self._rotate_selected(90))
        rot_row.addWidget(self._cw_btn)

        self._r180_btn = _btn("180°", G100, G200, G700, border=True, h=44, w=60)
        self._r180_btn.setEnabled(False)
        self._r180_btn.clicked.connect(lambda: self._rotate_selected(180))
        rot_row.addWidget(self._r180_btn)

        rot_row.addStretch()
        lay.addLayout(rot_row)
        lay.addSpacing(8)

        self._sel_lbl = QLabel("No pages selected")
        self._sel_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        lay.addWidget(self._sel_lbl)
        lay.addSpacing(20)

        # Quick selection
        sec_sel = QLabel("SELECTION")
        sec_sel.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_sel)
        lay.addSpacing(8)

        sel_row = QHBoxLayout()
        sel_row.setSpacing(8)

        self._sel_all_btn = _btn("Select All", G100, G200, G700, border=True, h=32)
        self._sel_all_btn.setEnabled(False)
        self._sel_all_btn.clicked.connect(self._select_all)
        sel_row.addWidget(self._sel_all_btn)

        self._desel_btn = _btn("Deselect All", G100, G200, G700, border=True, h=32)
        self._desel_btn.setEnabled(False)
        self._desel_btn.clicked.connect(self._deselect_all)
        sel_row.addWidget(self._desel_btn)
        lay.addLayout(sel_row)
        lay.addSpacing(20)

        # Rotate all shortcut
        sec_all = QLabel("ROTATE ALL PAGES")
        sec_all.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_all)
        lay.addSpacing(10)

        all_row = QHBoxLayout()
        all_row.setSpacing(8)

        self._all_ccw_btn = _icon_btn("rotate-ccw", "Rotate all 90° CCW", 44)
        self._all_ccw_btn.setEnabled(False)
        self._all_ccw_btn.clicked.connect(lambda: self._rotate_all(-90))
        all_row.addWidget(self._all_ccw_btn)

        self._all_cw_btn = _icon_btn("rotate-cw", "Rotate all 90° CW", 44)
        self._all_cw_btn.setEnabled(False)
        self._all_cw_btn.clicked.connect(lambda: self._rotate_all(90))
        all_row.addWidget(self._all_cw_btn)

        self._all_180_btn = _btn("180°", G100, G200, G700, border=True, h=44, w=60)
        self._all_180_btn.setEnabled(False)
        self._all_180_btn.clicked.connect(lambda: self._rotate_all(180))
        all_row.addWidget(self._all_180_btn)

        all_row.addStretch()
        lay.addLayout(all_row)
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
        self._out_entry.setPlaceholderText("output.pdf")
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
            f"QProgressBar::chunk {{ background: {BLUE}; border-radius: 3px; }}"
        )
        self._progress.hide()
        bot_lay.addWidget(self._progress)

        self._save_btn = _btn("Save Rotated PDF", GREEN, GREEN_HOVER, h=42)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_pdf)
        bot_lay.addWidget(self._save_btn)

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

        hint = QLabel("Click pages to select, then rotate")
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

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF Files (*.pdf)"
        )
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
        self._selected.clear()
        self._rotations.clear()
        self._cells.clear()

        self._file_lbl.setText(Path(path).name)
        self._out_entry.setText(f"{Path(path).stem}_rotated.pdf")
        self._page_count_lbl.setText(f"{self._total_pages} pages")
        self._update_controls()
        self._build_grid()

    def _build_grid(self):
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cells.clear()

        for i in range(self._total_pages):
            cell = _PageCell(i, self._grid_widget)
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
                self._render_cell_thumb(i)
        if self._thumb_queue:
            self._thumb_timer.start(0)

    def _render_cell_thumb(self, page_idx: int):
        try:
            extra = self._rotations.get(page_idx, 0)
            page = self._doc.load_page(page_idx)
            mat = fitz.Matrix(THUMB_SCALE, THUMB_SCALE).prerotate(extra)
            pix = page.get_pixmap(matrix=mat)
            pm = _fitz_pix_to_qpixmap(pix)
            self._cells[page_idx].set_pixmap(pm)
            self._cells[page_idx]._rotation = extra
            self._cells[page_idx].update()
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Selection
    # -----------------------------------------------------------------------

    def _toggle_select(self, page_idx: int):
        if page_idx in self._selected:
            self._selected.discard(page_idx)
        else:
            self._selected.add(page_idx)
        if page_idx < len(self._cells):
            self._cells[page_idx].set_selected(page_idx in self._selected)
        self._update_controls()

    def _select_all(self):
        self._selected = set(range(self._total_pages))
        for cell in self._cells:
            cell.set_selected(True)
        self._update_controls()

    def _deselect_all(self):
        self._selected.clear()
        for cell in self._cells:
            cell.set_selected(False)
        self._update_controls()

    def _update_controls(self):
        has_doc = self._doc is not None
        has_sel = len(self._selected) > 0
        has_rotations = any(v % 360 != 0 for v in self._rotations.values())

        self._sel_all_btn.setEnabled(has_doc)
        self._desel_btn.setEnabled(has_doc)
        self._ccw_btn.setEnabled(has_sel)
        self._cw_btn.setEnabled(has_sel)
        self._r180_btn.setEnabled(has_sel)
        self._all_ccw_btn.setEnabled(has_doc)
        self._all_cw_btn.setEnabled(has_doc)
        self._all_180_btn.setEnabled(has_doc)
        self._save_btn.setEnabled(has_doc and has_rotations)

        n = len(self._selected)
        if n == 0:
            self._sel_lbl.setText("No pages selected")
        else:
            self._sel_lbl.setText(
                f"{n} page{'s' if n != 1 else ''} selected"
            )

    # -----------------------------------------------------------------------
    # Rotation
    # -----------------------------------------------------------------------

    def _apply_rotation(self, page_indices, delta: int):
        for idx in page_indices:
            current = self._rotations.get(idx, 0)
            self._rotations[idx] = (current + delta) % 360
        # Re-render affected cells
        rerender = list(page_indices)
        self._thumb_queue = rerender + [
            i for i in self._thumb_queue if i not in page_indices
        ]
        self._thumb_timer.start(0)
        self._update_controls()
        self._modified = any(v % 360 != 0 for v in self._rotations.values())

    def _rotate_selected(self, delta: int):
        if not self._selected:
            return
        self._apply_rotation(list(self._selected), delta)

    def _rotate_all(self, delta: int):
        self._apply_rotation(list(range(self._total_pages)), delta)

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------

    def _save_pdf(self):
        out_name = self._out_entry.text().strip() or "output.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        default_dir = str(Path(self._pdf_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF", str(Path(default_dir) / out_name), "PDF Files (*.pdf)"
        )
        if not out_path:
            return

        self._progress.setValue(0)
        self._progress.show()
        self._save_btn.setEnabled(False)
        self._status_lbl.setText("Saving...")

        self._worker = _RotateWorker(
            self._pdf_path, out_path, dict(self._rotations), self._total_pages
        )
        self._worker.progress.connect(self._progress.setValue)
        self._worker.finished.connect(self._on_save_done)
        self._worker.failed.connect(self._on_save_failed)
        self._worker.start()

    def _on_save_done(self, out_path: str, rotated_count: int):
        self._status_lbl.setText(
            f"Saved — {rotated_count} page{'s' if rotated_count != 1 else ''} rotated."
        )
        self._status_lbl.setStyleSheet(
            f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
        )
        self._save_btn.setEnabled(True)
        self._progress.hide()

    def _on_save_failed(self, msg: str):
        logger.error("save failed: %s", msg)
        QMessageBox.critical(self, "Save failed", msg)
        self._status_lbl.setText("Save failed.")
        self._save_btn.setEnabled(True)
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
        self._thumb_timer.stop()
        if self._doc:
            try:
                self._doc.close()
            except Exception:
                pass
            self._doc = None
