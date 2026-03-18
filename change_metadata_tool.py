"""Change Metadata Tool – view and edit PDF document metadata.

PySide6. Loaded by main.py when the user clicks "Change Metadata".
"""

from pathlib import Path

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

# fitz metadata dict keys and their display labels
_FIELDS = [
    ("title",        "Title"),
    ("author",       "Author"),
    ("subject",      "Subject"),
    ("keywords",     "Keywords"),
    ("creator",      "Creator"),
    ("producer",     "Producer"),
    ("creationDate", "Creation Date"),
    ("modDate",      "Modification Date"),
]


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


def _field_input(placeholder: str, multiline: bool = False):
    if multiline:
        w = QTextEdit()
        w.setPlaceholderText(placeholder)
        w.setFixedHeight(72)
        w.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 6px 10px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        return w
    w = QLineEdit()
    w.setPlaceholderText(placeholder)
    w.setFixedHeight(36)
    w.setStyleSheet(
        f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
        f" font: 13px; color: {G900}; background: {WHITE};"
    )
    return w


# ===========================================================================
# ChangeMetadataTool
# ===========================================================================


class ChangeMetadataTool(QWidget):
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
        left.setFixedWidth(400)
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

        # Title row
        title_row = QHBoxLayout()
        title_row.setSpacing(12)
        title_row.setContentsMargins(0, 0, 0, 0)

        icon_box = QLabel()
        icon_box.setFixedSize(40, 40)
        icon_box.setPixmap(svg_pixmap("pen-line", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet("background: #DBEAFE; border-radius: 8px;")
        title_row.addWidget(icon_box)

        title_lbl = QLabel("Change Metadata")
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

        # Metadata fields
        lay.addWidget(_section("METADATA FIELDS"))
        lay.addSpacing(12)

        self._inputs: dict[str, QLineEdit | QTextEdit] = {}
        multiline_keys = {"keywords"}

        for key, label in _FIELDS:
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"color: {G700}; font: 13px; background: transparent; border: none;"
            )
            lay.addWidget(lbl)
            lay.addSpacing(4)
            widget = _field_input(f"Enter {label.lower()}", multiline=key in multiline_keys)
            self._inputs[key] = widget
            lay.addWidget(widget)
            lay.addSpacing(12)

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
        self._out_entry.setPlaceholderText("output.pdf")
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

        self._save_btn = _btn("Save with New Metadata", GREEN, GREEN_HOVER, h=42)
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
        cl.setSpacing(16)

        # Current metadata display card (populated after load)
        self._meta_card = QFrame()
        self._meta_card.setStyleSheet(
            f"background: {WHITE}; border: 1px solid {G200}; border-radius: 12px;"
        )
        self._meta_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._meta_card_lay = QVBoxLayout(self._meta_card)
        self._meta_card_lay.setContentsMargins(24, 20, 24, 20)
        self._meta_card_lay.setSpacing(0)

        card_title = QLabel("Current Metadata")
        card_title.setStyleSheet(
            f"color: {G900}; font: bold 14px; background: transparent; border: none;"
        )
        self._meta_card_lay.addWidget(card_title)
        self._meta_card_lay.addSpacing(12)

        self._meta_rows: dict[str, QLabel] = {}
        for key, label in _FIELDS:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            key_lbl = QLabel(f"{label}:")
            key_lbl.setFixedWidth(120)
            key_lbl.setStyleSheet(
                f"color: {G500}; font: 12px; background: transparent; border: none;"
            )
            row.addWidget(key_lbl)
            val_lbl = QLabel("—")
            val_lbl.setWordWrap(True)
            val_lbl.setStyleSheet(
                f"color: {G700}; font: 12px; background: transparent; border: none;"
            )
            row.addWidget(val_lbl, 1)
            self._meta_rows[key] = val_lbl
            self._meta_card_lay.addLayout(row)
            self._meta_card_lay.addSpacing(4)

        cl.addWidget(self._meta_card)

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

        steps = [
            "Load a PDF to read its current metadata.",
            "Edit any field on the left — leave fields blank to clear them.",
            "Save to write a new PDF with the updated metadata.",
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

        cl.addWidget(tip_card)
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
            meta = doc.metadata
            doc.close()
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Could not open PDF:\n{exc}")
            return

        self._pdf_path = path
        name = Path(path).name
        self._file_lbl.setText(name)
        self._toolbar_lbl.setText(name)
        self._out_entry.setText(f"{Path(path).stem}_metadata.pdf")
        self._result_lbl.setText("")
        self._save_btn.setEnabled(True)

        # Populate left-panel inputs and right-panel display
        for key, _ in _FIELDS:
            value = meta.get(key, "") or ""
            widget = self._inputs[key]
            if isinstance(widget, QTextEdit):
                widget.setPlainText(value)
            else:
                widget.setText(value)
            self._meta_rows[key].setText(value if value else "—")

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------

    def _save(self):
        out_name = self._out_entry.text().strip() or "output_metadata.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        default_dir = str(Path(self._pdf_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF",
            str(Path(default_dir) / out_name),
            "PDF Files (*.pdf)",
        )
        if not out_path:
            return

        self._save_btn.setEnabled(False)
        self._result_lbl.setText("Saving...")
        QApplication.processEvents()

        new_meta = {}
        for key, _ in _FIELDS:
            widget = self._inputs[key]
            if isinstance(widget, QTextEdit):
                new_meta[key] = widget.toPlainText().strip()
            else:
                new_meta[key] = widget.text().strip()

        try:
            doc = fitz.open(self._pdf_path)
            doc.set_metadata(new_meta)
            doc.save(out_path, garbage=3, deflate=True)
            doc.close()

            self._result_lbl.setText(f"Saved: {Path(out_path).name}")
            self._result_lbl.setStyleSheet(
                f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
            )
            self._modified = False
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
