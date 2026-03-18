"""Remove Password Tool – strip encryption from a password-protected PDF.

PySide6. Loaded by main.py when the user clicks "Remove Password".
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
    QApplication,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QDragEnterEvent,
    QDropEvent,
)

from colors import (
    BLUE,
    BLUE_HOVER,
    GREEN,
    GREEN_HOVER,
    RED,
    RED_DIM,
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

try:
    import fitz
except ImportError:
    fitz = None


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
# RemovePasswordTool
# ===========================================================================


class RemovePasswordTool(QWidget):
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
        self._needs_pass = False

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
        icon_box.setPixmap(svg_pixmap("unlock", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet("background: #DBEAFE; border-radius: 8px;")
        title_row.addWidget(icon_box)

        title_lbl = QLabel("Remove Password")
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

        # Status badge
        self._status_badge = QFrame()
        self._status_badge.setFixedHeight(40)
        self._status_badge.setStyleSheet(
            f"background: {G100}; border: 1px solid {G200}; border-radius: 8px;"
        )
        badge_lay = QHBoxLayout(self._status_badge)
        badge_lay.setContentsMargins(12, 0, 12, 0)
        badge_lay.setSpacing(8)
        self._badge_icon = QLabel()
        self._badge_icon.setPixmap(svg_pixmap("lock", G400, 16))
        self._badge_icon.setStyleSheet("border: none; background: transparent;")
        badge_lay.addWidget(self._badge_icon)
        self._badge_lbl = QLabel("Load a file to check encryption status")
        self._badge_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        badge_lay.addWidget(self._badge_lbl, 1)
        lay.addWidget(self._status_badge)
        lay.addSpacing(24)

        # Password section
        lay.addWidget(_section("PASSWORD"))
        lay.addSpacing(8)

        pw_row = QHBoxLayout()
        pw_row.setSpacing(8)
        pw_row.setContentsMargins(0, 0, 0, 0)

        self._pw_field = QLineEdit()
        self._pw_field.setPlaceholderText("Enter PDF password")
        self._pw_field.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_field.setFixedHeight(38)
        self._pw_field.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        self._pw_field.returnPressed.connect(self._try_unlock)
        pw_row.addWidget(self._pw_field, 1)

        self._unlock_btn = _btn("Unlock", BLUE, BLUE_HOVER, h=38, w=80)
        self._unlock_btn.setEnabled(False)
        self._unlock_btn.clicked.connect(self._try_unlock)
        pw_row.addWidget(self._unlock_btn)
        lay.addLayout(pw_row)
        lay.addSpacing(6)

        self._pw_err = QLabel("")
        self._pw_err.setStyleSheet(
            "color: #EF4444; font: 12px; background: transparent; border: none;"
        )
        lay.addWidget(self._pw_err)

        self._unlocked_lbl = QLabel("")
        self._unlocked_lbl.setStyleSheet(
            f"color: {EMERALD}; font: 12px; background: transparent; border: none;"
        )
        lay.addWidget(self._unlocked_lbl)

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
        self._out_entry.setPlaceholderText("output_unlocked.pdf")
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

        self._save_btn = _btn("Remove Password & Save", GREEN, GREEN_HOVER, h=42)
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

        tip_title = QLabel("How it works")
        tip_title.setStyleSheet(
            f"color: {G900}; font: bold 14px; background: transparent; border: none;"
        )
        ic.addWidget(tip_title)

        steps = [
            "Load any password-protected PDF.",
            "Enter the current password to unlock it.",
            "Save a new copy without any encryption.",
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
            f"background: rgba(249,250,251,128);"
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
            needs_pass = bool(doc.needs_pass)
            doc.close()
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Could not open PDF:\n{exc}")
            return

        self._pdf_path = path
        self._needs_pass = needs_pass
        self._unlocked_doc = None

        name = Path(path).name
        self._file_lbl.setText(name)
        self._toolbar_lbl.setText(name)
        self._out_entry.setText(f"{Path(path).stem}_unlocked.pdf")
        self._pw_err.setText("")
        self._unlocked_lbl.setText("")
        self._result_lbl.setText("")

        if needs_pass:
            self._status_badge.setStyleSheet(
                f"background: {RED_DIM}; border: 1px solid #FECACA; border-radius: 8px;"
            )
            self._badge_icon.setPixmap(svg_pixmap("lock", RED, 16))
            self._badge_lbl.setText("Password-protected")
            self._badge_lbl.setStyleSheet(
                f"color: {RED}; font: bold 12px; background: transparent; border: none;"
            )
            self._unlock_btn.setEnabled(True)
            self._save_btn.setEnabled(False)
        else:
            self._status_badge.setStyleSheet(
                "background: #ECFDF5; border: 1px solid #6EE7B7; border-radius: 8px;"
            )
            self._badge_icon.setPixmap(svg_pixmap("unlock", EMERALD, 16))
            self._badge_lbl.setText("Not encrypted — no password needed")
            self._badge_lbl.setStyleSheet(
                f"color: {EMERALD}; font: bold 12px; background: transparent; border: none;"
            )
            self._unlock_btn.setEnabled(False)
            self._save_btn.setEnabled(True)

    # -----------------------------------------------------------------------
    # Unlock
    # -----------------------------------------------------------------------

    def _try_unlock(self):
        if not self._pdf_path:
            return
        pw = self._pw_field.text()
        if not pw:
            self._pw_err.setText("Enter the password first.")
            return

        try:
            doc = fitz.open(self._pdf_path)
            result = doc.authenticate(pw)
            doc.close()
        except Exception as exc:
            self._pw_err.setText(f"Error: {exc}")
            return

        if result:
            self._pw_err.setText("")
            self._unlocked_lbl.setText("Password accepted.")
            self._save_btn.setEnabled(True)
        else:
            self._pw_err.setText("Wrong password — try again.")
            self._unlocked_lbl.setText("")
            self._save_btn.setEnabled(False)

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------

    def _save(self):
        out_name = self._out_entry.text().strip() or "unlocked.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        default_dir = str(Path(self._pdf_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save Unlocked PDF",
            str(Path(default_dir) / out_name),
            "PDF Files (*.pdf)",
        )
        if not out_path:
            return

        self._save_btn.setEnabled(False)
        self._result_lbl.setText("Saving...")
        QApplication.processEvents()

        try:
            doc = fitz.open(self._pdf_path)
            if doc.needs_pass:
                pw = self._pw_field.text()
                if not doc.authenticate(pw):
                    QMessageBox.warning(self, "Wrong password", "Could not authenticate.")
                    return
            doc.save(out_path, encryption=fitz.PDF_ENCRYPT_NONE, garbage=3, deflate=True)
            doc.close()

            self._result_lbl.setText(f"Saved: {Path(out_path).name}")
            self._result_lbl.setStyleSheet(
                f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            self._result_lbl.setText("Save failed.")
        finally:
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
