"""Scale Pages Tool – resize all pages in a PDF to a target page size.

PySide6. Loaded by main.py when the user clicks "Scale Pages".
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

MM_TO_PT = 2.83465


class _ScalePagesWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)
    progress = Signal(int)

    def __init__(
        self,
        pdf_path,
        out_path,
        target_w,
        target_h,
        scale_content,
        preserve_aspect,
        parent=None,
    ):
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._out_path = out_path
        self._target_w = target_w
        self._target_h = target_h
        self._scale_content = scale_content
        self._preserve_aspect = preserve_aspect

    def run(self):
        try:
            assert_file_writable(Path(self._out_path))
            backup_original(Path(self._pdf_path))
            src = fitz.open(self._pdf_path)
            out = fitz.open()
            try:
                for i in range(src.page_count):
                    src_page = src[i]
                    new_page = out.new_page(
                        width=self._target_w, height=self._target_h
                    )
                    if self._scale_content:
                        if self._preserve_aspect:
                            src_r = src_page.rect
                            scale = min(
                                self._target_w / src_r.width,
                                self._target_h / src_r.height,
                            )
                            scaled_w = src_r.width * scale
                            scaled_h = src_r.height * scale
                            x0 = (self._target_w - scaled_w) / 2
                            y0 = (self._target_h - scaled_h) / 2
                            target_rect = fitz.Rect(
                                x0, y0, x0 + scaled_w, y0 + scaled_h
                            )
                        else:
                            target_rect = fitz.Rect(
                                0, 0, self._target_w, self._target_h
                            )
                        new_page.show_pdf_page(target_rect, src, i)
                    else:
                        new_page.show_pdf_page(
                            fitz.Rect(0, 0, self._target_w, self._target_h), src, i
                        )
                    self.progress.emit(int((i + 1) / src.page_count * 90))
                out.save(self._out_path, garbage=4, deflate=True)
                self.progress.emit(100)
            finally:
                src.close()
                out.close()
            self.finished.emit(self._out_path)
        except PermissionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            logger.exception("worker failed")
            self.failed.emit(str(exc))

PAGE_SIZES = {
    "A4 Portrait (210×297 mm)": (595.28, 841.89),
    "A4 Landscape (297×210 mm)": (841.89, 595.28),
    "Letter Portrait (216×279 mm)": (612.0, 792.0),
    "Letter Landscape (279×216 mm)": (792.0, 612.0),
    "A3 Portrait (297×420 mm)": (841.89, 1190.55),
    "A3 Landscape (420×297 mm)": (1190.55, 841.89),
    "Custom": None,
}


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 ** 2:.2f} MB"


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


# ===========================================================================
# ScalePagesTool
# ===========================================================================


class ScalePagesTool(QWidget):
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
        icon_box.setPixmap(svg_pixmap("maximize", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)

        title_lbl = QLabel("Scale Pages")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 20px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        # Source file
        lay.addWidget(_section("SOURCE FILE"))
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
        lay.addSpacing(24)

        # Target size
        lay.addWidget(_section("TARGET SIZE"))
        lay.addSpacing(8)
        self._size_combo = _combo(list(PAGE_SIZES.keys()))
        self._size_combo.currentTextChanged.connect(self._on_size_change)
        lay.addWidget(self._size_combo)
        lay.addSpacing(10)

        # Custom size fields (hidden by default)
        self._custom_widget = QWidget()
        self._custom_widget.setStyleSheet("background: transparent;")
        custom_lay = QVBoxLayout(self._custom_widget)
        custom_lay.setContentsMargins(0, 0, 0, 0)
        custom_lay.setSpacing(8)

        w_row = QHBoxLayout()
        w_row.setSpacing(8)
        w_lbl = QLabel("Width (mm)")
        w_lbl.setFixedWidth(80)
        w_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        w_row.addWidget(w_lbl)
        self._custom_w = QLineEdit("210")
        self._custom_w.setFixedHeight(32)
        self._custom_w.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 8px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        w_row.addWidget(self._custom_w, 1)
        custom_lay.addLayout(w_row)

        h_row = QHBoxLayout()
        h_row.setSpacing(8)
        h_lbl = QLabel("Height (mm)")
        h_lbl.setFixedWidth(80)
        h_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        h_row.addWidget(h_lbl)
        self._custom_h = QLineEdit("297")
        self._custom_h.setFixedHeight(32)
        self._custom_h.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 8px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        h_row.addWidget(self._custom_h, 1)
        custom_lay.addLayout(h_row)

        lay.addWidget(self._custom_widget)
        self._custom_widget.hide()
        lay.addSpacing(24)

        # Scale content
        lay.addWidget(_section("SCALE CONTENT"))
        lay.addSpacing(8)

        self._chk_scale = QCheckBox("Scale content to fit")
        self._chk_scale.setChecked(True)
        self._chk_scale.setStyleSheet(
            f"color: {G900}; font: 13px; background: transparent; border: none;"
        )
        self._chk_scale.stateChanged.connect(self._on_scale_changed)
        lay.addWidget(self._chk_scale)
        lay.addSpacing(4)

        self._scale_desc = QLabel(
            "When unchecked, only the page box is resized; content may be clipped."
        )
        self._scale_desc.setWordWrap(True)
        self._scale_desc.setStyleSheet(
            f"color: {G500}; font: 11px; background: transparent; border: none;"
        )
        lay.addWidget(self._scale_desc)
        lay.addSpacing(10)

        self._chk_aspect = QCheckBox("Preserve aspect ratio (add margins)")
        self._chk_aspect.setChecked(True)
        self._chk_aspect.setStyleSheet(
            f"color: {G900}; font: 13px; background: transparent; border: none;"
        )
        lay.addWidget(self._chk_aspect)

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
        self._out_entry.setPlaceholderText("output_scaled.pdf")
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

        self._scale_btn = _btn("Scale Pages", GREEN, GREEN_HOVER, h=42)
        self._scale_btn.setEnabled(False)
        self._scale_btn.clicked.connect(self._scale)
        bot_lay.addWidget(self._scale_btn)

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
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF Files (*.pdf)"
        )
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        try:
            doc = fitz.open(path)
            page_count = doc.page_count
            first_page = doc[0]
            w_pt = first_page.rect.width
            h_pt = first_page.rect.height
            doc.close()
        except Exception as exc:
            logger.exception("could not open pdf")
            QMessageBox.warning(self, "Error", f"Could not open PDF:\n{exc}")
            return

        self._pdf_path = path
        self._original_size = Path(path).stat().st_size
        stem = Path(path).stem
        self._out_entry.setText(f"{stem}_scaled.pdf")
        self._scale_btn.setEnabled(True)
        self._status_lbl.setText("")

        self._toolbar_lbl.setText(Path(path).name)
        self._show_file_info(page_count, w_pt, h_pt)

    def _show_file_info(self, page_count: int, w_pt: float, h_pt: float):
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

        self._add_info_row(card_lay, "File", Path(self._pdf_path).name)
        self._add_info_row(card_lay, "Size", _fmt_size(self._original_size))
        self._add_info_row(card_lay, "Pages", str(page_count))

        w_mm = w_pt / MM_TO_PT
        h_mm = h_pt / MM_TO_PT
        self._add_info_row(card_lay, "Current size", f"{w_mm:.1f} × {h_mm:.1f} mm")

        self._info_lay.addWidget(card)
        self._info_lay.addStretch()

    def _add_info_row(self, parent_lay: QVBoxLayout, label: str, value: str):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label)
        lbl.setFixedWidth(90)
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
    # Controls
    # -----------------------------------------------------------------------

    def _on_size_change(self, text: str):
        self._custom_widget.setVisible(text == "Custom")

    def _on_scale_changed(self, state: int):
        checked = state == Qt.CheckState.Checked.value
        self._chk_aspect.setEnabled(checked)

    # -----------------------------------------------------------------------
    # Scaling
    # -----------------------------------------------------------------------

    def _scale(self):
        if not self._pdf_path:
            return

        out_name = self._out_entry.text().strip() or "scaled.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        default_dir = str(Path(self._pdf_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Scaled PDF",
            str(Path(default_dir) / out_name),
            "PDF Files (*.pdf)",
        )
        if not out_path:
            return

        if self._size_combo.currentText() == "Custom":
            try:
                w_mm = float(self._custom_w.text() or "210")
                h_mm = float(self._custom_h.text() or "297")
            except ValueError as exc:
                QMessageBox.critical(self, "Invalid dimensions", str(exc))
                return
            target_w = w_mm * MM_TO_PT
            target_h = h_mm * MM_TO_PT
        else:
            target_w, target_h = PAGE_SIZES[self._size_combo.currentText()]

        self._progress.setValue(0)
        self._progress.show()
        self._scale_btn.setEnabled(False)
        self._status_lbl.setText("Scaling...")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )

        self._worker = _ScalePagesWorker(
            self._pdf_path,
            out_path,
            target_w,
            target_h,
            self._chk_scale.isChecked(),
            self._chk_aspect.isChecked(),
        )
        self._worker.progress.connect(self._progress.setValue)
        self._worker.finished.connect(self._on_save_done)
        self._worker.failed.connect(self._on_save_failed)
        self._worker.start()

    def _on_save_done(self, _out_path: str):
        self._status_lbl.setText("Done.")
        self._status_lbl.setStyleSheet(
            f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
        )
        self._scale_btn.setEnabled(True)
        self._progress.hide()

    def _on_save_failed(self, msg: str):
        logger.error("scaling failed: %s", msg)
        QMessageBox.critical(self, "Scaling failed", msg)
        self._status_lbl.setText("Scaling failed.")
        self._status_lbl.setStyleSheet(
            "color: red; font: 12px; border: none; background: transparent;"
        )
        self._scale_btn.setEnabled(True)
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
