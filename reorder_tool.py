"""Reorder Pages Tool – drag-and-drop page reordering for PDFs.

PySide6. Loaded by main.py when the user clicks "Reorder Pages".
"""

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
    QApplication,
)
from PySide6.QtCore import Qt, QTimer, QMimeData, QPoint
from PySide6.QtGui import (
    QPainter,
    QColor,
    QFont,
    QDrag,
    QDragEnterEvent,
    QDropEvent,
    QPixmap,
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
)
from icons import svg_pixmap
from utils import _fitz_pix_to_qpixmap

try:
    import fitz
except ImportError:
    fitz = None

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    PdfReader = PdfWriter = None

THUMB_W = 110
THUMB_H = 140
GRID_COLS = 4
THUMB_SCALE = 0.25


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


# ===========================================================================
# Page Thumbnail Cell  (draggable + drop target)
# ===========================================================================


class _PageCell(QFrame):
    def __init__(self, original_idx, position, parent=None):
        super().__init__(parent)
        self.original_idx = original_idx
        self._position = position
        self._pixmap = None
        self._drop_highlight = False
        self.setFixedSize(THUMB_W, THUMB_H + 22)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAcceptDrops(True)
        self._apply_style()

    def _apply_style(self):
        if self._drop_highlight:
            self.setStyleSheet(
                f"background: {BLUE_DIM}; border: 2px solid {BLUE}; border-radius: 6px;"
            )
        else:
            self.setStyleSheet(
                f"background: {WHITE}; border: 1px solid {G200}; border-radius: 6px;"
            )

    def set_pixmap(self, pm):
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

        p.setPen(QColor(G500))
        f = QFont()
        f.setPointSize(8)
        p.setFont(f)
        p.drawText(0, THUMB_H, THUMB_W, 22, Qt.AlignmentFlag.AlignCenter,
                   str(self._position + 1))

    # -----------------------------------------------------------------------
    # Drag
    # -----------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(str(self._position))
            drag.setMimeData(mime)
            grab = self.grab()
            drag.setPixmap(grab.scaled(88, 110, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation))
            drag.setHotSpot(QPoint(44, 55))
            drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            self._drop_highlight = True
            self._apply_style()
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._drop_highlight = False
        self._apply_style()

    def dropEvent(self, event):
        self._drop_highlight = False
        self._apply_style()
        from_pos = int(event.mimeData().text())
        if from_pos != self._position:
            tool = self._find_tool()
            if tool:
                tool._move_page(from_pos, self._position)
        event.acceptProposedAction()

    def _find_tool(self):
        w = self.parent()
        while w:
            if isinstance(w, ReorderTool):
                return w
            w = w.parent()
        return None


# ===========================================================================
# ReorderTool
# ===========================================================================


