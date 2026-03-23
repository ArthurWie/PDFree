"""Form Unlock Tool – remove the read-only flag from every AcroForm field.

PySide6. Uses pypdf to clear the ReadOnly bit (Ff bit 0) on each field
so the resulting PDF can be filled by any viewer.
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
    QHBoxLayout,
    QVBoxLayout,
    QFileDialog,
    QMessageBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent

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
    BLUE_MED,
)
from icons import svg_pixmap

try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NumberObject, NameObject

    _HAS_PYPDF = True
except ImportError:
    _HAS_PYPDF = False

logger = logging.getLogger(__name__)

_FF_READ_ONLY = 1


class _FormUnlockWorker(QThread):
    finished = Signal(str, int)  # out_path, fields_modified
    failed = Signal(str)

    def __init__(self, pdf_path, out_path, parent=None):
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._out_path = out_path

    def run(self):
        try:
            assert_file_writable(Path(self._out_path))
            backup_original(Path(self._pdf_path))
            n = unlock_form_fields(self._pdf_path, self._out_path)
            self.finished.emit(self._out_path, n)
        except PermissionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))


def unlock_form_fields(src_path: str, dst_path: str) -> int:
    """Clear the ReadOnly bit on every AcroForm field.

    Returns the number of fields that were modified.
    """
    reader = PdfReader(src_path)
    writer = PdfWriter()
    writer.append(reader)

    modified = 0
    for page in writer.pages:
        if "/Annots" not in page:
            continue
        for annot in page["/Annots"]:
            obj = annot.get_object()
            if obj.get("/Type") == "/Annot" and obj.get("/Subtype") == "/Widget":
                ff = int(obj.get("/Ff", 0))
                if ff & _FF_READ_ONLY:
                    obj[NameObject("/Ff")] = NumberObject(ff & ~_FF_READ_ONLY)
                    modified += 1

    with open(dst_path, "wb") as f:
        writer.write(f)
    return modified


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


class FormUnlockTool(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._modified = False

        if not _HAS_PYPDF:
            lay = QVBoxLayout(self)
            lbl = QLabel("Missing dependency.\n\nInstall with:\n  pip install pypdf")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {G500}; font: 16px;")
            lay.addWidget(lbl)
            return

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

    def _build_left_panel(self) -> QWidget:
        left = QWidget()
        left.setFixedWidth(380)
        left.setStyleSheet(f"background: {WHITE}; border-right: 1px solid {G200};")
        outer = QVBoxLayout(left)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

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
        icon_box.setPixmap(svg_pixmap("unlock", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)
        title_lbl = QLabel("Unlock Form Fields")
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
        lay.addWidget(self._drop_zone())
        lay.addSpacing(8)
        self._file_lbl = QLabel("No file loaded")
        self._file_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        self._file_lbl.setWordWrap(True)
        lay.addWidget(self._file_lbl)
        lay.addStretch()

        outer.addWidget(inner, 1)

        # Bottom bar
        bottom = QWidget()
        bottom.setStyleSheet(f"background: {WHITE}; border-top: 1px solid {G200};")
        bot = QVBoxLayout(bottom)
        bot.setContentsMargins(24, 16, 24, 20)
        bot.setSpacing(10)

        bot.addWidget(_section("OUTPUT FILE"))
        self._out_entry = QLineEdit()
        self._out_entry.setPlaceholderText("output_unlocked.pdf")
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

        self._save_btn = _btn("Unlock Form Fields", GREEN, GREEN_HOVER, h=42)
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
        cl.setSpacing(0)

        info_card = QFrame()
        info_card.setStyleSheet(
            f"background: {WHITE}; border: 1px solid {G200}; border-radius: 12px;"
        )
        info_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        ic = QVBoxLayout(info_card)
        ic.setContentsMargins(24, 20, 24, 20)
        ic.setSpacing(8)

        tip_title = QLabel("About form unlocking")
        tip_title.setStyleSheet(
            f"color: {G900}; font: bold 14px; background: transparent; border: none;"
        )
        ic.addWidget(tip_title)

        tips = [
            (
                "Read-only fields",
                "PDF forms can have individual fields marked read-only via the Ff flag. "
                "This prevents viewers from letting users type into them.",
            ),
            (
                "What this tool does",
                "Clears the ReadOnly bit on every AcroForm field, producing a new PDF "
                "where all fields are fillable.",
            ),
            (
                "Limitations",
                "Does not bypass password-based restrictions. "
                "The source PDF must be openable without a password.",
            ),
        ]
        for term, desc in tips:
            row = QHBoxLayout()
            row.setContentsMargins(0, 4, 0, 0)
            row.setSpacing(10)
            dot = QLabel("•")
            dot.setFixedWidth(12)
            dot.setStyleSheet(
                f"color: {BLUE}; font: bold 14px; background: transparent; border: none;"
            )
            row.addWidget(dot)
            txt = QLabel(f"<b>{term}</b> — {desc}")
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

    def _drop_zone(self) -> QFrame:
        dz = QFrame()
        dz.setFixedHeight(56)
        dz.setStyleSheet(
            f"background: {G100}; border: 2px dashed {G200}; border-radius: 12px;"
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

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        self._pdf_path = path
        name = Path(path).name
        self._file_lbl.setText(name)
        self._toolbar_lbl.setText(name)
        self._out_entry.setText(f"{Path(path).stem}_unlocked.pdf")
        self._save_btn.setEnabled(True)
        self._status_lbl.setText("")

    def _save(self):
        if not self._pdf_path:
            return
        out_name = self._out_entry.text().strip() or "unlocked.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"
        default_dir = str(Path(self._pdf_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Unlocked PDF",
            str(Path(default_dir) / out_name),
            "PDF Files (*.pdf)",
        )
        if not out_path:
            return

        self._save_btn.setEnabled(False)
        self._status_lbl.setText("Unlocking…")

        self._worker = _FormUnlockWorker(self._pdf_path, out_path)
        self._worker.finished.connect(self._on_save_done)
        self._worker.failed.connect(self._on_save_failed)
        self._worker.start()

    def _on_save_done(self, _out_path: str, n: int):
        if n == 0:
            self._status_lbl.setText(
                "No read-only fields found — file saved unchanged."
            )
        else:
            self._status_lbl.setText(f"Done — {n} field(s) unlocked.")
        self._status_lbl.setStyleSheet(
            f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
        )
        self._save_btn.setEnabled(True)

    def _on_save_failed(self, msg: str):
        logger.error("form unlock failed: %s", msg)
        QMessageBox.critical(self, "Failed", msg)
        self._status_lbl.setText("Failed.")
        self._save_btn.setEnabled(True)

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
