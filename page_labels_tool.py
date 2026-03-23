"""Page Labels Tool – define custom page numbering ranges for a PDF.

Each range specifies: first page, numbering style, optional prefix, and
start number.  For example: pages 1–4 use Roman numerals (i, ii, iii, iv)
and pages 5 onward use Arabic numerals starting at 1.

PyMuPDF's doc.set_page_labels / doc.get_page_labels API is used to read
and write the PDF NumberTree.
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
    QComboBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent

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
from icons import svg_icon, svg_pixmap

try:
    import fitz
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Style options
# ---------------------------------------------------------------------------

_STYLE_DISPLAY = [
    "Arabic  (1, 2, 3…)",
    "roman   (i, ii, iii…)",
    "ROMAN   (I, II, III…)",
    "alpha   (a, b, c…)",
    "ALPHA   (A, B, C…)",
    "None    (no label)",
]
_STYLE_CODE = ["D", "r", "R", "a", "A", ""]


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024**2:.2f} MB"


def _btn(text, bg, hover, text_color=WHITE, border=False, h=36, w=None) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(h)
    if w:
        b.setFixedWidth(w)
    border_s = f"border: 1px solid {G300};" if border else "border: none;"
    b.setStyleSheet(
        f"""
        QPushButton {{
            background: {bg}; color: {text_color};
            {border_s} border-radius: 6px;
            font: {"bold " if bg in (BLUE, GREEN) else ""}13px;
            padding: 0 12px;
        }}
        QPushButton:hover {{ background: {hover}; }}
        QPushButton:disabled {{ color: {G300}; background: {G100}; border-color: {G200}; }}
        """
    )
    return b


# ---------------------------------------------------------------------------
# Pure helper: compute labels from a ranges list + page count
# ---------------------------------------------------------------------------


def compute_labels(ranges: list[dict], page_count: int) -> list[str]:
    """Return a list of page-label strings (one per page) for a preview.

    ``ranges`` is a list of dicts with keys: startpage (0-based), style, prefix,
    firstpagenum.  Must be sorted by startpage ascending before calling.
    """
    if not ranges or page_count == 0:
        return [str(i + 1) for i in range(page_count)]

    sorted_ranges = sorted(ranges, key=lambda r: r["startpage"])
    labels = []
    ri = 0
    for page_idx in range(page_count):
        # Advance to the range that applies to this page
        while (
            ri + 1 < len(sorted_ranges)
            and sorted_ranges[ri + 1]["startpage"] <= page_idx
        ):
            ri += 1
        r = sorted_ranges[ri]
        if r["startpage"] > page_idx:
            labels.append(str(page_idx + 1))
            continue
        offset = page_idx - r["startpage"]
        num = r.get("firstpagenum", 1) + offset
        prefix = r.get("prefix", "")
        style = r.get("style", "D")
        labels.append(prefix + _format_num(num, style))
    return labels


def _format_num(n: int, style: str) -> str:
    if style == "D":
        return str(n)
    if style == "r":
        return _to_roman(n).lower()
    if style == "R":
        return _to_roman(n)
    if style == "a":
        return _to_alpha(n).lower()
    if style == "A":
        return _to_alpha(n)
    return ""  # no label


def _to_roman(n: int) -> str:
    if n <= 0:
        return str(n)
    val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    sym = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    result = ""
    for v, s in zip(val, sym):
        while n >= v:
            result += s
            n -= v
    return result


def _to_alpha(n: int) -> str:
    """1→A, 26→Z, 27→AA, …"""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


# ---------------------------------------------------------------------------
# Range row widget
# ---------------------------------------------------------------------------


class _RangeRow(QFrame):
    def __init__(self, page_count: int, parent=None):
        super().__init__(parent)
        self._page_count = page_count
        self.setFixedHeight(44)
        self.setStyleSheet(f"background: {WHITE}; border-bottom: 1px solid {G100};")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(6)

        # First page (1-based)
        page_lbl = QLabel("Page")
        page_lbl.setFixedWidth(34)
        page_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )
        lay.addWidget(page_lbl)

        self.page_spin = QSpinBox()
        self.page_spin.setRange(1, max(1, page_count))
        self.page_spin.setValue(1)
        self.page_spin.setFixedWidth(56)
        self.page_spin.setFixedHeight(32)
        self.page_spin.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 4px; padding: 0 4px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        lay.addWidget(self.page_spin)

        # Style combo
        self.style_combo = QComboBox()
        for disp in _STYLE_DISPLAY:
            self.style_combo.addItem(disp)
        self.style_combo.setFixedHeight(32)
        self.style_combo.setMinimumWidth(140)
        self.style_combo.setStyleSheet(
            f"QComboBox {{ border: 1px solid {G200}; border-radius: 4px;"
            f" padding: 0 6px; font: 12px; color: {G900}; background: {WHITE}; }}"
            f"QComboBox::drop-down {{ border: none; }}"
        )
        lay.addWidget(self.style_combo, 1)

        # Prefix
        pfx_lbl = QLabel("Prefix")
        pfx_lbl.setFixedWidth(36)
        pfx_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )
        lay.addWidget(pfx_lbl)

        self.prefix_entry = QLineEdit()
        self.prefix_entry.setPlaceholderText("optional")
        self.prefix_entry.setFixedWidth(64)
        self.prefix_entry.setFixedHeight(32)
        self.prefix_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 4px; padding: 0 6px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        lay.addWidget(self.prefix_entry)

        # Start number
        start_lbl = QLabel("Start")
        start_lbl.setFixedWidth(30)
        start_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )
        lay.addWidget(start_lbl)

        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, 9999)
        self.start_spin.setValue(1)
        self.start_spin.setFixedWidth(52)
        self.start_spin.setFixedHeight(32)
        self.start_spin.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 4px; padding: 0 4px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        lay.addWidget(self.start_spin)

        # Remove button
        rm_btn = QPushButton()
        rm_btn.setFixedSize(24, 24)
        rm_btn.setIcon(svg_icon("x", G400, 14))
        rm_btn.setStyleSheet(
            "border: none; background: transparent; border-radius: 4px;"
        )
        rm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rm_btn.clicked.connect(self._remove_self)
        lay.addWidget(rm_btn)

    def _remove_self(self) -> None:
        tool = self._find_tool()
        if tool:
            tool._remove_range(self)

    def _find_tool(self):
        w = self.parent()
        while w:
            if isinstance(w, PageLabelsTool):
                return w
            w = w.parent()
        return None

    def to_dict(self) -> dict:
        return {
            "startpage": self.page_spin.value() - 1,  # 0-based
            "style": _STYLE_CODE[self.style_combo.currentIndex()],
            "prefix": self.prefix_entry.text(),
            "firstpagenum": self.start_spin.value(),
        }

    def from_dict(self, d: dict) -> None:
        self.page_spin.setValue(d.get("startpage", 0) + 1)
        style = d.get("style", "D")
        idx = _STYLE_CODE.index(style) if style in _STYLE_CODE else 0
        self.style_combo.setCurrentIndex(idx)
        self.prefix_entry.setText(d.get("prefix", ""))
        self.start_spin.setValue(d.get("firstpagenum", 1))


# ---------------------------------------------------------------------------
# PageLabelsTool
# ---------------------------------------------------------------------------


class PageLabelsTool(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._modified = False
        self._pdf_path = ""
        self._page_count = 0
        self._rows: list[_RangeRow] = []

        if fitz is None:
            lay = QVBoxLayout(self)
            lbl = QLabel("Missing dependency.\n\nInstall with:\n  pip install pymupdf")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {G500}; font: 16px;")
            lay.addWidget(lbl)
            return

        self._build_ui()
        self.setAcceptDrops(True)

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_left_panel())
        root.addWidget(self._build_right_panel(), 1)

    def _build_left_panel(self) -> QWidget:
        left = QWidget()
        left.setFixedWidth(420)
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
        icon_box.setPixmap(svg_pixmap("file-plus", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)
        title_lbl = QLabel("Page Labels")
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

        # Label ranges section
        sec_ranges = QLabel("LABEL RANGES")
        sec_ranges.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_ranges)
        lay.addSpacing(4)

        hint = QLabel(
            "Each range applies from its page to the start of the next range."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color: {G400}; font: 11px; background: transparent; border: none;"
        )
        lay.addWidget(hint)
        lay.addSpacing(8)

        # Scrollable rows area
        rows_scroll = QScrollArea()
        rows_scroll.setWidgetResizable(True)
        rows_scroll.setFixedHeight(220)
        rows_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rows_scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {G200}; border-radius: 8px;"
            " background: transparent; }}"
        )

        self._rows_widget = QWidget()
        self._rows_widget.setStyleSheet(f"background: {WHITE};")
        self._rows_lay = QVBoxLayout(self._rows_widget)
        self._rows_lay.setContentsMargins(0, 0, 0, 0)
        self._rows_lay.setSpacing(0)

        self._empty_ranges_lbl = QLabel(
            "No ranges defined — entire document\nuses the default (1, 2, 3…)."
        )
        self._empty_ranges_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_ranges_lbl.setStyleSheet(
            f"color: {G400}; font: 12px; border: none; background: transparent;"
        )
        self._rows_lay.addWidget(self._empty_ranges_lbl)
        self._rows_lay.addStretch()

        rows_scroll.setWidget(self._rows_widget)
        lay.addWidget(rows_scroll)
        lay.addSpacing(8)

        add_row_btn = _btn(
            "+ Add Range", G100, G200, text_color=G700, border=True, h=32
        )
        add_row_btn.setEnabled(False)
        add_row_btn.clicked.connect(self._add_range)
        self._add_range_btn = add_row_btn
        lay.addWidget(add_row_btn)

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
        self._out_entry.setPlaceholderText("output_labeled.pdf")
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

        self._save_btn = _btn("Apply Labels", GREEN, GREEN_HOVER, h=42)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save)
        bot_lay.addWidget(self._save_btn)

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
        self._toolbar_lbl = QLabel("Label preview")
        self._toolbar_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._toolbar_lbl)
        tb.addStretch()
        v.addWidget(toolbar)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Physical Page", "Label"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().hide()
        self._table.setStyleSheet(
            f"QTableWidget {{ border: none; background: {WHITE}; gridline-color: {G100}; }}"
            f"QTableWidget::item {{ padding: 0 8px; color: {G900}; }}"
            f"QHeaderView::section {{ background: {G100}; color: {G700}; font: bold 12px;"
            f" border: none; border-bottom: 1px solid {G200}; padding: 6px 8px; }}"
        )
        v.addWidget(self._table, 1)
        return right

    # -----------------------------------------------------------------------
    # File loading
    # -----------------------------------------------------------------------

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if path:
            self._load_file(path)

    def _load_file(self, path: str) -> None:
        try:
            doc = fitz.open(path)
            page_count = doc.page_count
            existing = doc.get_page_labels()
            doc.close()
        except Exception as exc:
            logger.exception("could not open pdf for page labels")
            QMessageBox.warning(self, "Error", f"Could not open PDF:\n{exc}")
            return

        self._pdf_path = path
        self._page_count = page_count
        stem = Path(path).stem
        self._out_entry.setText(f"{stem}_labeled.pdf")
        self._toolbar_lbl.setText(Path(path).name)
        self._save_btn.setEnabled(True)
        self._add_range_btn.setEnabled(True)

        # Clear existing rows
        for row in list(self._rows):
            self._remove_range(row, _silent=True)

        # Populate from existing labels (or add a sensible default)
        if existing:
            for d in existing:
                self._add_range(init=d)
        else:
            # Default: Arabic from page 1
            self._add_range(
                init={"startpage": 0, "style": "D", "prefix": "", "firstpagenum": 1}
            )

        self._refresh_preview()

    # -----------------------------------------------------------------------
    # Range management
    # -----------------------------------------------------------------------

    def _add_range(self, init: dict | None = None) -> None:
        row = _RangeRow(self._page_count)
        if init:
            row.from_dict(init)

        # Wire change signals to preview refresh
        row.page_spin.valueChanged.connect(self._refresh_preview)
        row.style_combo.currentIndexChanged.connect(self._refresh_preview)
        row.prefix_entry.textChanged.connect(self._refresh_preview)
        row.start_spin.valueChanged.connect(self._refresh_preview)

        self._rows.append(row)
        self._empty_ranges_lbl.setVisible(False)
        # Insert before stretch
        stretch_idx = self._rows_lay.count() - 1
        self._rows_lay.insertWidget(stretch_idx, row)
        self._refresh_preview()

    def _remove_range(self, row: _RangeRow, _silent: bool = False) -> None:
        if row in self._rows:
            self._rows.remove(row)
        row.deleteLater()
        self._empty_ranges_lbl.setVisible(len(self._rows) == 0)
        if not _silent:
            self._refresh_preview()

    # -----------------------------------------------------------------------
    # Preview
    # -----------------------------------------------------------------------

    def _get_ranges(self) -> list[dict]:
        return [r.to_dict() for r in self._rows]

    def _refresh_preview(self) -> None:
        if not self._page_count:
            return
        ranges = self._get_ranges()
        labels = compute_labels(ranges, self._page_count)

        self._table.setRowCount(self._page_count)
        for i, label in enumerate(labels):
            phys_item = QTableWidgetItem(str(i + 1))
            phys_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            label_item = QTableWidgetItem(label)
            self._table.setItem(i, 0, phys_item)
            self._table.setItem(i, 1, label_item)

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------

    def _save(self) -> None:
        if not self._pdf_path:
            return

        out_name = self._out_entry.text().strip() or "labeled.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        default_dir = str(Path(self._pdf_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Labeled PDF",
            str(Path(default_dir) / out_name),
            "PDF Files (*.pdf)",
        )
        if not out_path:
            return

        ranges = self._get_ranges()
        # Sort by startpage, validate no duplicate startpages
        sorted_ranges = sorted(ranges, key=lambda r: r["startpage"])

        try:
            assert_file_writable(Path(out_path))
            backup_original(Path(self._pdf_path))
            doc = fitz.open(self._pdf_path)
            if sorted_ranges:
                doc.set_page_labels(sorted_ranges)
            else:
                doc.set_page_labels([])
            doc.save(out_path, garbage=3, deflate=True)
            doc.close()
        except PermissionError as exc:
            logger.exception("could not save page labels pdf")
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        except Exception as exc:
            logger.exception("could not save page labels pdf")
            QMessageBox.critical(self, "Save failed", str(exc))
            return

        self._status_lbl.setText("Saved successfully.")
        self._status_lbl.setStyleSheet(
            f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
        )
        self._modified = False

    # -----------------------------------------------------------------------
    # Drag and drop
    # -----------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pdf"):
                self._load_file(path)
                break

    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------

    def cleanup(self) -> None:
        pass