class ReorderTool(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._modified = False

        if fitz is None or PdfReader is None:
            lay = QVBoxLayout(self)
            lbl = QLabel("Missing dependencies.\n\nInstall:\n  pip install pymupdf pypdf")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {G500}; font: 16px;")
            lay.addWidget(lbl)
            return

        self._pdf_path = ""
        self._doc = None
        self._total_pages = 0
        self._order: list[int] = []          # current position → original page index
        self._cells: list[_PageCell] = []
        self._thumb_cache: dict[int, QPixmap] = {}  # original_idx → pixmap
        self._thumb_timer = QTimer(self)
        self._thumb_timer.setSingleShot(True)
        self._thumb_timer.timeout.connect(self._render_thumbs_deferred)
        self._thumb_queue: list[int] = []
        self._selected_pos: int = -1

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
        icon_box.setPixmap(svg_pixmap("layers", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet("background: #DBEAFE; border-radius: 8px;")
        title_row.addWidget(icon_box)
        title_lbl = QLabel("Reorder Pages")
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
            f"background: rgba(249,250,251,128);"
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

        # Hint
        hint = QLabel("Drag pages to reorder them.\nUse the buttons below for precise control.")
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        lay.addWidget(hint)
        lay.addSpacing(20)

        # Move controls
        lay.addWidget(_section("MOVE SELECTED PAGE"))
        lay.addSpacing(8)

        _arrow_ss = (
            f"QPushButton {{ border: 1px solid {G200}; border-radius: 6px;"
            f" background: {WHITE}; color: {G700}; font: bold 14px; }}"
            f"QPushButton:hover {{ background: {G100}; }}"
            f"QPushButton:disabled {{ color: {G300}; background: {G100}; }}"
        )
        move_row = QHBoxLayout()
        move_row.setSpacing(6)
        move_row.setContentsMargins(0, 0, 0, 0)

        self._first_btn = QPushButton("⇤")
        self._first_btn.setFixedSize(36, 36)
        self._first_btn.setStyleSheet(_arrow_ss)
        self._first_btn.setEnabled(False)
        self._first_btn.setToolTip("Move to first")
        self._first_btn.clicked.connect(self._move_to_first)
        move_row.addWidget(self._first_btn)

        self._up_btn = QPushButton("↑")
        self._up_btn.setFixedSize(36, 36)
        self._up_btn.setStyleSheet(_arrow_ss)
        self._up_btn.setEnabled(False)
        self._up_btn.clicked.connect(self._move_up)
        move_row.addWidget(self._up_btn)

        self._down_btn = QPushButton("↓")
        self._down_btn.setFixedSize(36, 36)
        self._down_btn.setStyleSheet(_arrow_ss)
        self._down_btn.setEnabled(False)
        self._down_btn.clicked.connect(self._move_down)
        move_row.addWidget(self._down_btn)

        self._last_btn = QPushButton("⇥")
        self._last_btn.setFixedSize(36, 36)
        self._last_btn.setStyleSheet(_arrow_ss)
        self._last_btn.setEnabled(False)
        self._last_btn.setToolTip("Move to last")
        self._last_btn.clicked.connect(self._move_to_last)
        move_row.addWidget(self._last_btn)

        move_row.addStretch()
        lay.addLayout(move_row)
        lay.addSpacing(8)

        self._sel_lbl = QLabel("Click a page to select it")
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

        bot.addWidget(_section("OUTPUT FILE"))
        self._out_entry = QLineEdit()
        self._out_entry.setPlaceholderText("output_reordered.pdf")
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

        self._save_btn = _btn("Save Reordered PDF", GREEN, GREEN_HOVER, h=42)
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
        self._page_count_lbl = QLabel("Load a PDF to begin")
        self._page_count_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._page_count_lbl)
        tb.addStretch()
        hint = QLabel("Drag pages to reorder")
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

    def _load_file(self, path):
        if self._doc:
            try:
                self._doc.close()
            except Exception:
                pass
        try:
            self._doc = fitz.open(path)
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Could not open PDF:\n{exc}")
            return

        self._pdf_path = path
        self._total_pages = self._doc.page_count
        self._order = list(range(self._total_pages))
        self._thumb_cache.clear()
        self._selected_pos = -1

        self._file_lbl.setText(Path(path).name)
        self._out_entry.setText(f"{Path(path).stem}_reordered.pdf")
        self._page_count_lbl.setText(f"{self._total_pages} pages")
        self._save_btn.setEnabled(False)
        self._update_move_buttons()
        self._rebuild_grid(render=True)

    # -----------------------------------------------------------------------
    # Grid
    # -----------------------------------------------------------------------

    def _rebuild_grid(self, render=False):
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cells.clear()

        for pos, orig_idx in enumerate(self._order):
            cell = _PageCell(orig_idx, pos, self._grid_widget)
            if orig_idx in self._thumb_cache:
                cell.set_pixmap(self._thumb_cache[orig_idx])
            row, col = divmod(pos, GRID_COLS)
            self._grid_layout.addWidget(cell, row, col)
            self._cells.append(cell)

        if render:
            uncached = [orig for orig in self._order if orig not in self._thumb_cache]
            self._thumb_queue = uncached
            if self._thumb_queue:
                self._thumb_timer.start(0)

        # Restore selection highlight
        if 0 <= self._selected_pos < len(self._cells):
            self._cells[self._selected_pos].setStyleSheet(
                f"background: {BLUE_DIM}; border: 2px solid {BLUE}; border-radius: 6px;"
            )

    def _render_thumbs_deferred(self):
        if not self._thumb_queue or not self._doc:
            return
        batch = self._thumb_queue[:8]
        self._thumb_queue = self._thumb_queue[8:]
        for orig_idx in batch:
            try:
                page = self._doc.load_page(orig_idx)
                mat = fitz.Matrix(THUMB_SCALE, THUMB_SCALE)
                pix = page.get_pixmap(matrix=mat)
                pm = _fitz_pix_to_qpixmap(pix)
                self._thumb_cache[orig_idx] = pm
                # Find the cell showing this original index
                for cell in self._cells:
                    if cell.original_idx == orig_idx:
                        cell.set_pixmap(pm)
                        break
            except Exception:
                pass
        if self._thumb_queue:
            self._thumb_timer.start(0)

    # -----------------------------------------------------------------------
    # Reorder logic
    # -----------------------------------------------------------------------

    def _move_page(self, from_pos, to_pos):
        item = self._order.pop(from_pos)
        self._order.insert(to_pos, item)
        if self._selected_pos == from_pos:
            self._selected_pos = to_pos
        elif from_pos < to_pos:
            if from_pos < self._selected_pos <= to_pos:
                self._selected_pos -= 1
        else:
            if to_pos <= self._selected_pos < from_pos:
                self._selected_pos += 1
        self._rebuild_grid()
        self._save_btn.setEnabled(True)
        self._modified = True
        self._update_move_buttons()

    def _select_pos(self, pos):
        self._selected_pos = pos
        self._sel_lbl.setText(f"Page {pos + 1} selected")
        self._update_move_buttons()
        # Update cell highlight
        for i, cell in enumerate(self._cells):
            if i == pos:
                cell.setStyleSheet(
                    f"background: {BLUE_DIM}; border: 2px solid {BLUE}; border-radius: 6px;"
                )
            else:
                cell.setStyleSheet(
                    f"background: {WHITE}; border: 1px solid {G200}; border-radius: 6px;"
                )

    def _move_to_first(self):
        if self._selected_pos > 0:
            self._move_page(self._selected_pos, 0)

    def _move_up(self):
        if self._selected_pos > 0:
            self._move_page(self._selected_pos, self._selected_pos - 1)

    def _move_down(self):
        if self._selected_pos < self._total_pages - 1:
            self._move_page(self._selected_pos, self._selected_pos + 1)

    def _move_to_last(self):
        if self._selected_pos < self._total_pages - 1:
            self._move_page(self._selected_pos, self._total_pages - 1)

    def _update_move_buttons(self):
        has_sel = 0 <= self._selected_pos < self._total_pages
        self._first_btn.setEnabled(has_sel and self._selected_pos > 0)
        self._up_btn.setEnabled(has_sel and self._selected_pos > 0)
        self._down_btn.setEnabled(has_sel and self._selected_pos < self._total_pages - 1)
        self._last_btn.setEnabled(has_sel and self._selected_pos < self._total_pages - 1)

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------

    def _save(self):
        out_name = self._out_entry.text().strip() or "reordered.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        default_dir = str(Path(self._pdf_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF",
            str(Path(default_dir) / out_name),
            "PDF Files (*.pdf)",
        )
        if not out_path:
            return

        self._save_btn.setEnabled(False)
        self._status_lbl.setText("Saving...")
        QApplication.processEvents()

        try:
            reader = PdfReader(self._pdf_path)
            writer = PdfWriter()
            for orig_idx in self._order:
                writer.add_page(reader.pages[orig_idx])
            with open(out_path, "wb") as f:
                writer.write(f)
            self._status_lbl.setText(f"Saved: {Path(out_path).name}")
            self._status_lbl.setStyleSheet(
                f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
            )
            self._modified = False
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            self._status_lbl.setText("Save failed.")
        finally:
            self._save_btn.setEnabled(True)

    # -----------------------------------------------------------------------
    # Drag and drop (file drop onto tool)
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
