"""HTML to PDF Tool – convert HTML files, URLs, or pasted HTML to PDF.

PySide6. Requires weasyprint. Loaded by main.py.
"""

import logging
from pathlib import Path
from utils import assert_file_writable

from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QScrollArea,
    QHBoxLayout,
    QVBoxLayout,
    QFileDialog,
    QMessageBox,
    QSizePolicy,
    QButtonGroup,
    QRadioButton,
    QStackedWidget,
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
    BLUE_MED,)
from icons import svg_pixmap

try:
    from weasyprint import HTML as _WeasyHTML
    _HAS_WEASYPRINT = True
except ImportError:
    _HAS_WEASYPRINT = False

logger = logging.getLogger(__name__)


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


def _radio(text):
    r = QRadioButton(text)
    r.setStyleSheet(
        f"color: {G700}; font: 13px; background: transparent; border: none;"
    )
    return r


# ===========================================================================
# Worker thread
# ===========================================================================


class _ConvertWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, mode, source, out_path):
        super().__init__()
        self._mode = mode      # "file", "url", "paste"
        self._source = source
        self._out_path = out_path

    def run(self):
        try:
            assert_file_writable(Path(self._out_path))
            if self._mode == "file":
                _WeasyHTML(filename=self._source).write_pdf(self._out_path)
            elif self._mode == "url":
                _WeasyHTML(url=self._source).write_pdf(self._out_path)
            else:  # paste
                _WeasyHTML(string=self._source).write_pdf(self._out_path)
            self.finished.emit(self._out_path)
        except PermissionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            logger.exception("worker failed")
            self.failed.emit(str(exc))


# ===========================================================================
# HTMLToPDFTool
# ===========================================================================


