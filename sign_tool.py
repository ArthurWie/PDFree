"""Sign Tool – cryptographically sign a PDF with a PKCS#12 certificate."""

import io
import logging
from pathlib import Path
from utils import assert_file_writable, backup_original

from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QHBoxLayout,
    QVBoxLayout,
    QScrollArea,
    QFileDialog,
    QMessageBox,
    QProgressBar,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QDragEnterEvent, QDropEvent

from colors import (
    BLUE,
    BLUE_HOVER,
    GREEN,
    GREEN_HOVER,
    G50,
    G100,
    G200,
    G300,
    G400,
    G500,
    G700,
    G900,
    WHITE,
    EMERALD,
)
from icons import svg_pixmap
from utils import _fitz_pix_to_qpixmap, _make_back_button
from widgets import PreviewCanvas

try:
    import fitz
except ImportError:
    fitz = None

try:
    from pyhanko.sign import signers, fields as sig_fields
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

    _HAS_PYHANKO = True
except ImportError:
    _HAS_PYHANKO = False

logger = logging.getLogger(__name__)

LEFT_W = 300

# Signature box presets — (label, callable(page_w, page_h) → (x0,y0,x1,y1) PDF coords)
# PDF coords use bottom-left origin with y-axis pointing up.
_POSITIONS = [
    ("Bottom Right", lambda w, h: (w - 260, 20, w - 20, 90)),
    ("Bottom Left", lambda w, h: (20, 20, 260, 90)),
    ("Top Right", lambda w, h: (w - 260, h - 90, w - 20, h - 20)),
    ("Top Left", lambda w, h: (20, h - 90, 260, h - 20)),
]


def _fmt_size(n: int) -> str:
    if n < 1024**2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024**2:.2f} MB"


def _pdf_box_to_canvas(pdf_box, page_h: float, scale: float):
    """Convert PDF-coords box (bottom-left origin) to canvas pixel coords (top-left origin)."""
    x0, y0, x1, y1 = pdf_box
    cx0 = x0 * scale
    cy0 = (page_h - y1) * scale
    cx1 = x1 * scale
    cy1 = (page_h - y0) * scale
    return cx0, cy0, cx1, cy1


