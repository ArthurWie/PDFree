"""Merge Tool – combine multiple PDF files into one.

PySide6. Loaded by main.py when the user clicks "Merge".

Right panel shows a continuous merge preview: all pages from all files
in their final merge order, grouped by file with a coloured section header.
Reordering or removing a file instantly updates the preview.
"""

import io
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
    QFileDialog,
    QMessageBox,
    QProgressBar,
    QDialog,
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
    BLUE_MED,)
from icons import svg_pixmap
from utils import _fitz_pix_to_qpixmap, _WheelToHScroll, assert_file_writable

try:
    import fitz
except ImportError:
    fitz = None

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    PdfReader = PdfWriter = None

logger = logging.getLogger(__name__)

# Thumb dimensions for the merge preview
THUMB_W = 88
THUMB_H = 116

# Cycling accent colours assigned to each file section
SECTION_COLORS = [
    "#3B82F6",  # blue
    "#10B981",  # emerald
    "#F59E0B",  # amber
    "#EF4444",  # red
    "#8B5CF6",  # violet
    "#F97316",  # orange
    "#06B6D4",  # cyan
    "#EC4899",  # pink
]


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
# File Row  (left panel)
# ===========================================================================


class _FileRow(QFrame):
    """One row in the ordered file list."""

    def __init__(
        self, path: str, thumb: QPixmap, page_count: int, color: str, parent=None
    ):
        super().__init__(parent)
        self.path = path
        self.setFixedHeight(64)
        self.setStyleSheet(
            f"background: {WHITE}; border: 1px solid {G200}; border-radius: 8px;"
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(10)

        # Colour swatch
        swatch = QFrame()
        swatch.setFixedSize(4, 40)
        swatch.setStyleSheet(f"background: {color}; border-radius: 2px; border: none;")
        lay.addWidget(swatch)

        # Thumbnail
        thumb_lbl = QLabel()
        thumb_lbl.setFixedSize(34, 46)
        thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_lbl.setStyleSheet("border: none; background: transparent;")
        if thumb and not thumb.isNull():
            scaled = thumb.scaled(
                34,
                46,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            thumb_lbl.setPixmap(scaled)
        else:
            thumb_lbl.setPixmap(svg_pixmap("file-text", G400, 22))
        lay.addWidget(thumb_lbl)

        # Name + pages
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

        pages_lbl = QLabel(f"{page_count} page{'s' if page_count != 1 else ''}")
        pages_lbl.setStyleSheet(
            f"color: {G500}; font: 11px; border: none; background: transparent;"
        )
        info.addWidget(pages_lbl)
        lay.addLayout(info, 1)

        _arrow_ss = (
            f"QPushButton {{ border: 1px solid {G200}; border-radius: 6px;"
            f" background: {WHITE}; color: {G700}; font: bold 14px; }}"
            f"QPushButton:hover {{ background: {G100}; }}"
            f"QPushButton:disabled {{ color: {G300}; background: {G100}; }}"
        )

        self._up_btn = QPushButton("↑")
        self._up_btn.setFixedSize(28, 28)
        self._up_btn.setStyleSheet(_arrow_ss)
        self._up_btn.setToolTip("Move up")
        lay.addWidget(self._up_btn)

        self._down_btn = QPushButton("↓")
        self._down_btn.setFixedSize(28, 28)
        self._down_btn.setStyleSheet(_arrow_ss)
        self._down_btn.setToolTip("Move down")
        lay.addWidget(self._down_btn)

        self._del_btn = QPushButton("✕")
        self._del_btn.setFixedSize(28, 28)
        self._del_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid {G200}; border-radius: 6px;"
            f" background: {WHITE}; color: {RED}; font: bold 12px; }}"
            f"QPushButton:hover {{ background: #FEF2F2; border-color: {RED}; }}"
        )
        self._del_btn.setToolTip("Remove")
        lay.addWidget(self._del_btn)


# ===========================================================================
# Page thumb cell used inside the merge preview
# ===========================================================================


class _ThumbCell(QFrame):
    """Small page thumbnail with a global merge-order page number badge."""

    def __init__(self, merged_page_num: int, color: str, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._merged_page_num = merged_page_num
        self._color = color
        self.setFixedSize(THUMB_W, THUMB_H + 20)
        self.setStyleSheet(
            f"background: {WHITE}; border: 1px solid {G200}; border-radius: 6px;"
        )

    def set_pixmap(self, pm: QPixmap):
        self._pixmap = pm
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                THUMB_W - 6,
                THUMB_H - 6,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (THUMB_W - scaled.width()) // 2
            y = (THUMB_H - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
        else:
            p.setPen(QColor(G400))
            p.drawText(0, 0, THUMB_W, THUMB_H, Qt.AlignmentFlag.AlignCenter, "…")

        # Global page number badge at bottom
        p.setPen(QColor(self._color))
        f = QFont()
        f.setPointSize(8)
        f.setBold(True)
        p.setFont(f)
        p.drawText(
            0,
            THUMB_H,
            THUMB_W,
            20,
            Qt.AlignmentFlag.AlignCenter,
            str(self._merged_page_num),
        )


# ===========================================================================
# MergeTool
# ===========================================================================


# ===========================================================================
# In-app merge preview dialog
# ===========================================================================


class _MergePreviewDialog(QDialog):
    """Shows the full merged PDF rendered page by page inside the application."""

    _PAGE_W = 640  # target render width in pixels

    def __init__(self, entries: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Merge Preview")
        self.setMinimumSize(740, 860)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._doc = None
        self._page_cells: list[QLabel] = []
        self._render_queue: list[int] = []
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._render_batch)

        self._build_ui()
        self._load(entries)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QWidget()
        toolbar.setFixedHeight(48)
        toolbar.setStyleSheet(f"background: {WHITE}; border-bottom: 1px solid {G200};")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(16, 0, 16, 0)
        tb.setSpacing(12)
        self._title_lbl = QLabel("Preparing preview…")
        self._title_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._title_lbl)
        tb.addStretch()
        close_btn = _btn("Close", WHITE, G100, G700, border=True, h=32, w=72)
        close_btn.clicked.connect(self.close)
        tb.addWidget(close_btn)
        root.addWidget(toolbar)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(f"border: none; background: {G200};")

        self._pages_widget = QWidget()
        self._pages_widget.setStyleSheet(f"background: {G200};")
        self._pages_lay = QVBoxLayout(self._pages_widget)
        self._pages_lay.setContentsMargins(40, 32, 40, 32)
        self._pages_lay.setSpacing(20)
        self._pages_lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._scroll.setWidget(self._pages_widget)
        root.addWidget(self._scroll, 1)

    def _load(self, entries: list):
        try:
            buf = io.BytesIO()
            writer = PdfWriter()
            for entry in entries:
                writer.append(PdfReader(entry["path"]))
            writer.write(buf)
            buf.seek(0)
            self._doc = fitz.open(stream=buf.read(), filetype="pdf")
        except Exception as exc:
            self._title_lbl.setText(f"Preview failed: {exc}")
            return

        total = self._doc.page_count
        self._title_lbl.setText(f"Preview — {total} page{'s' if total != 1 else ''}")

        for i in range(total):
            # Placeholder while rendering
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"background: {WHITE}; border: 1px solid {G200}; border-radius: 4px;"
            )
            lbl.setFixedSize(self._PAGE_W, int(self._PAGE_W * 1.414))
            lbl.setText("…")
            self._pages_lay.addWidget(lbl, 0, Qt.AlignmentFlag.AlignHCenter)
            self._page_cells.append(lbl)
            self._render_queue.append(i)

        self._render_timer.start(0)

    def _render_batch(self):
        if not self._render_queue or self._doc is None:
            return
        batch = self._render_queue[:3]
        self._render_queue = self._render_queue[3:]
        for pi in batch:
            try:
                page = self._doc.load_page(pi)
                scale = self._PAGE_W / page.rect.width
                mat = fitz.Matrix(scale, scale)
                pix = page.get_pixmap(matrix=mat)
                pm = _fitz_pix_to_qpixmap(pix)
                lbl = self._page_cells[pi]
                lbl.setFixedSize(pm.width(), pm.height())
                lbl.setPixmap(pm)
                lbl.setText("")
            except Exception:
                pass
        if self._render_queue:
            self._render_timer.start(0)

    def closeEvent(self, event):
        self._render_timer.stop()
        if self._doc:
            try:
                self._doc.close()
            except Exception:
                pass
            self._doc = None
        super().closeEvent(event)


# ===========================================================================
# MergeTool
class _MergeWorker(QThread):
    progress = Signal(int)
    finished = Signal(str, int)  # (out_path, total_files)
    failed = Signal(str)

    def __init__(self, entries: list, out_path: str):
        super().__init__()
        self._entries = entries
        self._out_path = out_path

    def run(self):
        import worker_semaphore

        worker_semaphore.acquire()
        try:
            assert_file_writable(Path(self._out_path))
            writer = PdfWriter()
            total = len(self._entries)
            for i, entry in enumerate(self._entries):
                reader = PdfReader(entry["path"])
                writer.append(reader)
                self.progress.emit(int((i + 1) / total * 90))
            with open(self._out_path, "wb") as f:
                writer.write(f)
            self.progress.emit(100)
            self.finished.emit(self._out_path, total)
        except PermissionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            logger.exception("worker failed")
            self.failed.emit(str(exc))
        finally:
            worker_semaphore.release()


# ===========================================================================


class MergeTool(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._modified = False
        self._worker = None

        if fitz is None or PdfReader is None:
            lay = QVBoxLayout(self)
            lbl = QLabel(
                "Missing dependencies.\n\nInstall with:\n  pip install pymupdf pypdf"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {G500}; font: 16px;")
            lay.addWidget(lbl)
            return

        # Each entry: {path, page_count, doc, cover_thumb, page_thumbs: list[QPixmap|None]}
        self._entries: list[dict] = []
        self._rows: list[_FileRow] = []

        # Lazy thumb rendering queue: list of (entry_idx, page_idx)
        self._thumb_queue: list[tuple[int, int]] = []
        self._thumb_timer = QTimer(self)
        self._thumb_timer.setSingleShot(True)
        self._thumb_timer.timeout.connect(self._render_thumbs_deferred)

        # Flat list of _ThumbCell widgets mirroring the preview, by (entry_idx, page_idx)
        self._preview_cells: dict[tuple[int, int], _ThumbCell] = {}

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
        icon_box.setPixmap(svg_pixmap("merge", BLUE, 22))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)
        title_lbl = QLabel("Merge PDFs")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 20px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        sec_lbl = QLabel("FILES TO MERGE")
        sec_lbl.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_lbl)
        lay.addSpacing(8)

        drop_zone = QFrame()
        drop_zone.setFixedHeight(52)
        drop_zone.setStyleSheet(
            f"background: {G100};"
            f" border: 2px dashed {G200}; border-radius: 12px;"
        )
        dz_lay = QHBoxLayout(drop_zone)
        dz_lay.setContentsMargins(10, 0, 10, 0)
        dz_lay.setSpacing(8)
        dz_icon = QLabel()
        dz_icon.setPixmap(svg_pixmap("file-text", G400, 18))
        dz_icon.setStyleSheet("border: none; background: transparent;")
        dz_lay.addWidget(dz_icon)
        dz_lbl = QLabel("Drop PDFs here or")
        dz_lbl.setStyleSheet(
            f"color: {G500}; font: 13px; border: none; background: transparent;"
        )
        dz_lay.addWidget(dz_lbl)
        browse_btn = _btn("Browse", BLUE, BLUE_HOVER, h=30, w=80)
        browse_btn.clicked.connect(self._browse_files)
        dz_lay.addWidget(browse_btn)
        dz_lay.addStretch()
        lay.addWidget(drop_zone)
        lay.addSpacing(12)

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet(f"background: {WHITE};")
        self._list_lay = QVBoxLayout(self._list_widget)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(6)
        self._list_lay.addStretch()
        lay.addWidget(self._list_widget)
        lay.addStretch()

        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # Bottom
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
        self._out_entry = QLineEdit("merged.pdf")
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

        self._merge_btn = _btn("Merge PDFs", GREEN, GREEN_HOVER, h=42)
        self._merge_btn.setEnabled(False)
        self._merge_btn.clicked.connect(self._merge_pdfs)
        bot_lay.addWidget(self._merge_btn)

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
        self._toolbar_lbl = QLabel("Merge preview")
        self._toolbar_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._toolbar_lbl)
        tb.addStretch()
        self._total_lbl = QLabel("")
        self._total_lbl.setStyleSheet(
            f"color: {G400}; font: 12px; background: transparent; border: none;"
        )
        tb.addWidget(self._total_lbl)
        tb.addSpacing(12)
        self._preview_btn = _btn(
            "See Preview", WHITE, G100, G700, border=True, h=32, w=108
        )
        self._preview_btn.setEnabled(False)
        self._preview_btn.clicked.connect(self._open_preview)
        tb.addWidget(self._preview_btn)
        v.addWidget(toolbar)

        # Scrollable preview area
        self._preview_scroll = QScrollArea()
        self._preview_scroll.setWidgetResizable(True)
        self._preview_scroll.setStyleSheet("border: none; background: transparent;")

        self._preview_widget = QWidget()
        self._preview_widget.setStyleSheet(f"background: {G100};")
        self._preview_lay = QVBoxLayout(self._preview_widget)
        self._preview_lay.setContentsMargins(20, 20, 20, 20)
        self._preview_lay.setSpacing(0)
        self._preview_lay.addStretch()

        self._preview_scroll.setWidget(self._preview_widget)
        v.addWidget(self._preview_scroll, 1)
        return right

    # -----------------------------------------------------------------------
    # File management
    # -----------------------------------------------------------------------

    def _file_color(self, entry_idx: int) -> str:
        return SECTION_COLORS[entry_idx % len(SECTION_COLORS)]

    def _browse_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add PDFs", "", "PDF Files (*.pdf)"
        )
        for p in paths:
            self._add_file(p)

    def _add_file(self, path: str):
        if not path.lower().endswith(".pdf"):
            return
        if any(e["path"] == path for e in self._entries):
            return

        try:
            doc = fitz.open(path)
            page_count = doc.page_count
            # Render cover thumb synchronously (just page 0, small)
            cover = self._render_page_thumb(doc, 0)
        except Exception as exc:
            logger.exception("could not open pdf")
            QMessageBox.warning(self, "Error", f"Could not open PDF:\n{exc}")
            return

        entry = {
            "path": path,
            "page_count": page_count,
            "doc": doc,
            "cover_thumb": cover,
            "page_thumbs": [None] * page_count,  # filled lazily
        }
        entry["page_thumbs"][0] = cover
        self._entries.append(entry)

        # Queue all remaining pages for this file
        new_idx = len(self._entries) - 1
        for pi in range(1, page_count):
            self._thumb_queue.append((new_idx, pi))

        self._rebuild_list()
        self._rebuild_preview()
        self._update_merge_btn()
        self._thumb_timer.start(0)

    def _render_page_thumb(self, doc, page_idx: int) -> QPixmap:
        page = doc.load_page(page_idx)
        mat = fitz.Matrix(0.28, 0.28)
        pix = page.get_pixmap(matrix=mat)
        return _fitz_pix_to_qpixmap(pix)

    def _render_thumbs_deferred(self):
        if not self._thumb_queue:
            return
        batch = self._thumb_queue[:6]
        self._thumb_queue = self._thumb_queue[6:]
        for entry_idx, page_idx in batch:
            if entry_idx >= len(self._entries):
                continue
            entry = self._entries[entry_idx]
            if page_idx >= entry["page_count"]:
                continue
            try:
                pm = self._render_page_thumb(entry["doc"], page_idx)
                entry["page_thumbs"][page_idx] = pm
                key = (entry_idx, page_idx)
                if key in self._preview_cells:
                    self._preview_cells[key].set_pixmap(pm)
            except Exception:
                pass
        if self._thumb_queue:
            self._thumb_timer.start(0)

    # -----------------------------------------------------------------------
    # Left panel list
    # -----------------------------------------------------------------------

    def _rebuild_list(self):
        for row in self._rows:
            self._list_lay.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        self._list_lay.takeAt(self._list_lay.count() - 1)

        for i, entry in enumerate(self._entries):
            color = self._file_color(i)
            row = _FileRow(
                entry["path"],
                entry["cover_thumb"],
                entry["page_count"],
                color,
                self._list_widget,
            )
            row._up_btn.clicked.connect(lambda _=False, idx=i: self._move_up(idx))
            row._down_btn.clicked.connect(lambda _=False, idx=i: self._move_down(idx))
            row._del_btn.clicked.connect(lambda _=False, idx=i: self._remove_file(idx))
            self._list_lay.addWidget(row)
            self._rows.append(row)

        self._list_lay.addStretch()

        for i, row in enumerate(self._rows):
            row._up_btn.setEnabled(i > 0)
            row._down_btn.setEnabled(i < len(self._rows) - 1)

    def _move_up(self, idx: int):
        if idx <= 0:
            return
        self._entries[idx], self._entries[idx - 1] = (
            self._entries[idx - 1],
            self._entries[idx],
        )
        self._rebuild_list()
        self._rebuild_preview()

    def _move_down(self, idx: int):
        if idx >= len(self._entries) - 1:
            return
        self._entries[idx], self._entries[idx + 1] = (
            self._entries[idx + 1],
            self._entries[idx],
        )
        self._rebuild_list()
        self._rebuild_preview()

    def _remove_file(self, idx: int):
        entry = self._entries.pop(idx)
        try:
            entry["doc"].close()
        except Exception:
            pass
        # Remove queued thumb jobs for this entry (indices have shifted,
        # safest to just clear queue and re-queue remaining entries)
        self._thumb_queue.clear()
        for ei, e in enumerate(self._entries):
            for pi, pm in enumerate(e["page_thumbs"]):
                if pm is None:
                    self._thumb_queue.append((ei, pi))
        self._rebuild_list()
        self._rebuild_preview()
        self._update_merge_btn()
        if self._thumb_queue:
            self._thumb_timer.start(0)

    # -----------------------------------------------------------------------
    # Merge preview (right panel)
    # -----------------------------------------------------------------------

    def _rebuild_preview(self):
        self._preview_cells.clear()

        # Clear existing content
        while self._preview_lay.count():
            item = self._preview_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not self._entries:
            placeholder = QLabel("Add PDFs — the merge preview will appear here")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet(
                f"color: {G400}; font: 14px; background: transparent; border: none;"
            )
            self._preview_lay.addStretch()
            self._preview_lay.addWidget(placeholder)
            self._preview_lay.addStretch()
            self._toolbar_lbl.setText("Merge preview")
            self._total_lbl.setText("")
            return

        global_page = 1
        total_pages = sum(e["page_count"] for e in self._entries)

        for ei, entry in enumerate(self._entries):
            color = self._file_color(ei)
            section = self._build_file_section(entry, ei, color, global_page)
            self._preview_lay.addWidget(section)
            self._preview_lay.addSpacing(8)
            global_page += entry["page_count"]

        self._preview_lay.addStretch()
        self._toolbar_lbl.setText(
            f"Merge preview — {len(self._entries)} file{'s' if len(self._entries) != 1 else ''}"
        )
        self._total_lbl.setText(
            f"{total_pages} page{'s' if total_pages != 1 else ''} total"
        )

    def _build_file_section(
        self, entry: dict, entry_idx: int, color: str, start_page: int
    ) -> QWidget:
        section = QWidget()
        section.setStyleSheet("background: transparent;")
        sv = QVBoxLayout(section)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(6)

        # Section header
        header = QFrame()
        header.setFixedHeight(36)
        header.setStyleSheet(
            f"background: {WHITE}; border-left: 4px solid {color};"
            f" border-top: 1px solid {G200}; border-bottom: 1px solid {G200};"
            f" border-right: 1px solid {G200}; border-radius: 0 6px 6px 0;"
        )
        hh = QHBoxLayout(header)
        hh.setContentsMargins(12, 0, 12, 0)
        hh.setSpacing(10)

        name_lbl = QLabel(Path(entry["path"]).name)
        name_lbl.setStyleSheet(
            f"color: {G900}; font: bold 12px; background: transparent; border: none;"
        )
        hh.addWidget(name_lbl, 1)

        pages_lbl = QLabel(
            f"{entry['page_count']} page{'s' if entry['page_count'] != 1 else ''}"
            f"  ·  p.{start_page}–{start_page + entry['page_count'] - 1}"
        )
        pages_lbl.setStyleSheet(
            f"color: {G500}; font: 11px; background: transparent; border: none;"
        )
        hh.addWidget(pages_lbl)
        sv.addWidget(header)

        # Horizontal scrollable thumb row
        row_scroll = QScrollArea()
        row_scroll.setFixedHeight(THUMB_H + 36)
        row_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        row_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        row_scroll.setWidgetResizable(True)
        row_scroll.setStyleSheet("border: none; background: transparent;")
        row_scroll.viewport().installEventFilter(_WheelToHScroll(row_scroll))

        row_inner = QWidget()
        row_inner.setStyleSheet("background: transparent;")
        row_h = QHBoxLayout(row_inner)
        row_h.setContentsMargins(4, 4, 4, 4)
        row_h.setSpacing(8)

        for pi in range(entry["page_count"]):
            merged_num = start_page + pi
            cell = _ThumbCell(merged_num, color, row_inner)
            pm = entry["page_thumbs"][pi]
            if pm is not None:
                cell.set_pixmap(pm)
            self._preview_cells[(entry_idx, pi)] = cell
            row_h.addWidget(cell)

        row_h.addStretch()
        row_scroll.setWidget(row_inner)
        sv.addWidget(row_scroll)

        return section

    # -----------------------------------------------------------------------
    # Merge
    # -----------------------------------------------------------------------

    def _update_merge_btn(self):
        has_files = len(self._entries) >= 2
        self._merge_btn.setEnabled(has_files)
        self._preview_btn.setEnabled(has_files)

    def _open_preview(self):
        if not self._entries:
            return
        dlg = _MergePreviewDialog(self._entries, self)
        dlg.exec()

    def _merge_pdfs(self):
        if len(self._entries) < 2:
            return

        out_name = self._out_entry.text().strip() or "merged.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save Merged PDF", out_name, "PDF Files (*.pdf)"
        )
        if not out_path:
            return

        self._progress.setValue(0)
        self._progress.show()
        self._merge_btn.setEnabled(False)
        self._status_lbl.setText("Merging...")

        self._worker = _MergeWorker(list(self._entries), out_path)
        self._worker.progress.connect(self._progress.setValue)
        self._worker.finished.connect(self._on_merge_done)
        self._worker.failed.connect(self._on_merge_failed)
        self._worker.start()

    def _on_merge_done(self, out_path: str, total: int):
        self._status_lbl.setText(f"Saved {total} files → {Path(out_path).name}")
        self._merge_btn.setEnabled(len(self._entries) >= 2)
        self._progress.hide()

    def _on_merge_failed(self, msg: str):
        QMessageBox.critical(self, "Merge failed", msg)
        self._status_lbl.setText("Merge failed.")
        self._merge_btn.setEnabled(len(self._entries) >= 2)
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
                self._add_file(path)

    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------

    def cleanup(self):
        self._thumb_timer.stop()
        for entry in self._entries:
            try:
                entry["doc"].close()
            except Exception:
                pass
        self._entries.clear()
