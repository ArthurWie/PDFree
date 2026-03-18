"""OCR Tool – add a searchable text layer to scanned PDFs.

PySide6. Requires ocrmypdf (and Tesseract). Loaded by main.py.
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
    RED,
)
from icons import svg_pixmap

try:
    import ocrmypdf as _ocrmypdf
    _HAS_OCR = True
except ImportError:
    _HAS_OCR = False

LANGUAGES = [
    ("English",    "eng"),
    ("French",     "fra"),
    ("German",     "deu"),
    ("Spanish",    "spa"),
    ("Portuguese", "por"),
    ("Italian",    "ita"),
    ("Dutch",      "nld"),
    ("Chinese (Simplified)", "chi_sim"),
    ("Japanese",   "jpn"),
    ("Arabic",     "ara"),
]


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


def _combo(options):
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


def _checkbox(text):
    cb = QCheckBox(text)
    cb.setStyleSheet(
        f"color: {G700}; font: 13px; background: transparent; border: none;"
    )
    return cb


# ===========================================================================
# Worker thread
# ===========================================================================


class _OCRWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, pdf_path, out_path, lang, deskew, force_ocr, skip_text):
        super().__init__()
        self._pdf_path = pdf_path
        self._out_path = out_path
        self._lang = lang
        self._deskew = deskew
        self._force_ocr = force_ocr
        self._skip_text = skip_text

    def run(self):
        try:
            kwargs = dict(
                input_file=self._pdf_path,
                output_file=self._out_path,
                language=self._lang,
                deskew=self._deskew,
                force_ocr=self._force_ocr,
                skip_text=self._skip_text,
                progress_bar=False,
            )
            _ocrmypdf.ocr(**kwargs)
            self.finished.emit(self._out_path)
        except Exception as exc:
            self.failed.emit(str(exc))


# ===========================================================================
# OCRTool
# ===========================================================================


class OCRTool(QWidget):
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
        icon_box.setPixmap(svg_pixmap("scan-line", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet("background: #DBEAFE; border-radius: 8px;")
        title_row.addWidget(icon_box)
        title_lbl = QLabel("OCR PDF")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 18px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        if not _HAS_OCR:
            warn = QFrame()
            warn.setStyleSheet(
                "background: #FEF3C7; border: 1px solid #FCD34D; border-radius: 8px;"
            )
            wl = QVBoxLayout(warn)
            wl.setContentsMargins(16, 12, 16, 12)
            wl.setSpacing(4)
            wt = QLabel("ocrmypdf not installed")
            wt.setStyleSheet(
                "color: #92400E; font: bold 13px; background: transparent; border: none;"
            )
            wl.addWidget(wt)
            ws = QLabel("pip install ocrmypdf")
            ws.setStyleSheet(
                "color: #78350F; font: 12px; font-family: monospace;"
                " background: transparent; border: none;"
            )
            wl.addWidget(ws)
            wt2 = QLabel("Also requires Tesseract OCR installed on your system.")
            wt2.setWordWrap(True)
            wt2.setStyleSheet(
                "color: #78350F; font: 12px; background: transparent; border: none;"
            )
            wl.addWidget(wt2)
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

        # Language
        lay.addWidget(_section("LANGUAGE"))
        lay.addSpacing(8)
        self._lang_combo = _combo([name for name, _ in LANGUAGES])
        lay.addWidget(self._lang_combo)
        lay.addSpacing(24)

        # Options
        lay.addWidget(_section("OPTIONS"))
        lay.addSpacing(8)
        self._deskew_cb = _checkbox("Deskew (straighten scanned pages)")
        self._deskew_cb.setChecked(True)
        lay.addWidget(self._deskew_cb)
        lay.addSpacing(8)
        self._force_cb = _checkbox("Force OCR (re-OCR pages that already have text)")
        lay.addWidget(self._force_cb)
        lay.addSpacing(8)
        self._skip_cb = _checkbox("Skip pages that already have text")
        self._skip_cb.setChecked(True)
        lay.addWidget(self._skip_cb)

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
        self._out_entry.setPlaceholderText("output_ocr.pdf")
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

        self._run_btn = _btn("Run OCR", GREEN, GREEN_HOVER, h=42)
        self._run_btn.setEnabled(False)
        self._run_btn.clicked.connect(self._start_ocr)
        bot.addWidget(self._run_btn)

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
        lbl = QLabel("OCR PDF")
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

        # How it works
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
            "Load a scanned PDF (pages are images with no selectable text).",
            "Choose the document language for better recognition accuracy.",
            "Enable Deskew to straighten tilted scanned pages.",
            "Click Run OCR — the result is a searchable, copy-paste-able PDF.",
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

        # Requirements card
        req_card = QFrame()
        req_card.setStyleSheet(
            "background: #F0FDF4; border: 1px solid #86EFAC; border-radius: 12px;"
        )
        req_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        rc = QVBoxLayout(req_card)
        rc.setContentsMargins(24, 16, 24, 16)
        rc.setSpacing(4)
        req_title = QLabel("Requirements")
        req_title.setStyleSheet(
            "color: #14532D; font: bold 13px; background: transparent; border: none;"
        )
        rc.addWidget(req_title)
        req_body = QLabel(
            "Requires ocrmypdf (pip install ocrmypdf) and "
            "Tesseract OCR installed on your system. "
            "On Windows: install Tesseract from UB Mannheim's installer. "
            "On macOS: brew install tesseract."
        )
        req_body.setWordWrap(True)
        req_body.setStyleSheet(
            "color: #166534; font: 12px; background: transparent; border: none;"
        )
        rc.addWidget(req_body)
        cl.addWidget(req_card)
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
        self._out_entry.setText(f"{Path(path).stem}_ocr.pdf")
        self._run_btn.setEnabled(_HAS_OCR)

    # -----------------------------------------------------------------------
    # Run OCR
    # -----------------------------------------------------------------------

    def _start_ocr(self):
        if not self._pdf_path:
            return
        if not _HAS_OCR:
            QMessageBox.warning(self, "Missing dependency",
                                "Install ocrmypdf:\n  pip install ocrmypdf\n\n"
                                "Also install Tesseract OCR on your system.")
            return

        out_name = self._out_entry.text().strip() or f"{Path(self._pdf_path).stem}_ocr.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        default_dir = str(Path(self._pdf_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save OCR PDF",
            str(Path(default_dir) / out_name),
            "PDF Files (*.pdf)",
        )
        if not out_path:
            return

        lang_idx = self._lang_combo.currentIndex()
        lang_code = LANGUAGES[lang_idx][1]
        deskew = self._deskew_cb.isChecked()
        force_ocr = self._force_cb.isChecked()
        skip_text = self._skip_cb.isChecked() and not force_ocr

        self._run_btn.setEnabled(False)
        self._status_lbl.setText("Running OCR — this may take a while...")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )

        self._worker = _OCRWorker(
            self._pdf_path, out_path, lang_code, deskew, force_ocr, skip_text
        )
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_finished(self, out_path):
        self._status_lbl.setText(f"Saved: {Path(out_path).name}")
        self._status_lbl.setStyleSheet(
            f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
        )
        self._run_btn.setEnabled(True)

    def _on_failed(self, msg):
        QMessageBox.critical(self, "OCR failed", msg)
        self._status_lbl.setText("OCR failed.")
        self._status_lbl.setStyleSheet(
            f"color: {RED}; font: 12px; border: none; background: transparent;"
        )
        self._run_btn.setEnabled(True)

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
