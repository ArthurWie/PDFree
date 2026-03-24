"""Add Password Tool – encrypt a PDF with user and owner passwords.

PySide6. Loaded by main.py when the user clicks "Add Password".
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
    QCheckBox,
    QScrollArea,
    QHBoxLayout,
    QVBoxLayout,
    QFileDialog,
    QInputDialog,
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
    BLUE_MED,
)
from icons import svg_pixmap

try:
    import fitz
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Encryption level options
# ---------------------------------------------------------------------------

ENC_OPTIONS = [
    ("AES 256-bit  (recommended)", "aes256"),
    ("AES 128-bit", "aes128"),
    ("RC4 128-bit  (legacy)", "rc4128"),
]

ENC_MAP = {
    "aes256": None,  # set after fitz import
    "aes128": None,
    "rc4128": None,
}

PERMISSIONS = [
    ("Allow printing (standard quality)", "print", None),
    ("Allow printing (high quality)", "print_hq", None),
    ("Allow copying text", "copy", None),
    ("Allow editing content", "modify", None),
    ("Allow adding annotations", "annotate", None),
    ("Allow filling forms", "forms", None),
    ("Allow assembling pages", "assemble", None),
    ("Allow extraction for accessibility", "accessibility", None),
]


def _fmt_size(n: int) -> str:
    if n < 1024**2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024**2:.2f} MB"


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


def _pw_field(placeholder: str) -> QLineEdit:
    f = QLineEdit()
    f.setPlaceholderText(placeholder)
    f.setEchoMode(QLineEdit.EchoMode.Password)
    f.setFixedHeight(38)
    f.setStyleSheet(
        f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
        f" font: 13px; color: {G900}; background: {WHITE};"
    )
    return f


# ===========================================================================
# Encryption level card
# ===========================================================================


class _EncCard(QFrame):
    def __init__(self, label: str, enc_id: str, parent=None):
        super().__init__(parent)
        self.enc_id = enc_id
        self._selected = False
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(10)

        self._dot = QLabel()
        self._dot.setFixedSize(16, 16)
        self._dot.setStyleSheet(
            f"border: 2px solid {G300}; border-radius: 8px; background: {WHITE};"
        )
        lay.addWidget(self._dot)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {G900}; font: 13px; background: transparent; border: none;"
        )
        lay.addWidget(lbl, 1)

    def _apply_style(self):
        if self._selected:
            self.setStyleSheet(
                f"background: #EFF6FF; border: 1.5px solid {BLUE}; border-radius: 6px;"
            )
        else:
            self.setStyleSheet(
                f"background: {WHITE}; border: 1px solid {G200}; border-radius: 6px;"
            )

    def set_selected(self, v: bool):
        self._selected = v
        self._apply_style()
        if v:
            self._dot.setStyleSheet(
                f"border: 2px solid {BLUE}; border-radius: 8px; background: {BLUE};"
            )
        else:
            self._dot.setStyleSheet(
                f"border: 2px solid {G300}; border-radius: 8px; background: {WHITE};"
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            tool = self._find_tool()
            if tool:
                tool._select_enc(self.enc_id)

    def _find_tool(self):
        w = self.parent()
        while w:
            if isinstance(w, AddPasswordTool):
                return w
            w = w.parent()
        return None


# ===========================================================================
# AddPasswordTool
# ===========================================================================


class _AddPasswordWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, pdf_path, out_path, enc_const, user_pw, owner_pw, perms):
        super().__init__()
        self._pdf_path = pdf_path
        self._out_path = out_path
        self._enc_const = enc_const
        self._user_pw = user_pw
        self._owner_pw = owner_pw
        self._perms = perms

    def run(self):
        try:
            assert_file_writable(Path(self._out_path))
            backup_original(Path(self._pdf_path))
            doc = fitz.open(self._pdf_path)
            doc.save(
                self._out_path,
                encryption=self._enc_const,
                user_pw=self._user_pw,
                owner_pw=self._owner_pw,
                permissions=self._perms,
                garbage=3,
                deflate=True,
            )
            doc.close()
            self.finished.emit(self._out_path)
        except PermissionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            logger.exception("worker failed")
            self.failed.emit(str(exc))


class AddPasswordTool(QWidget):
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

        ENC_MAP["aes256"] = fitz.PDF_ENCRYPT_AES_256
        ENC_MAP["aes128"] = fitz.PDF_ENCRYPT_AES_128
        ENC_MAP["rc4128"] = fitz.PDF_ENCRYPT_RC4_128

        self._pdf_path = ""
        self._enc_id = "aes256"
        self._worker = None
        self._enc_cards: dict[str, _EncCard] = {}
        self._perm_checks: dict[str, QCheckBox] = {}
        self._is_reencrypt = False  # True when editing an already-encrypted PDF

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
        icon_box.setPixmap(svg_pixmap("lock", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)

        title_lbl = QLabel("Add Password")
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
        drop_zone = self._drop_zone()
        lay.addWidget(drop_zone)
        lay.addSpacing(8)
        self._file_lbl = QLabel("No file loaded")
        self._file_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        self._file_lbl.setWordWrap(True)
        lay.addWidget(self._file_lbl)
        lay.addSpacing(8)

        self._reencrypt_banner = QFrame()
        self._reencrypt_banner.setStyleSheet(
            "background: #FEF9C3; border: 1px solid #FDE047; border-radius: 6px;"
        )
        self._reencrypt_banner.setVisible(False)
        rb_lay = QHBoxLayout(self._reencrypt_banner)
        rb_lay.setContentsMargins(10, 8, 10, 8)
        rb_lbl = QLabel(
            "This PDF is already protected. "
            "Enter the passwords you want to use (re-encrypt with new permissions)."
        )
        rb_lbl.setWordWrap(True)
        rb_lbl.setStyleSheet(
            "color: #713F12; font: 12px; background: transparent; border: none;"
        )
        rb_lay.addWidget(rb_lbl)
        lay.addWidget(self._reencrypt_banner)
        lay.addSpacing(16)

        # Passwords
        lay.addWidget(_section("PASSWORDS"))
        lay.addSpacing(8)

        self._user_pw = _pw_field("User password  (required to open)")
        self._user_pw.textChanged.connect(self._validate)
        lay.addWidget(self._user_pw)
        lay.addSpacing(6)

        self._user_pw2 = _pw_field("Confirm user password")
        self._user_pw2.textChanged.connect(self._validate)
        lay.addWidget(self._user_pw2)
        lay.addSpacing(6)

        self._owner_pw = _pw_field("Owner password  (optional — for full access)")
        lay.addWidget(self._owner_pw)
        lay.addSpacing(6)

        self._pw_err = QLabel("")
        self._pw_err.setStyleSheet(
            "color: #EF4444; font: 12px; background: transparent; border: none;"
        )
        lay.addWidget(self._pw_err)
        lay.addSpacing(20)

        # Encryption level
        lay.addWidget(_section("ENCRYPTION"))
        lay.addSpacing(8)
        for label, enc_id in ENC_OPTIONS:
            card = _EncCard(label, enc_id, inner)
            self._enc_cards[enc_id] = card
            lay.addWidget(card)
            lay.addSpacing(5)
        self._enc_cards["aes256"].set_selected(True)
        lay.addSpacing(20)

        # Permissions
        lay.addWidget(_section("PERMISSIONS  (what the user can do after opening)"))
        lay.addSpacing(8)
        for label, key, _ in PERMISSIONS:
            cb = QCheckBox(label)
            cb.setChecked(True)
            cb.setStyleSheet(
                f"color: {G700}; font: 13px; background: transparent; border: none;"
            )
            self._perm_checks[key] = cb
            lay.addWidget(cb)
            lay.addSpacing(4)

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
        self._out_entry.setPlaceholderText("output_protected.pdf")
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

        self._save_btn = _btn("Encrypt PDF", GREEN, GREEN_HOVER, h=42)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save)
        bot.addWidget(self._save_btn)
        self._save_btn_ref = self._save_btn

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

        tip_title = QLabel("About PDF passwords")
        tip_title.setStyleSheet(
            f"color: {G900}; font: bold 14px; background: transparent; border: none;"
        )
        ic.addWidget(tip_title)

        tips = [
            (
                "User password",
                "Required to open the file. Anyone without it cannot read the PDF.",
            ),
            (
                "Owner password",
                "Controls permissions. If omitted, defaults to the user password.",
            ),
            (
                "Permissions",
                "Define what an authenticated user is allowed to do (print, copy, etc.).",
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
        except Exception as exc:
            logger.exception("could not open pdf")
            QMessageBox.warning(self, "Error", f"Could not open PDF:\n{exc}")
            return

        if doc.needs_pass:
            doc.close()
            self._load_encrypted(path)
            return

        doc.close()
        self._is_reencrypt = False
        self._reencrypt_banner.setVisible(False)
        self._save_btn_ref.setText("Encrypt PDF")
        self._pdf_path = path
        name = Path(path).name
        self._file_lbl.setText(name)
        self._toolbar_lbl.setText(name)
        self._out_entry.setText(f"{Path(path).stem}_protected.pdf")
        self._validate()

    def _load_encrypted(self, path: str):
        owner_pw, ok = QInputDialog.getText(
            self,
            "Owner password required",
            "Enter the owner (permissions) password to load this protected PDF:",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return

        doc = fitz.open(path)
        level = doc.authenticate(owner_pw)
        if level < 2:
            doc.close()
            QMessageBox.warning(
                self,
                "Authentication failed",
                "Wrong password or the password does not grant owner-level access.",
            )
            return

        # Read current permission flags and pre-tick the checkboxes
        current_perms = doc.permissions
        doc.close()

        perm_flag_map = {
            "print": fitz.PDF_PERM_PRINT,
            "print_hq": fitz.PDF_PERM_PRINT_HQ,
            "copy": fitz.PDF_PERM_COPY,
            "modify": fitz.PDF_PERM_MODIFY,
            "annotate": fitz.PDF_PERM_ANNOTATE,
            "forms": fitz.PDF_PERM_FORM,
            "assemble": fitz.PDF_PERM_ASSEMBLE,
            "accessibility": fitz.PDF_PERM_ACCESSIBILITY,
        }
        for key, flag in perm_flag_map.items():
            if key in self._perm_checks:
                self._perm_checks[key].setChecked(bool(current_perms & flag))

        self._is_reencrypt = True
        self._reencrypt_banner.setVisible(True)
        self._save_btn_ref.setText("Re-encrypt PDF")
        self._pdf_path = path
        name = Path(path).name
        self._file_lbl.setText(name)
        self._toolbar_lbl.setText(name)
        self._out_entry.setText(f"{Path(path).stem}_updated.pdf")
        self._validate()

    # -----------------------------------------------------------------------
    # Enc selection + validation
    # -----------------------------------------------------------------------

    def _select_enc(self, enc_id: str):
        self._enc_id = enc_id
        for eid, card in self._enc_cards.items():
            card.set_selected(eid == enc_id)

    def _validate(self):
        pw1 = self._user_pw.text()
        pw2 = self._user_pw2.text()
        has_file = bool(self._pdf_path)
        has_pw = bool(pw1)
        match = pw1 == pw2

        if has_pw and not match:
            self._pw_err.setText("Passwords do not match.")
        else:
            self._pw_err.setText("")

        self._save_btn.setEnabled(has_file and has_pw and match)

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------

    def _save(self):
        user_pw = self._user_pw.text()
        owner_pw = self._owner_pw.text() or user_pw

        if not user_pw:
            return

        out_name = self._out_entry.text().strip() or "protected.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        default_dir = str(Path(self._pdf_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Encrypted PDF",
            str(Path(default_dir) / out_name),
            "PDF Files (*.pdf)",
        )
        if not out_path:
            return

        perms = 0
        perm_flag_map = {
            "print": fitz.PDF_PERM_PRINT,
            "print_hq": fitz.PDF_PERM_PRINT_HQ,
            "copy": fitz.PDF_PERM_COPY,
            "modify": fitz.PDF_PERM_MODIFY,
            "annotate": fitz.PDF_PERM_ANNOTATE,
            "forms": fitz.PDF_PERM_FORM,
            "assemble": fitz.PDF_PERM_ASSEMBLE,
            "accessibility": fitz.PDF_PERM_ACCESSIBILITY,
        }
        for key, flag in perm_flag_map.items():
            if self._perm_checks[key].isChecked():
                perms |= flag

        enc_const = ENC_MAP[self._enc_id]

        self._save_btn.setEnabled(False)
        self._status_lbl.setText("Encrypting...")

        self._worker = _AddPasswordWorker(
            self._pdf_path, out_path, enc_const, user_pw, owner_pw, perms
        )
        self._worker.finished.connect(self._on_save_done)
        self._worker.failed.connect(self._on_save_failed)
        self._worker.start()

    def _on_save_done(self, out_path: str):
        self._status_lbl.setText(f"Saved: {Path(out_path).name}")
        self._status_lbl.setStyleSheet(
            f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
        )
        self._save_btn.setEnabled(True)

    def _on_save_failed(self, msg: str):
        QMessageBox.critical(self, "Save failed", msg)
        self._status_lbl.setText("Save failed.")
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
