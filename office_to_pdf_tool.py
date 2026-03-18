"""Office to PDF Tool – convert Word, PowerPoint, and Excel files to PDF.

PySide6. Uses LibreOffice headless. Loaded by main.py.
"""

import os
import shutil
import subprocess
import tempfile
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

SUPPORTED_EXT = {
    ".docx": "Word",
    ".doc":  "Word",
    ".pptx": "PowerPoint",
    ".ppt":  "PowerPoint",
    ".xlsx": "Excel",
    ".xls":  "Excel",
    ".odt":  "OpenDocument",
    ".odp":  "OpenDocument",
    ".ods":  "OpenDocument",
}


def _find_soffice():
    if shutil.which("soffice"):
        return "soffice"
    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/usr/bin/soffice",
        "/usr/local/bin/soffice",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


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
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, soffice, input_file, out_path):
        super().__init__()
        self._soffice = soffice
        self._input_file = input_file
        self._out_path = out_path

    def run(self):
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                result = subprocess.run(
                    [
                        self._soffice,
                        "--headless",
                        "--convert-to", "pdf",
                        "--outdir", tmp_dir,
                        self._input_file,
                    ],
                    capture_output=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    err = result.stderr.decode("utf-8", errors="replace")
                    raise RuntimeError(err or "LibreOffice conversion failed.")

                stem = Path(self._input_file).stem
                tmp_pdf = Path(tmp_dir) / f"{stem}.pdf"
                if not tmp_pdf.exists():
                    # Some versions output with the original extension stripped differently
                    pdfs = list(Path(tmp_dir).glob("*.pdf"))
                    if not pdfs:
                        raise FileNotFoundError("LibreOffice produced no PDF output.")
                    tmp_pdf = pdfs[0]

                shutil.copy2(str(tmp_pdf), self._out_path)
            self.finished.emit(self._out_path)
        except Exception as exc:
            self.failed.emit(str(exc))


# ===========================================================================
# OfficeToPDFTool
# ===========================================================================


class OfficeToPDFTool(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._modified = False
        self._input_path = ""
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
        title_lbl = QLabel("Office to PDF")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 18px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        # LibreOffice status
        soffice = _find_soffice()
        if soffice:
            badge = QFrame()
            badge.setStyleSheet(
                "background: #F0FDF4; border: 1px solid #86EFAC; border-radius: 8px;"
            )
            bl = QHBoxLayout(badge)
            bl.setContentsMargins(12, 8, 12, 8)
            bl.setSpacing(8)
            bt = QLabel("LibreOffice found")
            bt.setStyleSheet(
                "color: #166534; font: 12px; background: transparent; border: none;"
            )
            bl.addWidget(bt)
            bl.addStretch()
        else:
            badge = QFrame()
            badge.setStyleSheet(
                "background: #FEF3C7; border: 1px solid #FCD34D; border-radius: 8px;"
            )
            bl = QVBoxLayout(badge)
            bl.setContentsMargins(12, 10, 12, 10)
            bl.setSpacing(4)
            bt = QLabel("LibreOffice not found")
            bt.setStyleSheet(
                "color: #92400E; font: bold 13px; background: transparent; border: none;"
            )
            bl.addWidget(bt)
            bs = QLabel(
                "Download and install LibreOffice from libreoffice.org"
            )
            bs.setWordWrap(True)
            bs.setStyleSheet(
                "color: #78350F; font: 12px; background: transparent; border: none;"
            )
            bl.addWidget(bs)
        lay.addWidget(badge)
        lay.addSpacing(20)

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
        dz_lbl = QLabel("Drop file or")
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
        lay.addSpacing(8)

        self._type_lbl = QLabel("")
        self._type_lbl.setStyleSheet(
            f"color: {G400}; font: 11px; background: transparent; border: none;"
        )
        lay.addWidget(self._type_lbl)

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
        self._out_entry.setPlaceholderText("output.pdf")
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

        self._convert_btn = _btn("Convert to PDF", GREEN, GREEN_HOVER, h=42)
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
        lbl = QLabel("Office to PDF")
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

        tip_card = QFrame()
        tip_card.setStyleSheet(
            f"background: {WHITE}; border: 1px solid {G200}; border-radius: 12px;"
        )
        tip_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        ic = QVBoxLayout(tip_card)
        ic.setContentsMargins(24, 20, 24, 20)
        ic.setSpacing(0)
        tip_title = QLabel("Supported formats")
        tip_title.setStyleSheet(
            f"color: {G900}; font: bold 14px; background: transparent; border: none;"
        )
        ic.addWidget(tip_title)
        ic.addSpacing(12)

        formats = [
            ("Word",        ".docx  .doc"),
            ("PowerPoint",  ".pptx  .ppt"),
            ("Excel",       ".xlsx  .xls"),
            ("OpenDocument",".odt  .odp  .ods"),
        ]
        for name, exts in formats:
            row = QHBoxLayout()
            row.setContentsMargins(0, 4, 0, 0)
            row.setSpacing(12)
            name_lbl = QLabel(name)
            name_lbl.setFixedWidth(110)
            name_lbl.setStyleSheet(
                f"color: {G700}; font: 13px; background: transparent; border: none;"
            )
            row.addWidget(name_lbl)
            ext_lbl = QLabel(exts)
            ext_lbl.setStyleSheet(
                f"color: {G400}; font: 12px; font-family: monospace;"
                " background: transparent; border: none;"
            )
            row.addWidget(ext_lbl, 1)
            ic.addLayout(row)

        cl.addWidget(tip_card)

        req_card = QFrame()
        req_card.setStyleSheet(
            "background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 12px;"
        )
        req_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        rc = QVBoxLayout(req_card)
        rc.setContentsMargins(24, 16, 24, 16)
        rc.setSpacing(4)
        req_title = QLabel("Requires LibreOffice")
        req_title.setStyleSheet(
            "color: #92400E; font: bold 13px; background: transparent; border: none;"
        )
        rc.addWidget(req_title)
        req_body = QLabel(
            "LibreOffice must be installed. Download free from libreoffice.org. "
            "On macOS: brew install --cask libreoffice."
        )
        req_body.setWordWrap(True)
        req_body.setStyleSheet(
            "color: #78350F; font: 12px; background: transparent; border: none;"
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
        ext_filter = (
            "Office Documents (*.docx *.doc *.pptx *.ppt *.xlsx *.xls *.odt *.odp *.ods)"
            ";;All Files (*)"
        )
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", ext_filter)
        if path:
            self._load_file(path)

    def _load_file(self, path):
        ext = Path(path).suffix.lower()
        if ext not in SUPPORTED_EXT:
            QMessageBox.warning(self, "Unsupported",
                                f"File type '{ext}' is not supported.")
            return
        self._input_path = path
        self._file_lbl.setText(Path(path).name)
        self._type_lbl.setText(f"{SUPPORTED_EXT[ext]} document")
        self._out_entry.setText(f"{Path(path).stem}.pdf")
        self._convert_btn.setEnabled(True)

    # -----------------------------------------------------------------------
    # Convert
    # -----------------------------------------------------------------------

    def _start_convert(self):
        soffice = _find_soffice()
        if not soffice:
            QMessageBox.warning(
                self, "LibreOffice not found",
                "Install LibreOffice from libreoffice.org and try again."
            )
            return

        out_name = self._out_entry.text().strip() or f"{Path(self._input_path).stem}.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        default_dir = str(Path(self._input_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF",
            str(Path(default_dir) / out_name),
            "PDF Files (*.pdf)",
        )
        if not out_path:
            return

        self._convert_btn.setEnabled(False)
        self._status_lbl.setText("Converting...")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )

        self._worker = _ConvertWorker(soffice, self._input_path, out_path)
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
            if Path(path).suffix.lower() in SUPPORTED_EXT:
                self._load_file(path)
                break

    def cleanup(self):
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(2000)
