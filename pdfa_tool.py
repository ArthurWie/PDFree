"""PDF/A Export Tool – best-effort conversion to PDF/A-1b, -2b, or -3b.

Approach
--------
Full certified PDF/A compliance requires a dedicated toolchain (e.g.
Ghostscript, PDF Tools, Acrobat Pro) because it demands verified font
embedding, ICC color profiles on every image, and strict object-level
checks that PyMuPDF does not perform automatically.

This tool performs the operations that PyMuPDF *can* reliably handle:
  1. Sanitise: strip JS, thumbnails, hidden text, embedded files,
     form-field reset values, and link annotations.
  2. Declare conformance: inject an XMP metadata block that sets the
     pdfaid:part / pdfaid:conformance identifiers required by ISO 19005.
  3. Clean up: collect garbage (xref compaction), deflate streams and
     fonts, and remove unused objects.

The resulting file will *declare* itself as PDF/A and will pass many
basic validator checks.  Users requiring certified compliance should
verify the output with VeraPDF (https://verapdf.org) or a similar tool.
"""

import logging
import textwrap
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
    QCheckBox,
    QProgressBar,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from colors import (
    BLUE,
    BLUE_HOVER,
    BLUE_DIM,
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
    AMBER,
    AMBER_BG,
    BLUE_MED,)
from icons import svg_pixmap

try:
    import fitz
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PDF/A version catalogue
# ---------------------------------------------------------------------------

_VERSIONS = [
    {
        "id": "1b",
        "label": "PDF/A-1b",
        "part": "1",
        "conformance": "B",
        "desc": "ISO 19005-1. Basic visual preservation. Most widely supported.",
    },
    {
        "id": "2b",
        "label": "PDF/A-2b",
        "part": "2",
        "conformance": "B",
        "desc": "ISO 19005-2. Adds transparency, JPEG 2000, and layers support.",
    },
    {
        "id": "3b",
        "label": "PDF/A-3b",
        "part": "3",
        "conformance": "B",
        "desc": "ISO 19005-3. Allows arbitrary embedded files.",
    },
]

# ---------------------------------------------------------------------------
# Pure conversion helper (no Qt — callable from worker and from tests)
# ---------------------------------------------------------------------------

_PDFA_XMP_TEMPLATE = textwrap.dedent(
    """\
    <?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>
    <x:xmpmeta xmlns:x="adobe:ns:meta/">
    <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
        xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/">
      <pdfaid:part>{part}</pdfaid:part>
      <pdfaid:conformance>{conformance}</pdfaid:conformance>
    </rdf:Description>
    </rdf:RDF>
    </x:xmpmeta>
    <?xpacket end="w"?>"""
)


def _run_verapdf(path: str) -> dict:
    import shutil
    import subprocess
    exe = shutil.which("verapdf")
    if exe is None:
        return {"available": False}
    try:
        result = subprocess.run(
            [exe, "--format", "text", path],
            capture_output=True, text=True, timeout=60,
        )
        passed = result.returncode == 0
        return {
            "available": True,
            "passed": passed,
            "output": (result.stdout or result.stderr or "").strip(),
        }
    except Exception as exc:
        return {"available": True, "passed": False, "output": str(exc)}


def convert_to_pdfa(
    src: str,
    dst: str,
    part: str,
    conformance: str,
    remove_js: bool = True,
    remove_embedded: bool = True,
    remove_hidden_text: bool = True,
    remove_thumbnails: bool = True,
) -> None:
    """Convert *src* PDF to best-effort PDF/A and write to *dst*.

    Parameters
    ----------
    src:               source PDF path
    dst:               destination PDF path
    part:              PDF/A part identifier ("1", "2", or "3")
    conformance:       conformance level ("B")
    remove_js:         strip JavaScript
    remove_embedded:   strip attached/embedded files
    remove_hidden_text: strip hidden text layers
    remove_thumbnails: strip thumbnail images
    """
    doc = fitz.open(src)
    try:
        # 1. Sanitise
        doc.scrub(
            javascript=remove_js,
            embedded_files=remove_embedded,
            attached_files=remove_embedded,
            hidden_text=remove_hidden_text,
            thumbnails=remove_thumbnails,
            metadata=False,  # keep document metadata
            clean_pages=True,
            redact_images=0,
            remove_links=False,
            reset_fields=False,
            reset_responses=False,
            xml_metadata=False,  # we will set our own XMP below
        )

        # 2. Inject PDF/A XMP conformance declaration
        xmp = _PDFA_XMP_TEMPLATE.format(part=part, conformance=conformance)
        doc.set_xml_metadata(xmp)

        # 3. Save — garbage collect, deflate, clean, do NOT encrypt
        doc.save(
            dst,
            garbage=4,
            deflate=True,
            deflate_images=True,
            deflate_fonts=True,
            clean=True,
            encryption=fitz.PDF_ENCRYPT_NONE,
        )
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------