class HTMLToPDFTool(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._modified = False
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
        icon_box.setPixmap(svg_pixmap("file-text", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)
        title_lbl = QLabel("HTML to PDF")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 18px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        if not _HAS_WEASYPRINT:
            warn = QFrame()
            warn.setStyleSheet(
                "background: #FEF3C7; border: 1px solid #FCD34D; border-radius: 8px;"
            )
            wl = QVBoxLayout(warn)
            wl.setContentsMargins(16, 12, 16, 12)
            wl.setSpacing(4)
            wt = QLabel("weasyprint not installed")
            wt.setStyleSheet(
                "color: #92400E; font: bold 13px; background: transparent; border: none;"
            )
            wl.addWidget(wt)
            ws = QLabel("pip install weasyprint")
            ws.setStyleSheet(
                "color: #78350F; font: 12px; font-family: monospace;"
                " background: transparent; border: none;"
            )
            wl.addWidget(ws)
            lay.addWidget(warn)
            lay.addSpacing(16)

        # Input mode
        lay.addWidget(_section("INPUT MODE"))
        lay.addSpacing(8)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(16)
        mode_row.setContentsMargins(0, 0, 0, 0)
        self._radio_file = _radio("File")
        self._radio_url = _radio("URL")
        self._radio_paste = _radio("Paste HTML")
        self._radio_file.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self._radio_file, 0)
        grp.addButton(self._radio_url, 1)
        grp.addButton(self._radio_paste, 2)
        grp.idClicked.connect(self._on_mode_changed)
        mode_row.addWidget(self._radio_file)
        mode_row.addWidget(self._radio_url)
        mode_row.addWidget(self._radio_paste)
        mode_row.addStretch()
        lay.addLayout(mode_row)
        lay.addSpacing(16)

        # Stacked input widgets
        self._input_stack = QStackedWidget()

        # Page 0: File
        file_w = QWidget()
        file_w.setStyleSheet("background: transparent;")
        fv = QVBoxLayout(file_w)
        fv.setContentsMargins(0, 0, 0, 0)
        fv.setSpacing(8)
        dz = QFrame()
        dz.setFixedHeight(52)
        dz.setStyleSheet(
            f"background: {G100};"
            f" border: 2px dashed {G200}; border-radius: 12px;"
        )
        dz_h = QHBoxLayout(dz)
        dz_h.setContentsMargins(10, 0, 10, 0)
        dz_h.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(svg_pixmap("file-text", G400, 18))
        ic.setStyleSheet("border: none; background: transparent;")
        dz_h.addWidget(ic)
        dz_lbl = QLabel("Drop .html or")
        dz_lbl.setStyleSheet(
            f"color: {G500}; font: 13px; border: none; background: transparent;"
        )
        dz_h.addWidget(dz_lbl)
        browse_btn = _btn("Browse", BLUE, BLUE_HOVER, h=30, w=80)
        browse_btn.clicked.connect(self._browse_file)
        dz_h.addWidget(browse_btn)
        dz_h.addStretch()
        fv.addWidget(dz)
        self._file_lbl = QLabel("No file selected")
        self._file_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        self._file_lbl.setWordWrap(True)
        fv.addWidget(self._file_lbl)
        self._input_stack.addWidget(file_w)

        # Page 1: URL
        url_w = QWidget()
        url_w.setStyleSheet("background: transparent;")
        uv = QVBoxLayout(url_w)
        uv.setContentsMargins(0, 0, 0, 0)
        uv.setSpacing(0)
        self._url_entry = QLineEdit()
        self._url_entry.setPlaceholderText("https://example.com")
        self._url_entry.setFixedHeight(36)
        self._url_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        uv.addWidget(self._url_entry)
        self._input_stack.addWidget(url_w)

        # Page 2: Paste
        paste_w = QWidget()
        paste_w.setStyleSheet("background: transparent;")
        pv = QVBoxLayout(paste_w)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(0)
        self._html_edit = QTextEdit()
        self._html_edit.setPlaceholderText(
            "<html>\n<body>\n  <h1>Hello World</h1>\n</body>\n</html>"
        )
        self._html_edit.setFixedHeight(160)
        self._html_edit.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 6px 10px;"
            f" font: 12px; font-family: monospace; color: {G900}; background: {WHITE};"
        )
        pv.addWidget(self._html_edit)
        self._input_stack.addWidget(paste_w)

        lay.addWidget(self._input_stack)

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
        self._out_entry.setText("output.pdf")
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
        self._convert_btn.setEnabled(_HAS_WEASYPRINT)
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
        lbl = QLabel("HTML to PDF")
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
        tip_title = QLabel("How it works")
        tip_title.setStyleSheet(
            f"color: {G900}; font: bold 14px; background: transparent; border: none;"
        )
        ic.addWidget(tip_title)
        ic.addSpacing(8)
        for step in [
            "File: load a local .html file from disk.",
            "URL: enter any public web page address.",
            "Paste: type or paste raw HTML directly.",
            "WeasyPrint renders the HTML with CSS and saves as PDF.",
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

        req_card = QFrame()
        req_card.setStyleSheet(
            "background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 12px;"
        )
        req_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        rc = QVBoxLayout(req_card)
        rc.setContentsMargins(24, 16, 24, 16)
        rc.setSpacing(4)
        req_title = QLabel("Requirements")
        req_title.setStyleSheet(
            "color: #92400E; font: bold 13px; background: transparent; border: none;"
        )
        rc.addWidget(req_title)
        req_body = QLabel(
            "pip install weasyprint\n\n"
            "On Windows, WeasyPrint requires GTK runtime libraries. "
            "Install via: pip install weasyprint and follow the Windows "
            "install guide at weasyprint.org/docs/install."
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
    # Input mode
    # -----------------------------------------------------------------------

    def _on_mode_changed(self, idx):
        self._input_stack.setCurrentIndex(idx)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open HTML File", "",
            "HTML Files (*.html *.htm);;All Files (*)"
        )
        if path:
            self._file_lbl.setText(Path(path).name)
            self._file_lbl.setProperty("path", path)
            stem = Path(path).stem
            self._out_entry.setText(f"{stem}.pdf")

    # -----------------------------------------------------------------------
    # Convert
    # -----------------------------------------------------------------------

    def _start_convert(self):
        if not _HAS_WEASYPRINT:
            QMessageBox.warning(self, "Missing dependency",
                                "Install weasyprint:\n  pip install weasyprint")
            return

        mode_idx = self._input_stack.currentIndex()
        if mode_idx == 0:
            mode = "file"
            source = self._file_lbl.property("path") or ""
            if not source:
                QMessageBox.warning(self, "No file", "Select an HTML file first.")
                return
        elif mode_idx == 1:
            mode = "url"
            source = self._url_entry.text().strip()
            if not source:
                QMessageBox.warning(self, "No URL", "Enter a URL first.")
                return
        else:
            mode = "paste"
            source = self._html_edit.toPlainText().strip()
            if not source:
                QMessageBox.warning(self, "No HTML", "Paste some HTML first.")
                return

        out_name = self._out_entry.text().strip() or "output.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF", out_name, "PDF Files (*.pdf)"
        )
        if not out_path:
            return

        self._convert_btn.setEnabled(False)
        self._status_lbl.setText("Converting...")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )

        self._worker = _ConvertWorker(mode, source, out_path)
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
            if path.lower().endswith((".html", ".htm")):
                self._radio_file.setChecked(True)
                self._input_stack.setCurrentIndex(0)
                self._file_lbl.setText(Path(path).name)
                self._file_lbl.setProperty("path", path)
                self._out_entry.setText(f"{Path(path).stem}.pdf")
                break

    def cleanup(self):
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(2000)
