"""Flatten Tool – bake annotations/form fields and scrub interactive elements from a PDF.

PySide6. Loaded by main.py when the user clicks "Flatten".
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
    QCheckBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import (
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
    G400,
    G500,
    G700,
    G900,
    WHITE,
    EMERALD,
    BLUE_MED,
)
from icons import svg_pixmap

try:
    import fitz
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)


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
    border_s = f"border: 1px solid {G200};" if border else "border: none;"  # noqa: E501 — using G200 from compress_tool pattern; G300 not imported here but G200 matches drop zone
    b.setStyleSheet(f"""
        QPushButton {{
            background: {bg}; color: {text_color};
            {border_s} border-radius: 6px;
            font: {"bold " if bg in (BLUE, GREEN) else ""}13px;
            padding: 0 12px;
        }}
        QPushButton:hover {{ background: {hover}; }}
        QPushButton:disabled {{ color: {G400}; background: {G100}; border-color: {G200}; }}
    """)
    return b


class _FlattenWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, pdf_path, out_path, annots, js, links):
        super().__init__()
        self._pdf_path = pdf_path
        self._out_path = out_path
        self._annots = annots
        self._js = js
        self._links = links

    def run(self):
        try:
            assert_file_writable(Path(self._out_path))
            backup_original(Path(self._pdf_path))
            doc = fitz.open(self._pdf_path)
            try:
                if self._annots:
                    doc.bake(annots=True, widgets=True)
                if self._js or self._links:
                    doc.scrub(javascript=self._js, links=self._links)
                doc.save(self._out_path, garbage=3, deflate=True)
            finally:
                doc.close()
            self.finished.emit(self._out_path)
        except PermissionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            logger.exception("worker failed")
            self.failed.emit(str(exc))


class FlattenTool(QWidget):
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
        self._original_size = 0
        self._worker = None

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
        icon_box.setPixmap(svg_pixmap("minimize", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)

        title_lbl = QLabel("Flatten PDF")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 20px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        # Source file section
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

        # Options section
        sec_opts = QLabel("OPTIONS")
        sec_opts.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_opts)
        lay.addSpacing(10)

        chk_style = f"color: {G900}; font: 13px; background: transparent;"

        self._chk_annots = QCheckBox("Flatten annotations and form fields")
        self._chk_annots.setChecked(True)
        self._chk_annots.setStyleSheet(chk_style)
        lay.addWidget(self._chk_annots)
        lay.addSpacing(8)

        self._chk_js = QCheckBox("Remove JavaScript")
        self._chk_js.setChecked(True)
        self._chk_js.setStyleSheet(chk_style)
        lay.addWidget(self._chk_js)
        lay.addSpacing(8)

        self._chk_links = QCheckBox("Remove interactive links")
        self._chk_links.setChecked(False)
        self._chk_links.setStyleSheet(chk_style)
        lay.addWidget(self._chk_links)

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
        self._out_entry.setPlaceholderText("output_flat.pdf")
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

        self._flatten_btn = _btn("Flatten PDF", GREEN, GREEN_HOVER, h=42)
        self._flatten_btn.setEnabled(False)
        self._flatten_btn.clicked.connect(self._flatten)
        bot_lay.addWidget(self._flatten_btn)

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

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        try:
            doc = fitz.open(path)
            page_count = doc.page_count
            annot_count = sum(len(list(doc[i].annots())) for i in range(doc.page_count))
            widget_count = sum(
                len(list(doc[i].widgets())) for i in range(doc.page_count)
            )
            doc.close()
        except Exception as exc:
            logger.exception("could not open pdf")
            QMessageBox.warning(self, "Error", f"Could not open PDF:\n{exc}")
            return

        self._pdf_path = path
        self._original_size = Path(path).stat().st_size
        stem = Path(path).stem
        self._out_entry.setText(f"{stem}_flat.pdf")
        self._flatten_btn.setEnabled(True)
        self._status_lbl.setText("")

        self._toolbar_lbl.setText(Path(path).name)
        self._show_file_info(page_count, annot_count, widget_count)

    def _show_file_info(self, page_count: int, annot_count: int, widget_count: int):
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
        self._add_info_row(card_lay, "Annots", str(annot_count))
        self._add_info_row(card_lay, "Fields", str(widget_count))

        self._info_lay.addWidget(card)
        self._result_card_placeholder = QWidget()
        self._info_lay.addWidget(self._result_card_placeholder)
        self._info_lay.addStretch()

    def _add_info_row(self, parent_lay: QVBoxLayout, label: str, value: str):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label)
        lbl.setFixedWidth(80)
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

    def _flatten(self):
        if not self._pdf_path:
            return

        out_name = self._out_entry.text().strip() or "flattened.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        default_dir = str(Path(self._pdf_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Flattened PDF",
            str(Path(default_dir) / out_name),
            "PDF Files (*.pdf)",
        )
        if not out_path:
            return

        self._progress.setValue(0)
        self._progress.show()
        self._flatten_btn.setEnabled(False)
        self._status_lbl.setText("Flattening...")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )

        self._worker = _FlattenWorker(
            self._pdf_path,
            out_path,
            self._chk_annots.isChecked(),
            self._chk_js.isChecked(),
            self._chk_links.isChecked(),
        )
        self._worker.finished.connect(self._on_save_done)
        self._worker.failed.connect(self._on_save_failed)
        self._worker.start()

    def _on_save_done(self, out_path: str):
        self._status_lbl.setText(f"Saved: {Path(out_path).name}")
        self._status_lbl.setStyleSheet(
            f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
        )
        self._flatten_btn.setEnabled(True)
        self._progress.hide()

    def _on_save_failed(self, msg: str):
        QMessageBox.critical(self, "Save failed", msg)
        self._status_lbl.setText("Save failed.")
        self._flatten_btn.setEnabled(True)
        self._progress.hide()

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
        pass
