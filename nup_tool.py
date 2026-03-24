"""N-Up Layout Tool – combine multiple source pages onto each output sheet.

PySide6. Loaded by main.py when the user clicks "N-Up Layout".

Layouts
-------
2-Up     – two pages side by side on landscape output.
4-Up     – four pages in a 2x2 grid on each sheet.
Booklet  – reorder pages for printing and folding into a booklet.
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
    QProgressBar,
    QSizePolicy,
    QComboBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import (
    QDragEnterEvent,
    QDropEvent,
)

from colors import (
    BLUE,
    BLUE_DIM,
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
    TEAL,
    EMERALD,
    BLUE_MED,
)
from icons import svg_pixmap

try:
    import fitz
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Layout definitions
# ---------------------------------------------------------------------------

LAYOUTS = [
    {
        "id": "2up",
        "label": "2-Up",
        "badge": "2×1",
        "badge_color": BLUE,
        "desc": "Two pages side by side on landscape output.",
    },
    {
        "id": "4up",
        "label": "4-Up",
        "badge": "2×2",
        "badge_color": TEAL,
        "desc": "Four pages in a 2×2 grid on each sheet.",
    },
    {
        "id": "booklet",
        "label": "Booklet",
        "badge": "Fold",
        "badge_color": EMERALD,
        "desc": "Reorder pages for printing and folding into a booklet.",
    },
]

OUTPUT_SIZES = {
    "A4 Portrait": (595.28, 841.89),
    "A4 Landscape": (841.89, 595.28),
    "Letter Portrait": (612.0, 792.0),
    "Letter Landscape": (792.0, 612.0),
}


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


def _combo(options: list) -> QComboBox:
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


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024**2:.2f} MB"


# ===========================================================================
# Layout Card
# ===========================================================================


class _LayoutCard(QFrame):
    """Selectable card representing one N-up layout option."""

    def __init__(self, layout: dict, parent=None):
        super().__init__(parent)
        self.layout_id = layout["id"]
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(76)
        self._apply_style()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        badge = QLabel(layout["badge"])
        badge.setFixedWidth(60)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: {layout['badge_color']}; color: {WHITE};"
            " border-radius: 4px; font: bold 11px; padding: 2px 0;"
            " border: none;"
        )
        lay.addWidget(badge)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)

        name_lbl = QLabel(layout["label"])
        name_lbl.setStyleSheet(
            f"color: {G900}; font: bold 13px; background: transparent; border: none;"
        )
        text_col.addWidget(name_lbl)

        desc_lbl = QLabel(layout["desc"])
        desc_lbl.setStyleSheet(
            f"color: {G500}; font: 11px; background: transparent; border: none;"
        )
        text_col.addWidget(desc_lbl)
        lay.addLayout(text_col, 1)

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
                tool._select_layout(self.layout_id)

    def _find_tool(self):
        w = self.parent()
        while w:
            if isinstance(w, NUpTool):
                return w
            w = w.parent()
        return None


# ===========================================================================
# NUpTool
# ===========================================================================


class _NUpWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, pdf_path, out_path, layout_id, out_w, out_h):
        super().__init__()
        self._pdf_path = pdf_path
        self._out_path = out_path
        self._layout_id = layout_id
        self._out_w = out_w
        self._out_h = out_h

    def run(self):
        try:
            assert_file_writable(Path(self._out_path))
            backup_original(Path(self._pdf_path))
            if self._layout_id == "2up":
                self._create_2up()
            elif self._layout_id == "4up":
                self._create_4up()
            else:
                self._create_booklet()
            self.finished.emit(self._out_path)
        except PermissionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            logger.exception("worker failed")
            self.failed.emit(str(exc))

    def _create_2up(self):
        out = fitz.open()
        src = fitz.open(self._pdf_path)
        total = src.page_count
        try:
            for i in range(0, total, 2):
                sheet = out.new_page(width=self._out_w, height=self._out_h)
                sheet.show_pdf_page(
                    fitz.Rect(0, 0, self._out_w / 2, self._out_h), src, i
                )
                if i + 1 < total:
                    sheet.show_pdf_page(
                        fitz.Rect(self._out_w / 2, 0, self._out_w, self._out_h),
                        src,
                        i + 1,
                    )
            out.save(self._out_path, garbage=3, deflate=True)
        finally:
            src.close()
            out.close()

    def _create_4up(self):
        out = fitz.open()
        src = fitz.open(self._pdf_path)
        total = src.page_count
        try:
            for i in range(0, total, 4):
                sheet = out.new_page(width=self._out_w, height=self._out_h)
                positions = [
                    fitz.Rect(0, 0, self._out_w / 2, self._out_h / 2),
                    fitz.Rect(self._out_w / 2, 0, self._out_w, self._out_h / 2),
                    fitz.Rect(0, self._out_h / 2, self._out_w / 2, self._out_h),
                    fitz.Rect(
                        self._out_w / 2, self._out_h / 2, self._out_w, self._out_h
                    ),
                ]
                for j, rect in enumerate(positions):
                    if i + j < total:
                        sheet.show_pdf_page(rect, src, i + j)
            out.save(self._out_path, garbage=3, deflate=True)
        finally:
            src.close()
            out.close()

    def _create_booklet(self):
        out = fitz.open()
        src = fitz.open(self._pdf_path)
        total = src.page_count
        n = total
        while n % 4 != 0:
            n += 1
        order = []
        lo, hi = 0, n - 1
        while lo <= hi:
            order.append((hi, lo))
            lo += 1
            hi -= 1
        try:
            for back_pg, front_pg in order:
                sheet = out.new_page(width=self._out_w, height=self._out_h)
                if back_pg < total:
                    sheet.show_pdf_page(
                        fitz.Rect(0, 0, self._out_w / 2, self._out_h), src, back_pg
                    )
                if front_pg < total:
                    sheet.show_pdf_page(
                        fitz.Rect(self._out_w / 2, 0, self._out_w, self._out_h),
                        src,
                        front_pg,
                    )
            out.save(self._out_path, garbage=3, deflate=True)
        finally:
            src.close()
            out.close()


class NUpTool(QWidget):
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
        self._layout_id = "2up"
        self._layout_cards: dict[str, _LayoutCard] = {}
        self._worker = None

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

        title_lbl = QLabel("N-Up Layout")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 20px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        # File section
        lay.addWidget(_section("SOURCE FILE"))
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

        # Layout section
        lay.addWidget(_section("LAYOUT"))
        lay.addSpacing(8)

        for layout in LAYOUTS:
            card = _LayoutCard(layout, inner)
            self._layout_cards[layout["id"]] = card
            lay.addWidget(card)
            lay.addSpacing(8)

        self._layout_cards["2up"].set_selected(True)

        lay.addSpacing(24)

        # Output page size
        lay.addWidget(_section("OUTPUT PAGE SIZE"))
        lay.addSpacing(8)
        self._size_combo = _combo(list(OUTPUT_SIZES.keys()))
        self._size_combo.setCurrentText("A4 Landscape")
        lay.addWidget(self._size_combo)

        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # Bottom action area
        bottom = QWidget()
        bottom.setStyleSheet(f"background: {WHITE}; border-top: 1px solid {G200};")
        bot_lay = QVBoxLayout(bottom)
        bot_lay.setContentsMargins(24, 16, 24, 20)
        bot_lay.setSpacing(10)

        out_lbl = _section("OUTPUT FILE")
        bot_lay.addWidget(out_lbl)

        self._out_entry = QLineEdit()
        self._out_entry.setPlaceholderText("output_nup.pdf")
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

        self._create_btn = _btn("Create Layout", GREEN, GREEN_HOVER, h=42)
        self._create_btn.setEnabled(False)
        self._create_btn.clicked.connect(self._create_layout)
        bot_lay.addWidget(self._create_btn)

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
        tb.setSpacing(0)
        self._toolbar_lbl = QLabel("File details")
        self._toolbar_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._toolbar_lbl)
        tb.addStretch()
        v.addWidget(toolbar)

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
        stem = Path(path).stem
        self._out_entry.setText(f"{stem}_nup.pdf")
        self._create_btn.setEnabled(True)
        self._status_lbl.setText("")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )

        self._toolbar_lbl.setText(Path(path).name)
        self._show_file_info(page_count)

    def _sheet_count(self, page_count: int, layout_id: str) -> int:
        if layout_id == "2up":
            return (page_count + 1) // 2
        if layout_id == "4up":
            return (page_count + 3) // 4
        # booklet: pad to multiple of 4
        n = page_count
        while n % 4 != 0:
            n += 1
        return n // 2

    def _show_file_info(self, page_count: int):
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

        title = QLabel("Source File")
        title.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1px;"
            " background: transparent; border: none;"
        )
        card_lay.addWidget(title)

        file_size = Path(self._pdf_path).stat().st_size
        self._add_info_row(card_lay, "File", Path(self._pdf_path).name)
        self._add_info_row(card_lay, "Size", _fmt_size(file_size))
        self._add_info_row(card_lay, "Pages", str(page_count))

        sheets = self._sheet_count(page_count, self._layout_id)
        self._add_info_row(
            card_lay, "Sheets", f"{sheets} output sheet{'s' if sheets != 1 else ''}"
        )

        self._info_lay.addWidget(card)
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

    # -----------------------------------------------------------------------
    # Layout selection
    # -----------------------------------------------------------------------

    def _select_layout(self, layout_id: str):
        self._layout_id = layout_id
        for lid, card in self._layout_cards.items():
            card.set_selected(lid == layout_id)

    # -----------------------------------------------------------------------
    # N-Up creation
    # -----------------------------------------------------------------------

    def _create_layout(self):
        if not self._pdf_path:
            return

        out_name = self._out_entry.text().strip() or "output_nup.pdf"
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

        self._progress.setValue(0)
        self._progress.show()
        self._create_btn.setEnabled(False)
        self._status_lbl.setText("Creating layout...")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )

        out_w, out_h = OUTPUT_SIZES[self._size_combo.currentText()]
        self._worker = _NUpWorker(
            self._pdf_path, out_path, self._layout_id, out_w, out_h
        )
        self._worker.finished.connect(self._on_save_done)
        self._worker.failed.connect(self._on_save_failed)
        self._worker.start()

    def _on_save_done(self, out_path: str):
        out_size = Path(out_path).stat().st_size
        self._status_lbl.setText(f"Saved — {_fmt_size(out_size)}")
        self._status_lbl.setStyleSheet(
            f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
        )
        self._create_btn.setEnabled(True)
        self._progress.hide()

    def _on_save_failed(self, msg: str):
        QMessageBox.critical(self, "Save failed", msg)
        self._status_lbl.setText("Failed.")
        self._create_btn.setEnabled(True)
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
