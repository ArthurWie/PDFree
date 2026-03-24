"""Compare PDFs Tool — side-by-side visual or text diff.

PySide6. Two-panel layout: left settings, right compare view.
"""

from __future__ import annotations

import difflib
import logging
import os
from pathlib import Path
from typing import Optional

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
    QCheckBox,
    QSlider,
    QTextEdit,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPixmap,
    QFont,
    QPen,
    QDragEnterEvent,
    QDropEvent,
)

from colors import (
    BLUE,
    BLUE_HOVER,
    BLUE_DIM,
    G100,
    G200,
    G300,
    G400,
    G500,
    G700,
    G900,
    WHITE,
    TEAL,
    RED,
    EMERALD,
    BLUE_MED,
)
from icons import svg_pixmap
from utils import _fitz_pix_to_qpixmap, assert_file_writable

try:
    import fitz
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)

MODES = [
    {
        "id": "visual",
        "label": "Visual Diff",
        "badge": "Pixels",
        "badge_color": BLUE,
        "desc": "Highlight pixel-level differences between pages.",
    },
    {
        "id": "text",
        "label": "Text Diff",
        "badge": "Text",
        "badge_color": TEAL,
        "desc": "Show added and removed text with color highlights.",
    },
]


def _btn(text, bg, hover, text_color=WHITE, border=False, h=36, w=None) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(h)
    if w:
        b.setFixedWidth(w)
    border_s = f"border: 1px solid {G300};" if border else "border: none;"
    b.setStyleSheet(
        f"QPushButton {{ background: {bg}; color: {text_color};"
        f" {border_s} border-radius: 6px;"
        f" font: {'bold ' if bg in (BLUE, '#16A34A') else ''}13px;"
        f" padding: 0 12px; }}"
        f" QPushButton:hover {{ background: {hover}; }}"
        f" QPushButton:disabled {{ color: {G300}; background: {G100}; border-color: {G200}; }}"
    )
    return b


class _ModeCard(QFrame):
    def __init__(self, mode: dict, parent=None):
        super().__init__(parent)
        self.mode_id = mode["id"]
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(76)
        self._apply_style()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        badge = QLabel(mode["badge"])
        badge.setFixedWidth(60)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: {mode['badge_color']}; color: {WHITE};"
            " border-radius: 4px; font: bold 11px; padding: 2px 0; border: none;"
        )
        lay.addWidget(badge)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)

        name_lbl = QLabel(mode["label"])
        name_lbl.setStyleSheet(
            f"color: {G900}; font: bold 13px; background: transparent; border: none;"
        )
        text_col.addWidget(name_lbl)

        desc_lbl = QLabel(mode["desc"])
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
                tool._select_mode(self.mode_id)

    def _find_tool(self):
        w = self.parent()
        while w:
            if isinstance(w, CompareTool):
                return w
            w = w.parent()
        return None