class _PreviewCanvas(PreviewCanvas):
    """Renders a PDF page with the planned signature box overlaid."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sig_box = None  # (cx0, cy0, cx1, cy1) in canvas pixels

    def set_content(self, pixmap, sig_box):
        self._pixmap = pixmap
        self._sig_box = sig_box
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(G50))
        if self._pixmap is None:
            p.setPen(QColor(G400))
            p.setFont(QFont("Segoe UI", 14))
            p.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "Open a PDF to preview"
            )
            return
        pm = self._pixmap
        ox = (self.width() - pm.width()) // 2
        oy = max(20, (self.height() - pm.height()) // 2)
        p.drawPixmap(ox, oy, pm)
        # Page border
        p.setPen(QPen(QColor(G200), 1))
        p.drawRect(ox - 1, oy - 1, pm.width() + 1, pm.height() + 1)
        # Signature box overlay
        if self._sig_box:
            cx0, cy0, cx1, cy1 = self._sig_box
            bx = int(ox + cx0)
            by = int(oy + cy0)
            bw = int(cx1 - cx0)
            bh = int(cy1 - cy0)
            p.fillRect(bx, by, bw, bh, QColor(59, 130, 246, 30))
            pen = QPen(QColor(BLUE), 2, Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(bx, by, bw, bh)
            p.setPen(QColor(BLUE))
            p.setFont(QFont("Segoe UI", 8))
            p.drawText(bx + 4, by + 13, "Signature")


class _SignWorker(QThread):
    progress = Signal(str)
    finished = Signal(str)  # output path
    failed = Signal(str)  # error message

    def __init__(
        self,
        pdf_path,
        cert_path,
        cert_password,
        output_path,
        page_idx,
        sig_box,
        reason,
        location,
        contact,
        tsa_url: str = "",
    ):
        super().__init__()
        self._pdf_path = pdf_path
        self._cert_path = cert_path
        self._cert_password = cert_password
        self._output_path = output_path
        self._page_idx = page_idx
        self._sig_box = sig_box  # (x0,y0,x1,y1) PDF coords, bottom-left origin
        self._reason = reason
        self._location = location
        self._contact = contact
        self._tsa_url = tsa_url

    def run(self):
        if not _HAS_PYHANKO:
            self.failed.emit("pyhanko is not installed.\n\nRun:  pip install pyhanko")
            return
        try:
            assert_file_writable(Path(self._output_path))
            backup_original(Path(self._pdf_path))
        except PermissionError as exc:
            self.failed.emit(str(exc))
            return
        try:
            pw = self._cert_password.encode("utf-8") if self._cert_password else None
            signer = signers.SimpleSigner.load_pkcs12(
                pfx_file=self._cert_path,
                passphrase=pw,
            )
        except Exception as exc:
            self.failed.emit(f"Could not load certificate:\n{exc}")
            return
        try:
            self.progress.emit("Reading PDF…")
            with open(self._pdf_path, "rb") as fh:
                pdf_bytes = fh.read()
            buf = io.BytesIO(pdf_bytes)
            w = IncrementalPdfFileWriter(buf)
            x0, y0, x1, y1 = self._sig_box
            field_spec = sig_fields.SigFieldSpec(
                sig_field_name="Sig1",
                on_page=self._page_idx,
                box=(int(x0), int(y0), int(x1), int(y1)),
            )
            meta = signers.PdfSignatureMetadata(
                field_name="Sig1",
                reason=self._reason or None,
                location=self._location or None,
                contact_info=self._contact or None,
            )
            self.progress.emit("Signing…")
            out = io.BytesIO()
            timestamper = None
            if self._tsa_url.strip():
                from pyhanko.sign.timestamps import HTTPTimeStamper

                timestamper = HTTPTimeStamper(self._tsa_url.strip())
            signers.sign_pdf(
                w,
                meta,
                signer=signer,
                new_field_spec=field_spec,
                output=out,
                timestamper=timestamper,
            )
            self.progress.emit("Saving…")
            with open(self._output_path, "wb") as fh:
                fh.write(out.getvalue())
            self.finished.emit(self._output_path)
        except Exception as exc:
            logger.exception("signing failed")
            self.failed.emit(str(exc))


class SignTool(QWidget):
    _modified = False

    def __init__(self, parent=None, initial_path: str = "", back_callback=None):
        super().__init__(parent)
        self._back_callback = back_callback
        self._pdf_path = ""
        self._cert_path = ""
        self._doc = None
        self._total_pages = 0
        self._current_page = 0
        self._scale = 1.0
        self._worker = None
        self._build_ui()
        if initial_path:
            self._load_file(initial_path)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_left())
        root.addWidget(self._build_right(), 1)

    def _build_left(self) -> QWidget:
        panel = QFrame()
        panel.setFixedWidth(LEFT_W)
        panel.setStyleSheet(
            f"QFrame {{ background: {WHITE}; border-right: 1px solid {G200}; }}"
        )
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- Header ------------------------------------------------
        hdr = QFrame()
        hdr.setFixedHeight(64)
        hdr.setStyleSheet(
            f"QFrame {{ background: {WHITE}; border-bottom: 1px solid {G200}; }}"
        )
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(16, 0, 16, 0)
        hdr_lay.setSpacing(8)
        if self._back_callback:
            hdr_lay.addWidget(_make_back_button("Back", self._back_callback, G500))
            div = QFrame()
            div.setFixedSize(1, 24)
            div.setStyleSheet(f"background: {G200}; border: none;")
            hdr_lay.addWidget(div)
        ic = QLabel()
        ic.setPixmap(svg_pixmap("pen-line", BLUE, 18))
        hdr_lay.addWidget(ic)
        title = QLabel("Sign PDF")
        title.setStyleSheet(f"color: {G900}; font: bold 14px; background: transparent;")
        hdr_lay.addWidget(title, 1)
        outer.addWidget(hdr)

        # ---- Scrollable controls -----------------------------------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(20)

        # PDF file
        lay.addWidget(self._section_label("PDF FILE"))
        self._file_lbl = self._path_label("No file selected")
        lay.addWidget(self._file_lbl)
        browse_pdf = self._action_btn("Browse…", BLUE, BLUE_HOVER)
        browse_pdf.clicked.connect(self._browse_pdf)
        lay.addWidget(browse_pdf)

        # Certificate
        lay.addWidget(self._section_label("CERTIFICATE  (.p12 / .pfx)"))
        self._cert_lbl = self._path_label("No certificate selected")
        lay.addWidget(self._cert_lbl)
        browse_cert = self._action_btn("Browse…", G100, G200, fg=G700, border=True)
        browse_cert.clicked.connect(self._browse_cert)
        lay.addWidget(browse_cert)
        pw_lbl = QLabel("Certificate password")
        pw_lbl.setStyleSheet(f"color: {G500}; font: 11px;")
        lay.addWidget(pw_lbl)
        self._cert_pw = QLineEdit()
        self._cert_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._cert_pw.setPlaceholderText("Leave blank if none")
        self._cert_pw.setFixedHeight(32)
        self._cert_pw.setStyleSheet(self._input_style())
        lay.addWidget(self._cert_pw)

        # Details
        lay.addWidget(self._section_label("SIGNATURE DETAILS  (optional)"))
        for attr, placeholder in [
            ("_reason_edit", "Reason (e.g. Approved)"),
            ("_location_edit", "Location (e.g. Paris, France)"),
            ("_contact_edit", "Contact info (e.g. email)"),
        ]:
            ed = QLineEdit()
            ed.setPlaceholderText(placeholder)
            ed.setFixedHeight(32)
            ed.setStyleSheet(self._input_style())
            setattr(self, attr, ed)
            lay.addWidget(ed)

        # TSA timestamp
        lay.addWidget(self._section_label("TIMESTAMP (OPTIONAL)"))
        lay.addSpacing(6)
        self._tsa_entry = QLineEdit()
        self._tsa_entry.setPlaceholderText(
            "TSA URL \u2014 e.g. http://timestamp.digicert.com"
        )
        self._tsa_entry.setFixedHeight(32)
        self._tsa_entry.setStyleSheet(self._input_style())
        lay.addWidget(self._tsa_entry)
        tsa_note = QLabel("Leave blank to sign without a timestamp.")
        tsa_note.setStyleSheet(f"color: {G500}; font: 12px;")
        lay.addWidget(tsa_note)
        lay.addSpacing(12)

        # Position
        lay.addWidget(self._section_label("PLACEMENT"))
        page_row = QHBoxLayout()
        page_row.setSpacing(8)
        page_lbl = QLabel("Page")
        page_lbl.setStyleSheet(f"color: {G700}; font: 12px;")
        page_row.addWidget(page_lbl)
        self._page_spin = QSpinBox()
        self._page_spin.setMinimum(1)
        self._page_spin.setMaximum(1)
        self._page_spin.setFixedHeight(32)
        self._page_spin.setStyleSheet(self._input_style())
        self._page_spin.valueChanged.connect(self._on_page_spin)
        page_row.addWidget(self._page_spin, 1)
        lay.addLayout(page_row)

        self._pos_combo = QComboBox()
        for label, _ in _POSITIONS:
            self._pos_combo.addItem(label)
        self._pos_combo.setFixedHeight(32)
        self._pos_combo.setStyleSheet(self._input_style())
        self._pos_combo.currentIndexChanged.connect(self._render_preview)
        lay.addWidget(self._pos_combo)

        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # ---- Sign button + status ----------------------------------
        footer = QFrame()
        footer.setStyleSheet(
            f"QFrame {{ background: {WHITE}; border-top: 1px solid {G200}; }}"
        )
        foot_lay = QVBoxLayout(footer)
        foot_lay.setContentsMargins(16, 12, 16, 12)
        foot_lay.setSpacing(8)
        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet(f"color: {G500}; font: 11px;")
        foot_lay.addWidget(self._status_lbl)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet(
            f"QProgressBar {{ background: {G200}; border: none; border-radius: 2px; }}"
            f"QProgressBar::chunk {{ background: {BLUE}; border-radius: 2px; }}"
        )
        foot_lay.addWidget(self._progress_bar)
        self._sign_btn = self._action_btn("Sign PDF", GREEN, GREEN_HOVER)
        self._sign_btn.setEnabled(False)
        self._sign_btn.clicked.connect(self._sign)
        foot_lay.addWidget(self._sign_btn)
        outer.addWidget(footer)

        return panel

    def _build_right(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {G50};")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Nav bar
        nav = QFrame()
        nav.setFixedHeight(48)
        nav.setStyleSheet(
            f"QFrame {{ background: {WHITE}; border-bottom: 1px solid {G200}; }}"
        )
        nav_lay = QHBoxLayout(nav)
        nav_lay.setContentsMargins(16, 0, 16, 0)
        nav_lay.setSpacing(8)
        self._prev_btn = QPushButton("‹")
        self._prev_btn.setFixedSize(32, 32)
        self._prev_btn.clicked.connect(self._prev_page)
        self._prev_btn.setStyleSheet(self._nav_btn_style())
        self._next_btn = QPushButton("›")
        self._next_btn.setFixedSize(32, 32)
        self._next_btn.clicked.connect(self._next_page)
        self._next_btn.setStyleSheet(self._nav_btn_style())
        self._page_lbl = QLabel("—")
        self._page_lbl.setStyleSheet(
            f"color: {G700}; font: 12px; background: transparent;"
        )
        nav_lay.addWidget(self._prev_btn)
        nav_lay.addWidget(self._page_lbl)
        nav_lay.addWidget(self._next_btn)
        nav_lay.addStretch()
        zoom_in = QPushButton("+")
        zoom_in.setFixedSize(28, 28)
        zoom_in.setStyleSheet(self._nav_btn_style())
        zoom_in.clicked.connect(self._zoom_in)
        zoom_out = QPushButton("−")
        zoom_out.setFixedSize(28, 28)
        zoom_out.setStyleSheet(self._nav_btn_style())
        zoom_out.clicked.connect(self._zoom_out)
        nav_lay.addWidget(zoom_out)
        nav_lay.addWidget(zoom_in)
        lay.addWidget(nav)

        self._canvas = _PreviewCanvas()
        lay.addWidget(self._canvas, 1)
        return panel

    # ------------------------------------------------------------------
    # Style helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {G500}; font: bold 10px; letter-spacing: 1px;")
        return lbl

    @staticmethod
    def _path_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {G700}; font: 11px; font-family: monospace;")
        return lbl

    @staticmethod
    def _input_style() -> str:
        return (
            f"QWidget {{ background: {WHITE}; border: 1px solid {G200}; "
            f"border-radius: 6px; color: {G900}; font: 12px; padding: 0 8px; }}"
            f"QWidget:focus {{ border: 1px solid {BLUE}; }}"
        )

    @staticmethod
    def _action_btn(text, bg, hover, fg=WHITE, border=False, h=36) -> QPushButton:
        b = QPushButton(text)
        b.setFixedHeight(h)
        border_s = f"border: 1px solid {G300};" if border else "border: none;"
        b.setStyleSheet(
            f"QPushButton {{ background: {bg}; color: {fg}; {border_s} "
            f"border-radius: 6px; font: 13px; padding: 0 12px; }}"
            f"QPushButton:hover {{ background: {hover}; }}"
            f"QPushButton:disabled {{ background: {G200}; color: {G400}; border: none; }}"
        )
        return b

    @staticmethod
    def _nav_btn_style() -> str:
        return (
            f"QPushButton {{ background: {WHITE}; color: {G700}; "
            f"border: 1px solid {G200}; border-radius: 6px; font: 14px; }}"
            f"QPushButton:hover {{ background: {G100}; }}"
            f"QPushButton:disabled {{ color: {G300}; border-color: {G200}; }}"
        )

    # ------------------------------------------------------------------
    # File loading
    # ------------------------------------------------------------------

    def _browse_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if path:
            self._load_file(path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(".pdf"):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path.lower().endswith(".pdf"):
                self._load_file(path)

    def _load_file(self, path: str):
        if fitz is None:
            QMessageBox.warning(
                self, "Missing dependency", "PyMuPDF (fitz) is not installed."
            )
            return
        try:
            if self._doc:
                self._doc.close()
            self._doc = fitz.open(path)
            self._pdf_path = path
            self._total_pages = self._doc.page_count
            self._current_page = 0
            self._page_spin.setMaximum(self._total_pages)
            self._page_spin.setValue(1)
            stem = Path(path).name
            self._file_lbl.setText(stem)
            self._update_nav()
            self._render_preview()
            self._refresh_sign_btn()
        except Exception as exc:
            logger.exception("load failed")
            QMessageBox.critical(self, "Error", f"Could not open file:\n{exc}")

    def _browse_cert(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Certificate",
            "",
            "PKCS#12 Certificates (*.p12 *.pfx);;All Files (*)",
        )
        if path:
            self._cert_path = path
            self._cert_lbl.setText(Path(path).name)
            self._refresh_sign_btn()

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _render_preview(self):
        if not self._doc or fitz is None:
            return
        page = self._doc[self._current_page]
        pw, ph = page.rect.width, page.rect.height
        vp_w = max(self._canvas.width() - 40, 300)
        self._scale = min(vp_w / pw, 1.5)
        dpr = self._canvas.devicePixelRatio()
        mat_phys = fitz.Matrix(self._scale * dpr, self._scale * dpr)
        pix = page.get_pixmap(matrix=mat_phys, alpha=False)
        pm = _fitz_pix_to_qpixmap(pix, dpr)
        sig_box = self._get_sig_box(pw, ph)
        canvas_box = _pdf_box_to_canvas(sig_box, ph, self._scale)
        self._canvas.set_content(pm, canvas_box)

    def _get_sig_box(self, page_w: float, page_h: float):
        idx = self._pos_combo.currentIndex()
        _, fn = _POSITIONS[idx]
        return fn(page_w, page_h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render_preview()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._page_spin.setValue(self._current_page + 1)
            self._update_nav()
            self._render_preview()

    def _next_page(self):
        if self._current_page < self._total_pages - 1:
            self._current_page += 1
            self._page_spin.setValue(self._current_page + 1)
            self._update_nav()
            self._render_preview()

    def _on_page_spin(self, val: int):
        new_page = val - 1
        if self._doc and 0 <= new_page < self._total_pages:
            self._current_page = new_page
            self._update_nav()
            self._render_preview()

    def _update_nav(self):
        self._page_lbl.setText(
            f"Page {self._current_page + 1} / {self._total_pages}"
            if self._total_pages
            else "—"
        )
        self._prev_btn.setEnabled(self._current_page > 0)
        self._next_btn.setEnabled(self._current_page < self._total_pages - 1)

    def _zoom_in(self):
        self._scale = min(self._scale * 1.25, 4.0)
        self._render_preview()

    def _zoom_out(self):
        self._scale = max(self._scale / 1.25, 0.2)
        self._render_preview()

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    def _refresh_sign_btn(self):
        self._sign_btn.setEnabled(bool(self._pdf_path) and bool(self._cert_path))

    def _sign(self):
        if not self._pdf_path or not self._cert_path:
            return
        if not _HAS_PYHANKO:
            QMessageBox.warning(
                self,
                "Missing dependency",
                "pyhanko is not installed.\n\nRun:  pip install pyhanko",
            )
            return
        stem = Path(self._pdf_path).stem
        default = str(Path(self._pdf_path).parent / f"{stem}_signed.pdf")
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save Signed PDF", default, "PDF Files (*.pdf)"
        )
        if not out_path:
            return
        if not out_path.lower().endswith(".pdf"):
            out_path += ".pdf"

        if not self._doc:
            return
        page = self._doc[self._current_page]
        pw, ph = page.rect.width, page.rect.height
        sig_box = self._get_sig_box(pw, ph)

        self._sign_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._status_lbl.setText("Starting…")

        self._worker = _SignWorker(
            pdf_path=self._pdf_path,
            cert_path=self._cert_path,
            cert_password=self._cert_pw.text(),
            output_path=out_path,
            page_idx=self._current_page,
            sig_box=sig_box,
            reason=self._reason_edit.text().strip(),
            location=self._location_edit.text().strip(),
            contact=self._contact_edit.text().strip(),
            tsa_url=self._tsa_entry.text(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, msg: str):
        self._status_lbl.setText(msg)

    def _on_done(self, out_path: str):
        self._progress_bar.setVisible(False)
        self._sign_btn.setEnabled(True)
        size = Path(out_path).stat().st_size if Path(out_path).exists() else 0
        self._status_lbl.setText(
            f"Signed successfully — {_fmt_size(size)}\n{Path(out_path).name}"
        )
        self._status_lbl.setStyleSheet(f"color: {EMERALD}; font: 11px;")

    def _on_failed(self, msg: str):
        self._progress_bar.setVisible(False)
        self._sign_btn.setEnabled(bool(self._pdf_path) and bool(self._cert_path))
        self._status_lbl.setText("")
        QMessageBox.critical(self, "Signing Failed", msg)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self):
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(3000)
        if self._doc:
            self._doc.close()
            self._doc = None
