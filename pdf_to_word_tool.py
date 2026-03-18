"""PDF to Word Tool – convert a PDF to an editable .docx file.

PySide6. Requires pdf2docx. Loaded by main.py when the user clicks "PDF to Word".
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
    RED,
)
from icons import svg_pixmap

try:
    from pdf2docx import Converter as _PDF2DocxConverter
    _HAS_PDF2DOCX = True
except ImportError:
    _HAS_PDF2DOCX = False


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
# Worker thread
# ===========================================================================


class _ConvertWorker(QThread):
    finished = Signal(str)   # output path on success
    failed = Signal(str)     # error message

    def __init__(self, pdf_path, out_path, start, end):
        super().__init__()
        self._pdf_path = pdf_path
        self._out_path = out_path
        self._start = start
        self._end = end

    def run(self):
        try:
            cv = _PDF2DocxConverter(self._pdf_path)
            cv.convert(self._out_path, start=self._start, end=self._end)
            cv.close()
            self.finished.emit(self._out_path)
        except Exception as exc:
            self.failed.emit(str(exc))


# ===========================================================================
# PDFToWordTool
# ===========================================================================


class PDFToWordTool(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._modified = False
        self._pdf_path = ""
        self._worker = None

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
        icon_box.setStyleSheet("background: #DBEAFE; border-radius: 8px;")
        title_row.addWidget(icon_box)
        title_lbl = QLabel("PDF to Word")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 18px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        if not _HAS_PDF2DOCX:
            warn = QFrame()
            warn.setStyleSheet(
                "background: #FEF3C7; border: 1px solid #FCD34D; border-radius: 8px;"
            )
            wl = QVBoxLayout(warn)
            wl.setContentsMargins(16, 12, 16, 12)
            wl.setSpacing(4)
            wt = QLabel("pdf2docx not installed")
            wt.setStyleSheet(
                "color: #92400E; font: bold 13px; background: transparent; border: none;"
            )
            wl.addWidget(wt)
            ws = QLabel("pip install pdf2docx")
            ws.setStyleSheet(
                "color: #78350F; font: 12px; font-family: monospace;"
                " background: transparent; border: none;"
            )
            wl.addWidget(ws)
            lay.addWidget(warn)
            lay.addSpacing(16)

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

        # Page range (optional)
        lay.addWidget(_section("PAGE RANGE (OPTIONAL)"))
        lay.addSpacing(8)
        range_row = QHBoxLayout()
        range_row.setSpacing(8)
        range_row.setContentsMargins(0, 0, 0, 0)
        from_lbl = QLabel("From:")
        from_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        from_lbl.setFixedWidth(40)
        range_row.addWidget(from_lbl)
        self._from_entry = QLineEdit()
        self._from_entry.setPlaceholderText("1")
        self._from_entry.setFixedHeight(34)
        self._from_entry.setFixedWidth(60)
        self._from_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 8px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        range_row.addWidget(self._from_entry)
        to_lbl = QLabel("To:")
        to_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        to_lbl.setFixedWidth(24)
        range_row.addWidget(to_lbl)
        self._to_entry = QLineEdit()
        self._to_entry.setPlaceholderText("end")
        self._to_entry.setFixedHeight(34)
        self._to_entry.setFixedWidth(60)
        self._to_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 8px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        range_row.addWidget(self._to_entry)
        range_row.addStretch()
        lay.addLayout(range_row)
        lay.addSpacing(6)
        hint = QLabel("Leave blank to convert the full document.")
        hint.setStyleSheet(
            f"color: {G400}; font: 11px; background: transparent; border: none;"
        )
        lay.addWidget(hint)

        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # Bottom bar
        bottom = QWidget()
        bottom.setStyleSheet(f"background: {WHITE}; border-top: 1px solid {G200};")
        bot = QVBoxLayout(bottom)
        bot.setContentsMargins(24, 16, 24, 20)
        bot.setSpacing(10)

        bot.addWidget(_section("OUTPUT FILE"))
        self._out_entry = QLineEdit()
        self._out_entry.setPlaceholderText("output.docx")
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

        self._convert_btn = _btn("Convert to Word", GREEN, GREEN_HOVER, h=42)
        self._convert_btn.setEnabled(False)
        self._convert_btn.clicked.connect(self._start_convert)
        bot.addWidget(self._convert_btn)

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
        lbl = QLabel("PDF to Word")
        lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(lbl)
        tb.addStretch()
        v.addWidget(toolbar)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(32, 32, 32, 32)
        cl.setSpacing(16)

        # How it works card
        tip_card = QFrame()
        tip_card.setStyleSheet(
            f"background: {WHITE}; border: 1px solid {G200}; border-radius: 12px;"
        )
        tip_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        ic = QVBoxLayout(tip_card)
        ic.setContentsMargins(24, 20, 24, 20)
        ic.setSpacing(0)
        tip_title = QLabel("How it works")
        tip_title.setStyleSheet(
            f"color: {G900}; font: bold 14px; background: transparent; border: none;"
        )
        ic.addWidget(tip_title)
        ic.addSpacing(8)
        for step in [
            "Load a PDF file from your computer.",
            "Optionally specify a page range to convert.",
            "Click Convert — a .docx file is saved next to the original.",
            "Open the result in Microsoft Word or LibreOffice.",
        ]:
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

        cl.addWidget(tip_card)

        # Quality note card
        note_card = QFrame()
        note_card.setStyleSheet(
            "background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 12px;"
        )
        note_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        nc = QVBoxLayout(note_card)
        nc.setContentsMargins(24, 16, 24, 16)
        nc.setSpacing(4)
        note_title = QLabel("Conversion quality")
        note_title.setStyleSheet(
            "color: #92400E; font: bold 13px; background: transparent; border: none;"
        )
        nc.addWidget(note_title)
        note_body = QLabel(
            "Text-based PDFs convert well. Scanned PDFs or those with complex "
            "layouts (multi-column, embedded images) may need manual cleanup."
        )
        note_body.setWordWrap(True)
        note_body.setStyleSheet(
            "color: #78350F; font: 12px; background: transparent; border: none;"
        )
        nc.addWidget(note_body)
        cl.addWidget(note_card)
        cl.addStretch()

        v.addWidget(content, 1)
        return right

    # -----------------------------------------------------------------------
    # File loading
    # -----------------------------------------------------------------------

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if path:
            self._load_file(path)

    def _load_file(self, path):
        self._pdf_path = path
        self._file_lbl.setText(Path(path).name)
        self._out_entry.setText(f"{Path(path).stem}.docx")
        self._convert_btn.setEnabled(_HAS_PDF2DOCX)

    # -----------------------------------------------------------------------
    # Convert
    # -----------------------------------------------------------------------

    def _parse_range(self):
        try:
            start = int(self._from_entry.text().strip()) - 1 if self._from_entry.text().strip() else 0
            start = max(0, start)
        except ValueError:
            start = 0
        try:
            end = int(self._to_entry.text().strip()) if self._to_entry.text().strip() else None
        except ValueError:
            end = None
        return start, end

    def _start_convert(self):
        if not self._pdf_path:
            return
        if not _HAS_PDF2DOCX:
            QMessageBox.warning(self, "Missing dependency",
                                "Install pdf2docx:\n  pip install pdf2docx")
            return

        out_name = self._out_entry.text().strip() or f"{Path(self._pdf_path).stem}.docx"
        if not out_name.lower().endswith(".docx"):
            out_name += ".docx"

        default_dir = str(Path(self._pdf_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save Word Document",
            str(Path(default_dir) / out_name),
            "Word Documents (*.docx)",
        )
        if not out_path:
            return

        start, end = self._parse_range()

        self._convert_btn.setEnabled(False)
        self._status_lbl.setText("Converting...")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )

        self._worker = _ConvertWorker(self._pdf_path, out_path, start, end)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_finished(self, out_path):
        self._status_lbl.setText(f"Saved: {Path(out_path).name}")
        self._status_lbl.setStyleSheet(
            f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
        )
        self._convert_btn.setEnabled(True)

    def _on_failed(self, msg):
        QMessageBox.critical(self, "Conversion failed", msg)
        self._status_lbl.setText("Conversion failed.")
        self._status_lbl.setStyleSheet(
            f"color: {RED}; font: 12px; border: none; background: transparent;"
        )
        self._convert_btn.setEnabled(True)

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
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(2000)
