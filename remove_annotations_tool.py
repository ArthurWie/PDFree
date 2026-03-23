"""Remove Annotations Tool – strip all annotations from a PDF.

PySide6. Loaded by main.py when the user clicks "Remove Annotations".
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

try:
    import fitz
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)


class _RemoveAnnotationsWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, pdf_path, out_path, parent=None):
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._out_path = out_path

    def run(self):
        try:
            assert_file_writable(Path(self._out_path))
            backup_original(Path(self._pdf_path))
            doc = fitz.open(self._pdf_path)
            for page in doc:
                annots = list(page.annots())
                for annot in annots:
                    page.delete_annot(annot)
            doc.save(self._out_path, garbage=3, deflate=True)
            doc.close()
            self.finished.emit(self._out_path)
        except PermissionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))


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


# ===========================================================================
# RemoveAnnotationsTool
# ===========================================================================


class RemoveAnnotationsTool(QWidget):
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
        self._annot_count = 0
        self._annot_types = {}
        self._worker = None

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
        icon_box.setPixmap(svg_pixmap("eraser", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)

        title_lbl = QLabel("Remove Annotations")
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
        lay.addWidget(self._build_drop_zone())
        lay.addSpacing(8)

        self._file_lbl = QLabel("No file loaded")
        self._file_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        self._file_lbl.setWordWrap(True)
        lay.addWidget(self._file_lbl)
        lay.addSpacing(24)

        # Annotation summary section
        lay.addWidget(_section("ANNOTATION SUMMARY"))
        lay.addSpacing(8)

        self._summary_card = QFrame()
        self._summary_card.setStyleSheet(
            f"background: {G100}; border: 1px solid {G200}; border-radius: 8px;"
        )
        summary_lay = QVBoxLayout(self._summary_card)
        summary_lay.setContentsMargins(16, 14, 16, 14)
        summary_lay.setSpacing(4)

        self._count_lbl = QLabel("—")
        self._count_lbl.setStyleSheet(
            f"color: {G900}; font: bold 28px; background: transparent; border: none;"
        )
        summary_lay.addWidget(self._count_lbl)

        self._count_sub = QLabel("Load a PDF to see annotation summary.")
        self._count_sub.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        self._count_sub.setWordWrap(True)
        summary_lay.addWidget(self._count_sub)

        self._pages_lbl = QLabel("")
        self._pages_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        summary_lay.addWidget(self._pages_lbl)

        lay.addWidget(self._summary_card)

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
        self._out_entry.setPlaceholderText("output_clean.pdf")
        self._out_entry.setFixedHeight(36)
        self._out_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        bot.addWidget(self._out_entry)

        self._result_lbl = QLabel("")
        self._result_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )
        bot.addWidget(self._result_lbl)

        self._save_btn = _btn("Remove Annotations & Save", GREEN, GREEN_HOVER, h=42)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save)
        bot.addWidget(self._save_btn)

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
        self._toolbar_lbl = QLabel("No file loaded")
        self._toolbar_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._toolbar_lbl)
        tb.addStretch()
        v.addWidget(toolbar)

        content = QWidget()
        content.setStyleSheet(f"background: {G100};")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(32, 32, 32, 32)
        cl.setSpacing(16)

        # Annotation types card
        types_card = QFrame()
        types_card.setStyleSheet(
            f"background: {WHITE}; border: 1px solid {G200}; border-radius: 12px;"
        )
        types_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        tc = QVBoxLayout(types_card)
        tc.setContentsMargins(24, 20, 24, 20)
        tc.setSpacing(8)

        types_title = QLabel("Annotation Types")
        types_title.setStyleSheet(
            f"color: {G900}; font: bold 14px; background: transparent; border: none;"
        )
        tc.addWidget(types_title)

        self._types_container = QVBoxLayout()
        self._types_container.setSpacing(4)
        self._types_placeholder = QLabel("Load a PDF to see annotation breakdown.")
        self._types_placeholder.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        self._types_container.addWidget(self._types_placeholder)
        tc.addLayout(self._types_container)

        cl.addWidget(types_card)

        # How it works card
        info_card = QFrame()
        info_card.setStyleSheet(
            f"background: {WHITE}; border: 1px solid {G200}; border-radius: 12px;"
        )
        info_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        ic = QVBoxLayout(info_card)
        ic.setContentsMargins(24, 20, 24, 20)
        ic.setSpacing(8)

        tip_title = QLabel("How it works")
        tip_title.setStyleSheet(
            f"color: {G900}; font: bold 14px; background: transparent; border: none;"
        )
        ic.addWidget(tip_title)

        steps = [
            "Load a PDF — annotation counts are shown instantly.",
            "Review which annotation types will be removed.",
            "Save a clean copy with all annotations stripped.",
        ]
        for step in steps:
            row = QHBoxLayout()
            row.setContentsMargins(0, 4, 0, 0)
            row.setSpacing(10)
            dot = QLabel("•")
            dot.setFixedWidth(12)
            dot.setStyleSheet(
                f"color: {BLUE}; font: bold 14px; background: transparent; border: none;"
            )
            row.addWidget(dot)
            txt = QLabel(step)
            txt.setWordWrap(True)
            txt.setStyleSheet(
                f"color: {G700}; font: 12px; background: transparent; border: none;"
            )
            row.addWidget(txt, 1)
            ic.addLayout(row)

        cl.addWidget(info_card)
        cl.addStretch()
        v.addWidget(content, 1)
        return right

    def _build_drop_zone(self) -> QFrame:
        dz = QFrame()
        dz.setFixedHeight(56)
        dz.setStyleSheet(
            f"background: {G100};"
            f" border: 2px dashed {G200}; border-radius: 12px;"
        )
        h = QHBoxLayout(dz)
        h.setContentsMargins(10, 0, 10, 0)
        h.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(svg_pixmap("file-text", G400, 20))
        ic.setStyleSheet("border: none; background: transparent;")
        h.addWidget(ic)
        lbl = QLabel("Drop PDF here or")
        lbl.setStyleSheet(
            f"color: {G500}; font: 13px; border: none; background: transparent;"
        )
        h.addWidget(lbl)
        btn = _btn("Browse", BLUE, BLUE_HOVER, h=32, w=80)
        btn.clicked.connect(self._browse)
        h.addWidget(btn)
        h.addStretch()
        return dz

    # -----------------------------------------------------------------------
    # File loading
    # -----------------------------------------------------------------------

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        try:
            doc = fitz.open(path)
            total = 0
            annot_types = {}
            for page in doc:
                for annot in page.annots():
                    total += 1
                    type_name = annot.type[1]
                    annot_types[type_name] = annot_types.get(type_name, 0) + 1
            page_count = doc.page_count
            doc.close()
        except Exception as exc:
            logger.exception("could not open pdf")
            QMessageBox.warning(self, "Error", f"Could not open PDF:\n{exc}")
            return

        self._pdf_path = path
        self._annot_count = total
        self._annot_types = annot_types

        name = Path(path).name
        self._file_lbl.setText(name)
        self._toolbar_lbl.setText(name)
        self._out_entry.setText(f"{Path(path).stem}_clean.pdf")
        self._result_lbl.setText("")

        self._count_lbl.setText(str(total))
        if total == 0:
            self._count_sub.setText("No annotations found")
            self._count_sub.setStyleSheet(
                f"color: {G500}; font: 12px; background: transparent; border: none;"
            )
            self._pages_lbl.setText("")
            self._save_btn.setEnabled(False)
        else:
            self._count_sub.setText("annotations found")
            self._count_sub.setStyleSheet(
                f"color: {G700}; font: 12px; background: transparent; border: none;"
            )
            self._pages_lbl.setText(f"(across {page_count} pages)")
            self._save_btn.setEnabled(True)

        self._update_types_list()

    def _update_types_list(self):
        while self._types_container.count():
            item = self._types_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._annot_types:
            placeholder = QLabel("Load a PDF to see annotation breakdown.")
            placeholder.setStyleSheet(
                f"color: {G500}; font: 12px; background: transparent; border: none;"
            )
            self._types_container.addWidget(placeholder)
            return

        for type_name, count in sorted(self._annot_types.items()):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(0)
            name_lbl = QLabel(f"{type_name}:")
            name_lbl.setStyleSheet(
                f"color: {G700}; font: 13px; background: transparent; border: none;"
            )
            row.addWidget(name_lbl)
            row.addStretch()
            count_lbl = QLabel(str(count))
            count_lbl.setStyleSheet(
                f"color: {G900}; font: bold 13px; background: transparent; border: none;"
            )
            row.addWidget(count_lbl)
            wrapper = QWidget()
            wrapper.setStyleSheet("background: transparent;")
            wrapper.setLayout(row)
            self._types_container.addWidget(wrapper)

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------

    def _save(self):
        out_name = self._out_entry.text().strip() or "clean.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        default_dir = str(Path(self._pdf_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save Clean PDF",
            str(Path(default_dir) / out_name),
            "PDF Files (*.pdf)",
        )
        if not out_path:
            return

        self._save_btn.setEnabled(False)
        self._result_lbl.setText("Saving...")

        self._worker = _RemoveAnnotationsWorker(self._pdf_path, out_path)
        self._worker.finished.connect(self._on_save_done)
        self._worker.failed.connect(self._on_save_failed)
        self._worker.start()

    def _on_save_done(self, out_path: str):
        self._result_lbl.setText(f"Saved: {Path(out_path).name}")
        self._result_lbl.setStyleSheet(
            f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
        )
        self._save_btn.setEnabled(True)

    def _on_save_failed(self, msg: str):
        logger.error("save failed: %s", msg)
        QMessageBox.critical(self, "Save failed", msg)
        self._result_lbl.setText("Save failed.")
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
        pass