class _CompareCanvas(QWidget):
    def __init__(self, tool: "CompareTool", parent=None):
        super().__init__(parent)
        self._t = tool
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(400, 300)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = self._t
        w = self.width()
        h = self.height()
        half_w = w // 2

        p.fillRect(self.rect(), QColor(G100))

        if t._pix_a is None and t._pix_b is None:
            p.setPen(QColor(G400))
            p.setFont(QFont("Segoe UI", 13))
            p.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Load two PDF files to compare them",
            )
            return

        # Draw page A on left half
        if t._pix_a is not None:
            scaled_a = t._pix_a.scaled(
                half_w - 8,
                h - 20,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x_a = (half_w - scaled_a.width()) // 2
            y_a = (h - scaled_a.height()) // 2
            p.drawPixmap(x_a, y_a, scaled_a)

            # Label A
            p.setPen(QColor(G700))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(4, 16, "A")
        else:
            p.setPen(QColor(G400))
            p.setFont(QFont("Segoe UI", 11))
            p.drawText(
                0,
                0,
                half_w,
                h,
                Qt.AlignmentFlag.AlignCenter,
                "No file A",
            )

        # Draw page B on right half
        if t._pix_b is not None:
            scaled_b = t._pix_b.scaled(
                half_w - 8,
                h - 20,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x_b = half_w + (half_w - scaled_b.width()) // 2
            y_b = (h - scaled_b.height()) // 2
            p.drawPixmap(x_b, y_b, scaled_b)

            # Label B
            p.setPen(QColor(G700))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(half_w + 4, 16, "B")
        else:
            p.setPen(QColor(G400))
            p.setFont(QFont("Segoe UI", 11))
            p.drawText(
                half_w,
                0,
                half_w,
                h,
                Qt.AlignmentFlag.AlignCenter,
                "No file B",
            )

        # Draw diff highlight rects (visual mode)
        if t._diff_rects and t._pix_a is not None:
            scaled_a = t._pix_a.scaled(
                half_w - 8,
                h - 20,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x_a = (half_w - scaled_a.width()) // 2
            y_a = (h - scaled_a.height()) // 2
            sx = scaled_a.width() / t._pix_a.width() if t._pix_a.width() else 1
            sy = scaled_a.height() / t._pix_a.height() if t._pix_a.height() else 1
            pen = QPen(QColor(RED), 2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            for rx, ry, rw, rh in t._diff_rects:
                p.drawRect(
                    int(x_a + rx * sx),
                    int(y_a + ry * sy),
                    int(rw * sx),
                    int(rh * sy),
                )

        # Vertical divider
        pen = QPen(QColor(G300), 1)
        p.setPen(pen)
        p.drawLine(half_w, 0, half_w, h)


class _ExportDiffWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, path_a, path_b, out_path):
        super().__init__()
        self._path_a = path_a
        self._path_b = path_b
        self._out_path = out_path

    def run(self):
        try:
            assert_file_writable(Path(self._out_path))
            mat = fitz.Matrix(1.5, 1.5)
            doc_a = fitz.open(self._path_a)
            doc_b = fitz.open(self._path_b)
            out = fitz.open()
            n = min(doc_a.page_count, doc_b.page_count)
            try:
                for i in range(n):
                    pix_a = doc_a[i].get_pixmap(matrix=mat)
                    page_b_idx = min(i, doc_b.page_count - 1)
                    pix_b = doc_b[page_b_idx].get_pixmap(matrix=mat)
                    page_w = pix_a.width * 2
                    page_h = pix_a.height
                    page = out.new_page(width=page_w / 1.5, height=page_h / 1.5)
                    page.insert_image(
                        fitz.Rect(0, 0, page_w / 1.5 / 2, page_h / 1.5), pixmap=pix_a
                    )
                    page.insert_image(
                        fitz.Rect(page_w / 1.5 / 2, 0, page_w / 1.5, page_h / 1.5),
                        pixmap=pix_b,
                    )
                out.save(self._out_path)
            finally:
                doc_a.close()
                doc_b.close()
                out.close()
            self.finished.emit(self._out_path)
        except PermissionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            logger.exception("worker failed")
            self.failed.emit(str(exc))


class CompareTool(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._doc_a = None
        self._doc_b = None
        self._path_a = ""
        self._path_b = ""
        self._page_idx = 0
        self._total_pages = 0
        self._pix_a: Optional[QPixmap] = None
        self._pix_b: Optional[QPixmap] = None
        self._diff_rects: list = []
        self._mode_id = "visual"
        self._mode_cards: dict[str, _ModeCard] = {}
        self._worker = None

        if fitz is None:
            lay = QVBoxLayout(self)
            lbl = QLabel("Missing dependency.\n\nInstall with:\n  pip install pymupdf")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {G500}; font: 16px;")
            lay.addWidget(lbl)
            return

        self._build_ui()
        self.setAcceptDrops(True)

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
        icon_box.setPixmap(svg_pixmap("file-text", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)

        title_lbl = QLabel("Compare PDFs")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 20px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        # File A
        sec_a = QLabel("FILE A")
        sec_a.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_a)
        lay.addSpacing(8)

        row_a = QHBoxLayout()
        row_a.setSpacing(6)
        row_a.setContentsMargins(0, 0, 0, 0)
        self._path_a_entry = QLineEdit()
        self._path_a_entry.setReadOnly(True)
        self._path_a_entry.setPlaceholderText("No file selected…")
        self._path_a_entry.setFixedHeight(34)
        self._path_a_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
            f" font: 13px; color: {G900}; background: {G100};"
        )
        row_a.addWidget(self._path_a_entry, 1)
        browse_a = _btn("Browse", BLUE, BLUE_HOVER, h=34, w=80)
        browse_a.clicked.connect(lambda: self._browse_file("a"))
        row_a.addWidget(browse_a)
        lay.addLayout(row_a)
        lay.addSpacing(24)

        # File B
        sec_b = QLabel("FILE B")
        sec_b.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_b)
        lay.addSpacing(8)

        row_b = QHBoxLayout()
        row_b.setSpacing(6)
        row_b.setContentsMargins(0, 0, 0, 0)
        self._path_b_entry = QLineEdit()
        self._path_b_entry.setReadOnly(True)
        self._path_b_entry.setPlaceholderText("No file selected…")
        self._path_b_entry.setFixedHeight(34)
        self._path_b_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
            f" font: 13px; color: {G900}; background: {G100};"
        )
        row_b.addWidget(self._path_b_entry, 1)
        browse_b = _btn("Browse", BLUE, BLUE_HOVER, h=34, w=80)
        browse_b.clicked.connect(lambda: self._browse_file("b"))
        row_b.addWidget(browse_b)
        lay.addLayout(row_b)
        lay.addSpacing(24)

        # Compare mode
        sec_mode = QLabel("COMPARE MODE")
        sec_mode.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_mode)
        lay.addSpacing(8)

        for mode in MODES:
            card = _ModeCard(mode, inner)
            self._mode_cards[mode["id"]] = card
            lay.addWidget(card)
            lay.addSpacing(8)

        self._mode_cards["visual"].set_selected(True)

        lay.addSpacing(24)

        # Sensitivity (visual mode only)
        self._sensitivity_widget = QWidget()
        self._sensitivity_widget.setStyleSheet("background: transparent;")
        sens_v = QVBoxLayout(self._sensitivity_widget)
        sens_v.setContentsMargins(0, 0, 0, 0)
        sens_v.setSpacing(6)

        sec_sens = QLabel("SENSITIVITY")
        sec_sens.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        sens_v.addWidget(sec_sens)

        slider_row = QHBoxLayout()
        slider_row.setSpacing(10)
        slider_row.setContentsMargins(0, 0, 0, 0)

        self._threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self._threshold_slider.setRange(1, 50)
        self._threshold_slider.setValue(10)
        self._threshold_slider.setStyleSheet(
            f"QSlider::groove:horizontal {{ height: 4px; background: {G200};"
            f" border-radius: 2px; }}"
            f" QSlider::handle:horizontal {{ background: {BLUE}; border: none;"
            f" width: 14px; height: 14px; border-radius: 7px; margin: -5px 0; }}"
            f" QSlider::sub-page:horizontal {{ background: {BLUE}; border-radius: 2px; }}"
        )
        slider_row.addWidget(self._threshold_slider, 1)

        self._threshold_lbl = QLabel("Threshold: 10")
        self._threshold_lbl.setFixedWidth(90)
        self._threshold_lbl.setStyleSheet(
            f"color: {G700}; font: 12px; background: transparent; border: none;"
        )
        slider_row.addWidget(self._threshold_lbl)
        sens_v.addLayout(slider_row)

        sens_hint = QLabel("Lower = more sensitive to small changes.")
        sens_hint.setStyleSheet(
            f"color: {G500}; font: 11px; background: transparent; border: none;"
        )
        sens_v.addWidget(sens_hint)
        lay.addWidget(self._sensitivity_widget)

        self._threshold_slider.valueChanged.connect(
            lambda v: self._threshold_lbl.setText(f"Threshold: {v}")
        )

        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # Bottom action bar
        bottom = QWidget()
        bottom.setStyleSheet(f"background: {WHITE}; border-top: 1px solid {G200};")
        bot_lay = QVBoxLayout(bottom)
        bot_lay.setContentsMargins(24, 16, 24, 20)
        bot_lay.setSpacing(8)

        export_row = QHBoxLayout()
        export_row.setSpacing(8)
        export_row.setContentsMargins(0, 0, 0, 0)
        self._export_chk = QCheckBox("Export diff PDF")
        self._export_chk.setChecked(True)
        self._export_chk.setStyleSheet(
            f"color: {G700}; font: 12px; background: transparent;"
        )
        export_row.addWidget(self._export_chk)
        bot_lay.addLayout(export_row)

        out_row = QHBoxLayout()
        out_row.setSpacing(6)
        self._out_entry = QLineEdit("diff_output.pdf")
        self._out_entry.setFixedHeight(32)
        self._out_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 8px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        out_row.addWidget(self._out_entry, 1)
        bot_lay.addLayout(out_row)

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

        self._compare_btn = _btn("Compare", BLUE, BLUE_HOVER, h=42)
        self._compare_btn.setEnabled(False)
        self._compare_btn.clicked.connect(self._run_compare)
        bot_lay.addWidget(self._compare_btn)

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
        tb.setSpacing(8)

        self._prev_btn = QPushButton()
        self._prev_btn.setIcon(
            self.style().standardIcon(self.style().StandardPixmap.SP_ArrowLeft)
        )
        self._prev_btn.setFixedSize(30, 30)
        self._prev_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {G200};"
            f" border-radius: 4px; }}"
            f" QPushButton:hover {{ background: {G100}; }}"
            f" QPushButton:disabled {{ color: {G300}; }}"
        )
        self._prev_btn.clicked.connect(self._prev_page)
        self._prev_btn.setEnabled(False)
        tb.addWidget(self._prev_btn)

        self._page_lbl = QLabel("No files loaded")
        self._page_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._page_lbl)

        self._next_btn = QPushButton()
        self._next_btn.setIcon(
            self.style().standardIcon(self.style().StandardPixmap.SP_ArrowRight)
        )
        self._next_btn.setFixedSize(30, 30)
        self._next_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {G200};"
            f" border-radius: 4px; }}"
            f" QPushButton:hover {{ background: {G100}; }}"
            f" QPushButton:disabled {{ color: {G300}; }}"
        )
        self._next_btn.clicked.connect(self._next_page)
        self._next_btn.setEnabled(False)
        tb.addWidget(self._next_btn)

        tb.addStretch()

        a_lbl = QLabel("A")
        a_lbl.setFixedWidth(20)
        a_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        a_lbl.setStyleSheet(
            f"color: {BLUE}; font: bold 13px; background: transparent; border: none;"
        )
        tb.addWidget(a_lbl)

        tb.addStretch()

        b_lbl = QLabel("B")
        b_lbl.setFixedWidth(20)
        b_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b_lbl.setStyleSheet(
            f"color: {BLUE}; font: bold 13px; background: transparent; border: none;"
        )
        tb.addWidget(b_lbl)

        v.addWidget(toolbar)

        # Canvas / text diff area (stacked)
        from PySide6.QtWidgets import QStackedWidget

        self._content_stack = QStackedWidget()

        # Index 0: visual canvas
        self._canvas = _CompareCanvas(self)
        self._content_stack.addWidget(self._canvas)

        # Index 1: text diff (splitter with two QTextEdits)
        text_container = QWidget()
        text_container.setStyleSheet(f"background: {WHITE};")
        tc_h = QHBoxLayout(text_container)
        tc_h.setContentsMargins(0, 0, 0, 0)
        tc_h.setSpacing(0)

        self._text_a = QTextEdit()
        self._text_a.setReadOnly(True)
        self._text_a.setStyleSheet(
            f"border: none; border-right: 1px solid {G200};"
            f" font: 12px 'Courier New'; background: {WHITE};"
        )
        tc_h.addWidget(self._text_a, 1)

        self._text_b = QTextEdit()
        self._text_b.setReadOnly(True)
        self._text_b.setStyleSheet(
            f"border: none; font: 12px 'Courier New'; background: {WHITE};"
        )
        tc_h.addWidget(self._text_b, 1)

        self._content_stack.addWidget(text_container)

        v.addWidget(self._content_stack, 1)
        return right

    def _select_mode(self, mode_id: str):
        self._mode_id = mode_id
        for mid, card in self._mode_cards.items():
            card.set_selected(mid == mode_id)
        self._sensitivity_widget.setVisible(mode_id == "visual")
        if mode_id == "visual":
            self._content_stack.setCurrentIndex(0)
        else:
            self._content_stack.setCurrentIndex(1)

    def _browse_file(self, which: str):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if path:
            self._load_file(which, path)

    def _load_file(self, which: str, path: str):
        try:
            doc = fitz.open(path)
        except Exception as exc:
            logger.exception("could not open pdf")
            QMessageBox.warning(self, "Error", f"Could not open PDF:\n{exc}")
            return

        if which == "a":
            if self._doc_a is not None:
                try:
                    self._doc_a.close()
                except RuntimeError:
                    pass
            self._doc_a = doc
            self._path_a = path
            self._path_a_entry.setText(os.path.basename(path))
        else:
            if self._doc_b is not None:
                try:
                    self._doc_b.close()
                except RuntimeError:
                    pass
            self._doc_b = doc
            self._path_b = path
            self._path_b_entry.setText(os.path.basename(path))

        if self._doc_a is not None and self._doc_b is not None:
            self._total_pages = min(self._doc_a.page_count, self._doc_b.page_count)
            self._page_idx = 0
            self._compare_btn.setEnabled(True)
            self._update_page_label()

        self._status_lbl.setText("")

    def _update_page_label(self):
        if self._total_pages > 0:
            self._page_lbl.setText(f"Page {self._page_idx + 1} / {self._total_pages}")
            self._prev_btn.setEnabled(self._page_idx > 0)
            self._next_btn.setEnabled(self._page_idx < self._total_pages - 1)
        else:
            self._page_lbl.setText("No files loaded")
            self._prev_btn.setEnabled(False)
            self._next_btn.setEnabled(False)

    def _prev_page(self):
        if self._page_idx > 0:
            self._page_idx -= 1
            self._update_page_label()
            self._refresh_view()

    def _next_page(self):
        if self._page_idx < self._total_pages - 1:
            self._page_idx += 1
            self._update_page_label()
            self._refresh_view()

    def _refresh_view(self):
        if self._doc_a is None or self._doc_b is None:
            return
        if self._mode_id == "visual":
            self._render_visual()
        else:
            self._render_text_diff()

    def _render_visual(self):
        mat = fitz.Matrix(1.5, 1.5)
        try:
            pix_a = self._doc_a[self._page_idx].get_pixmap(matrix=mat)
            page_b_idx = min(self._page_idx, self._doc_b.page_count - 1)
            pix_b = self._doc_b[page_b_idx].get_pixmap(matrix=mat)
        except Exception as e:
            self._status_lbl.setText(f"Render error: {e}")
            return

        self._pix_a = _fitz_pix_to_qpixmap(pix_a)
        self._pix_b = _fitz_pix_to_qpixmap(pix_b)

        threshold = self._threshold_slider.value()
        self._diff_rects = self._compute_diff_rects(pix_a, pix_b, threshold)
        self._canvas.update()

    def _compute_diff_rects(self, pix_a, pix_b, threshold: int) -> list:
        try:
            samples_a = bytearray(pix_a.samples)
            samples_b = bytearray(pix_b.samples)
        except Exception:
            return []

        w = min(pix_a.width, pix_b.width)
        h = min(pix_a.height, pix_b.height)
        n_a = pix_a.n
        n_b = pix_b.n

        diff_pixels: list[tuple[int, int]] = []

        for py in range(h):
            for px in range(w):
                i_a = (py * pix_a.width + px) * n_a
                i_b = (py * pix_b.width + px) * n_b
                if i_a + 2 >= len(samples_a) or i_b + 2 >= len(samples_b):
                    continue
                diff_val = max(
                    abs(int(samples_a[i_a]) - int(samples_b[i_b])),
                    abs(int(samples_a[i_a + 1]) - int(samples_b[i_b + 1])),
                    abs(int(samples_a[i_a + 2]) - int(samples_b[i_b + 2])),
                )
                if diff_val > threshold:
                    diff_pixels.append((px, py))

        if not diff_pixels:
            return []

        # Group nearby pixels into bounding box regions (simple: one bbox over all diffs)
        min_y = min(p[1] for p in diff_pixels)
        max_y = max(p[1] for p in diff_pixels)

        # Split into rough bands to avoid one giant rectangle
        rects = []
        band_h = max(1, (max_y - min_y) // 8 + 1)
        band_y = min_y
        while band_y <= max_y:
            band_end = min(band_y + band_h, max_y + 1)
            band_pixels = [p for p in diff_pixels if band_y <= p[1] < band_end]
            if band_pixels:
                bx0 = min(p[0] for p in band_pixels)
                bx1 = max(p[0] for p in band_pixels)
                rects.append((bx0, band_y, bx1 - bx0 + 1, band_end - band_y))
            band_y = band_end

        return rects

    def _render_text_diff(self):
        try:
            words_a = self._doc_a[self._page_idx].get_text("words")
            page_b_idx = min(self._page_idx, self._doc_b.page_count - 1)
            words_b = self._doc_b[page_b_idx].get_text("words")
        except Exception as e:
            self._status_lbl.setText(f"Text extraction error: {e}")
            return

        text_a = [w[4] for w in words_a]
        text_b = [w[4] for w in words_b]

        matcher = difflib.SequenceMatcher(None, text_a, text_b)
        opcodes = matcher.get_opcodes()

        html_a = []
        html_b = []

        for tag, i1, i2, j1, j2 in opcodes:
            chunk_a = " ".join(text_a[i1:i2])
            chunk_b = " ".join(text_b[j1:j2])
            if tag == "equal":
                html_a.append(f"<span>{chunk_a} </span>")
                html_b.append(f"<span>{chunk_b} </span>")
            elif tag == "delete":
                html_a.append(
                    f'<span style="background:#FEE2E2; color:#B91C1C;">{chunk_a} </span>'
                )
            elif tag == "insert":
                html_b.append(
                    f'<span style="background:#D1FAE5; color:#065F46;">{chunk_b} </span>'
                )
            elif tag == "replace":
                html_a.append(
                    f'<span style="background:#FEE2E2; color:#B91C1C;">{chunk_a} </span>'
                )
                html_b.append(
                    f'<span style="background:#D1FAE5; color:#065F46;">{chunk_b} </span>'
                )

        self._text_a.setHtml("".join(html_a))
        self._text_b.setHtml("".join(html_b))

    def _run_compare(self):
        if self._doc_a is None or self._doc_b is None:
            QMessageBox.warning(
                self, "Missing Files", "Please load both PDF files first."
            )
            return

        self._compare_btn.setEnabled(False)
        self._progress.setValue(0)
        self._progress.show()
        self._status_lbl.setText("Comparing…")

        try:
            self._total_pages = min(self._doc_a.page_count, self._doc_b.page_count)
            self._page_idx = 0
            self._update_page_label()

            if self._mode_id == "visual":
                self._content_stack.setCurrentIndex(0)
                self._render_visual()
            else:
                self._content_stack.setCurrentIndex(1)
                self._render_text_diff()

            self._progress.setValue(50)

            if self._export_chk.isChecked():
                self._export_diff_pdf()
                return  # worker will re-enable button and update status

            self._progress.setValue(100)
            n_a = self._doc_a.page_count
            n_b = self._doc_b.page_count
            self._status_lbl.setText(
                f"Done. File A: {n_a} page{'s' if n_a != 1 else ''},"
                f" File B: {n_b} page{'s' if n_b != 1 else ''}."
            )
            self._compare_btn.setEnabled(True)
            self._progress.hide()

        except Exception as exc:
            logger.exception("compare failed")
            QMessageBox.critical(self, "Compare failed", str(exc))
            self._status_lbl.setText("Compare failed.")
            self._compare_btn.setEnabled(True)
            self._progress.hide()

    def _export_diff_pdf(self):
        out_name = self._out_entry.text().strip() or "diff_output.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        base_dir = str(Path(self._path_a).parent) if self._path_a else ""
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Diff PDF",
            os.path.join(base_dir, out_name) if base_dir else out_name,
            "PDF Files (*.pdf)",
        )
        if not out_path:
            self._compare_btn.setEnabled(True)
            self._progress.hide()
            return

        self._worker = _ExportDiffWorker(self._path_a, self._path_b, out_path)
        self._worker.finished.connect(self._on_save_done)
        self._worker.failed.connect(self._on_save_failed)
        self._worker.start()

    def _on_save_done(self, out_path: str):
        self._status_lbl.setText(f"Saved: {Path(out_path).name}")
        self._status_lbl.setStyleSheet(
            f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
        )
        self._compare_btn.setEnabled(True)
        self._progress.hide()

    def _on_save_failed(self, msg: str):
        QMessageBox.critical(self, "Save failed", msg)
        self._status_lbl.setText("Save failed.")
        self._compare_btn.setEnabled(True)
        self._progress.hide()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = [
            u.toLocalFile()
            for u in event.mimeData().urls()
            if u.toLocalFile().lower().endswith(".pdf")
        ]
        if len(urls) >= 1 and self._doc_a is None:
            self._load_file("a", urls[0])
            if len(urls) >= 2:
                self._load_file("b", urls[1])
        elif len(urls) >= 1 and self._doc_b is None:
            self._load_file("b", urls[0])

    def cleanup(self):
        if self._doc_a is not None:
            try:
                self._doc_a.close()
            except RuntimeError:
                pass
            self._doc_a = None
        if self._doc_b is not None:
            try:
                self._doc_b.close()
            except RuntimeError:
                pass
            self._doc_b = None