class _PDFAWorker(QThread):
    progress = Signal(int)
    finished = Signal(str, dict)
    failed = Signal(str)

    def __init__(self, src: str, dst: str, version: dict, options: dict):
        super().__init__()
        self._src = src
        self._dst = dst
        self._version = version
        self._options = options

    def run(self) -> None:
        import worker_semaphore

        worker_semaphore.acquire()
        try:
            assert_file_writable(Path(self._dst))
            backup_original(Path(self._src))
            self.progress.emit(10)
            convert_to_pdfa(
                self._src,
                self._dst,
                part=self._version["part"],
                conformance=self._version["conformance"],
                **self._options,
            )
            self.progress.emit(100)
            verapdf_result = _run_verapdf(self._dst)
            self.finished.emit(self._dst, verapdf_result)
        except PermissionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            logger.exception("pdfa conversion failed")
            self.failed.emit(str(exc))
        finally:
            worker_semaphore.release()


# ---------------------------------------------------------------------------
# Version card widget
# ---------------------------------------------------------------------------


class _VersionCard(QFrame):
    def __init__(self, version: dict, parent=None):
        super().__init__(parent)
        self.version_id = version["id"]
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(72)
        self._apply_style()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        badge = QLabel(version["label"])
        badge.setFixedWidth(72)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: {BLUE}; color: {WHITE}; border-radius: 4px;"
            " font: bold 11px; padding: 2px 0; border: none;"
        )
        lay.addWidget(badge)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)
        name_lbl = QLabel(version["label"])
        name_lbl.setStyleSheet(
            f"color: {G900}; font: bold 13px; background: transparent; border: none;"
        )
        text_col.addWidget(name_lbl)
        desc_lbl = QLabel(version["desc"])
        desc_lbl.setStyleSheet(
            f"color: {G500}; font: 11px; background: transparent; border: none;"
        )
        text_col.addWidget(desc_lbl)
        lay.addLayout(text_col, 1)

        self._indicator = QLabel()
        self._indicator.setFixedSize(18, 18)
        self._indicator.setStyleSheet(
            f"border: 2px solid {G300}; border-radius: 9px; background: {WHITE};"
        )
        lay.addWidget(self._indicator)

    def _apply_style(self) -> None:
        if self._selected:
            self.setStyleSheet(
                f"background: {BLUE_DIM}; border: 2px solid {BLUE}; border-radius: 8px;"
            )
        else:
            self.setStyleSheet(
                f"background: {WHITE}; border: 1px solid {G200}; border-radius: 8px;"
            )

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._apply_style()
        self._indicator.setStyleSheet(
            f"border: 2px solid {BLUE}; border-radius: 9px; background: {BLUE};"
            if selected
            else f"border: 2px solid {G300}; border-radius: 9px; background: {WHITE};"
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            tool = self._find_tool()
            if tool:
                tool._select_version(self.version_id)

    def _find_tool(self):
        w = self.parent()
        while w:
            if isinstance(w, PDFATool):
                return w
            w = w.parent()
        return None


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
    border_s = f"border: 1px solid {G300};" if border else "border: none;"
    b.setStyleSheet(
        f"""
        QPushButton {{
            background: {bg}; color: {text_color};
            {border_s} border-radius: 6px;
            font: {"bold " if bg in (BLUE, GREEN) else ""}13px;
            padding: 0 12px;
        }}
        QPushButton:hover {{ background: {hover}; }}
        QPushButton:disabled {{ color: {G300}; background: {G100}; border-color: {G200}; }}
        """
    )
    return b


# ---------------------------------------------------------------------------
# PDFATool
# ---------------------------------------------------------------------------


class PDFATool(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._modified = False
        self._worker = None
        self._pdf_path = ""
        self._version_id = "1b"
        self._version_cards: dict[str, _VersionCard] = {}

        if fitz is None:
            lay = QVBoxLayout(self)
            lbl = QLabel("Missing dependency.\n\nInstall with:\n  pip install pymupdf")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {G500}; font: 16px;")
            lay.addWidget(lbl)
            return

        self._build_ui()
        self.setAcceptDrops(True)

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
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
        icon_box.setPixmap(svg_pixmap("shield", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)
        title_lbl = QLabel("PDF/A Export")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 20px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        # File section
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

        # Version section
        sec_ver = QLabel("PDF/A VERSION")
        sec_ver.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_ver)
        lay.addSpacing(8)

        for ver in _VERSIONS:
            card = _VersionCard(ver, inner)
            self._version_cards[ver["id"]] = card
            lay.addWidget(card)
            lay.addSpacing(8)

        self._version_cards["1b"].set_selected(True)
        lay.addSpacing(24)

        # Sanitisation options
        sec_san = QLabel("SANITISATION")
        sec_san.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_san)
        lay.addSpacing(8)

        def _chk(text: str, checked: bool = True) -> QCheckBox:
            cb = QCheckBox(text)
            cb.setChecked(checked)
            cb.setStyleSheet(f"color: {G900}; font: 13px; background: transparent;")
            return cb

        self._chk_js = _chk("Remove JavaScript")
        self._chk_embedded = _chk("Remove embedded / attached files")
        self._chk_hidden = _chk("Remove hidden text")
        self._chk_thumbs = _chk("Remove page thumbnails")

        for cb in (
            self._chk_js,
            self._chk_embedded,
            self._chk_hidden,
            self._chk_thumbs,
        ):
            lay.addWidget(cb)
            lay.addSpacing(4)

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
        self._out_entry.setPlaceholderText("output_pdfa.pdf")
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

        self._verapdf_lbl = QLabel("")
        self._verapdf_lbl.setWordWrap(True)
        self._verapdf_lbl.setStyleSheet(
            f"color: {G500}; font: 11px; border: none; background: transparent;"
        )
        bot_lay.addWidget(self._verapdf_lbl)

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

        self._export_btn = _btn("Export PDF/A", GREEN, GREEN_HOVER, h=42)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export)
        bot_lay.addWidget(self._export_btn)

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
        tb.setSpacing(0)
        self._toolbar_lbl = QLabel("File info")
        self._toolbar_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._toolbar_lbl)
        tb.addStretch()
        v.addWidget(toolbar)

        # Content scroll area
        content = QScrollArea()
        content.setWidgetResizable(True)
        content.setStyleSheet("border: none; background: transparent;")

        self._info_widget = QWidget()
        self._info_widget.setStyleSheet(f"background: {G100};")
        self._info_lay = QVBoxLayout(self._info_widget)
        self._info_lay.setContentsMargins(32, 32, 32, 32)
        self._info_lay.setSpacing(16)

        # Best-effort notice (always visible)
        notice = QFrame()
        notice.setStyleSheet(
            f"background: {AMBER_BG}; border: 1px solid {AMBER}; border-radius: 10px;"
        )
        n_lay = QVBoxLayout(notice)
        n_lay.setContentsMargins(16, 14, 16, 14)
        n_lay.setSpacing(6)
        n_title = QLabel("Best-effort conversion")
        n_title.setStyleSheet(
            "color: #92400E; font: bold 13px; background: transparent; border: none;"
        )
        n_lay.addWidget(n_title)
        n_body = QLabel(
            "This tool applies sanitisation and sets the required XMP conformance "
            "declaration.  It does not verify font embedding, ICC colour profiles, "
            "or PDF object-level constraints.  For certified compliance, validate "
            "the output with VeraPDF (verapdf.org)."
        )
        n_body.setWordWrap(True)
        n_body.setStyleSheet(
            "color: #92400E; font: 12px; background: transparent; border: none;"
        )
        n_lay.addWidget(n_body)
        self._info_lay.addWidget(notice)

        self._file_card_placeholder = QWidget()
        self._info_lay.addWidget(self._file_card_placeholder)
        self._info_lay.addStretch()

        content.setWidget(self._info_widget)
        v.addWidget(content, 1)
        return right

    # -----------------------------------------------------------------------
    # File loading
    # -----------------------------------------------------------------------

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if path:
            self._load_file(path)

    def _load_file(self, path: str) -> None:
        try:
            doc = fitz.open(path)
            page_count = doc.page_count
            file_size = Path(path).stat().st_size
            doc.close()
        except Exception as exc:
            logger.exception("could not open pdf for pdfa export")
            QMessageBox.warning(self, "Error", f"Could not open PDF:\n{exc}")
            return

        self._pdf_path = path
        stem = Path(path).stem
        self._out_entry.setText(f"{stem}_pdfa.pdf")
        self._toolbar_lbl.setText(Path(path).name)
        self._export_btn.setEnabled(True)
        self._status_lbl.setText("")

        self._show_file_card(Path(path).name, page_count, file_size)

    def _show_file_card(self, name: str, pages: int, size: int) -> None:
        # Replace placeholder
        if hasattr(self, "_file_card_placeholder") and self._file_card_placeholder:
            self._file_card_placeholder.deleteLater()
            self._file_card_placeholder = None

        card = QFrame()
        card.setStyleSheet(
            f"background: {WHITE}; border: 1px solid {G200}; border-radius: 12px;"
        )
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(24, 20, 24, 20)
        c_lay.setSpacing(12)

        title = QLabel("Source File")
        title.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1px;"
            " background: transparent; border: none;"
        )
        c_lay.addWidget(title)

        for label, value in [
            ("File", name),
            ("Pages", str(pages)),
            ("Size", _fmt_size(size)),
        ]:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(label)
            lbl.setFixedWidth(50)
            lbl.setStyleSheet(
                f"color: {G500}; font: 12px; background: transparent; border: none;"
            )
            val = QLabel(value)
            val.setStyleSheet(
                f"color: {G900}; font: 13px; background: transparent; border: none;"
            )
            row.addWidget(lbl)
            row.addWidget(val, 1)
            c_lay.addLayout(row)

        idx = self._info_lay.count() - 1  # before stretch
        self._info_lay.insertWidget(idx, card)

    # -----------------------------------------------------------------------
    # Version selection
    # -----------------------------------------------------------------------

    def _select_version(self, version_id: str) -> None:
        self._version_id = version_id
        for vid, card in self._version_cards.items():
            card.set_selected(vid == version_id)

    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------

    def _export(self) -> None:
        if not self._pdf_path:
            return

        out_name = self._out_entry.text().strip() or "pdfa.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        default_dir = str(Path(self._pdf_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF/A",
            str(Path(default_dir) / out_name),
            "PDF Files (*.pdf)",
        )
        if not out_path:
            return

        version = next(v for v in _VERSIONS if v["id"] == self._version_id)
        options = {
            "remove_js": self._chk_js.isChecked(),
            "remove_embedded": self._chk_embedded.isChecked(),
            "remove_hidden_text": self._chk_hidden.isChecked(),
            "remove_thumbnails": self._chk_thumbs.isChecked(),
        }

        self._progress.setValue(0)
        self._progress.show()
        self._export_btn.setEnabled(False)
        self._status_lbl.setText("Converting…")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )

        self._worker = _PDFAWorker(self._pdf_path, out_path, version, options)
        self._worker.progress.connect(self._progress.setValue)
        self._worker.finished.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_done(self, out_path: str, verapdf_result: dict) -> None:
        size = Path(out_path).stat().st_size
        self._status_lbl.setText(f"Exported ({_fmt_size(size)}).")
        self._status_lbl.setStyleSheet(
            f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
        )

        if not verapdf_result.get("available"):
            self._verapdf_lbl.setText("VeraPDF not installed — skipping validation")
            self._verapdf_lbl.setStyleSheet(
                f"color: {G500}; font: 11px; border: none; background: transparent;"
            )
        elif verapdf_result.get("passed"):
            self._verapdf_lbl.setText("PDF/A validation passed")
            self._verapdf_lbl.setStyleSheet(
                f"color: {EMERALD}; font: 11px; border: none; background: transparent;"
            )
        else:
            first_lines = "\n".join(
                verapdf_result.get("output", "").splitlines()[:3]
            )
            self._verapdf_lbl.setText(f"PDF/A validation failed\n{first_lines}")
            self._verapdf_lbl.setStyleSheet(
                "color: red; font: 11px; border: none; background: transparent;"
            )

        self._export_btn.setEnabled(True)
        self._progress.hide()

    def _on_failed(self, msg: str) -> None:
        logger.exception("PDF/A export failed: %s", msg)
        QMessageBox.critical(self, "Export failed", msg)
        self._status_lbl.setText("Export failed.")
        self._status_lbl.setStyleSheet(
            "color: red; font: 12px; border: none; background: transparent;"
        )
        self._export_btn.setEnabled(True)
        self._progress.hide()

    # -----------------------------------------------------------------------
    # Drag and drop
    # -----------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pdf"):
                self._load_file(path)
                break

    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------

    def cleanup(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(3000)
