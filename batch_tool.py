"""Batch Tool – apply one operation to multiple PDFs at once."""

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
    QScrollArea,
    QHBoxLayout,
    QVBoxLayout,
    QFileDialog,
    QMessageBox,
    QProgressBar,
    QSizePolicy,
    QStackedWidget,
    QSpinBox,
)
from PySide6.QtCore import Qt, QObject, QThread, Signal
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
    RED,
    BLUE_MED,
)
from icons import svg_pixmap, svg_icon

try:
    import fitz
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Operation catalogue
# ---------------------------------------------------------------------------

_COMPRESS_PRESETS = ["Lossless", "Print (150 DPI)", "eBook (96 DPI)", "Screen (72 DPI)"]
_COMPRESS_DPI = [None, 150, 96, 72]

_ROTATE_OPTIONS = ["90° Clockwise", "90° Counter-clockwise", "180°"]
_ROTATE_DEGREES = [90, 270, 180]

_PN_POSITIONS = [
    "Bottom Center",
    "Bottom Right",
    "Bottom Left",
    "Top Center",
    "Top Right",
    "Top Left",
]
_PN_FORMATS = ["1", "Page 1", "1 / N", "Page 1 of N"]

_ENC_OPTIONS = ["AES 256-bit", "AES 128-bit", "RC4 128-bit"]


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
# Pure operation functions (run in worker thread, no Qt)
# ---------------------------------------------------------------------------


def _run_compress(src: str, dst: str, preset_idx: int) -> None:
    dpi = _COMPRESS_DPI[preset_idx]
    doc = fitz.open(src)
    try:
        if dpi is None:
            doc.save(
                dst,
                garbage=4,
                deflate=True,
                deflate_images=True,
                deflate_fonts=True,
                clean=True,
                use_objstms=True,
            )
        else:
            out = fitz.open()
            scale = dpi / 72.0
            mat = fitz.Matrix(scale, scale)
            try:
                for i in range(doc.page_count):
                    page = doc.load_page(i)
                    pix = page.get_pixmap(matrix=mat)
                    new_page = out.new_page(
                        width=page.rect.width, height=page.rect.height
                    )
                    new_page.insert_image(new_page.rect, pixmap=pix)
                out.save(dst, garbage=4, deflate=True, deflate_images=True)
            finally:
                out.close()
    finally:
        doc.close()


def _run_rotate(src: str, dst: str, degrees: int) -> None:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(src)
    writer = PdfWriter()
    for page in reader.pages:
        page.rotate(degrees)
        writer.add_page(page)
    with open(dst, "wb") as f:
        writer.write(f)


def _run_add_page_numbers(
    src: str, dst: str, pos_idx: int, fmt_idx: int, start: int
) -> None:
    doc = fitz.open(src)
    total = doc.page_count
    try:
        for i in range(total):
            page = doc.load_page(i)
            num = start + i
            fmt = _PN_FORMATS[fmt_idx]
            if fmt == "1":
                text = str(num)
            elif fmt == "Page 1":
                text = f"Page {num}"
            elif fmt == "1 / N":
                text = f"{num} / {total}"
            else:
                text = f"Page {num} of {total}"

            pw, ph = page.rect.width, page.rect.height
            pos_name = _PN_POSITIONS[pos_idx]
            margin = 24
            rect_h = 18
            if "Bottom" in pos_name:
                y0, y1 = ph - margin - rect_h, ph - margin
            else:
                y0, y1 = margin, margin + rect_h
            if "Center" in pos_name:
                x0, x1 = pw * 0.25, pw * 0.75
                align = fitz.TEXT_ALIGN_CENTER
            elif "Right" in pos_name:
                x0, x1 = pw - 200, pw - margin
                align = fitz.TEXT_ALIGN_RIGHT
            else:
                x0, x1 = margin, 200
                align = fitz.TEXT_ALIGN_LEFT
            page.insert_textbox(
                fitz.Rect(x0, y0, x1, y1), text, fontsize=11, align=align
            )
        doc.save(dst, garbage=3, deflate=True)
    finally:
        doc.close()


def _run_add_password(src: str, dst: str, password: str, enc_idx: int) -> None:
    enc_map = [
        fitz.PDF_ENCRYPT_AES_256,
        fitz.PDF_ENCRYPT_AES_128,
        fitz.PDF_ENCRYPT_RC4_128,
    ]
    doc = fitz.open(src)
    try:
        doc.save(dst, encryption=enc_map[enc_idx], user_pw=password, owner_pw=password)
    finally:
        doc.close()


def _run_remove_password(src: str, dst: str, password: str) -> None:
    doc = fitz.open(src)
    try:
        if doc.needs_pass and not doc.authenticate(password):
            raise ValueError("incorrect password")
        doc.save(dst, encryption=fitz.PDF_ENCRYPT_NONE, garbage=3, deflate=True)
    finally:
        doc.close()


def _run_watermark(src: str, dst: str, kwargs: dict) -> None:
    text = kwargs.get("text", "WATERMARK")
    opacity = kwargs.get("opacity", 0.3)
    color = kwargs.get("color", (128, 128, 128))
    rgb = tuple(c / 255.0 for c in color)
    fontsize = kwargs.get("fontsize", 48)
    doc = fitz.open(src)
    try:
        font = fitz.Font("helv")
        for page in doc:
            tw = fitz.TextWriter(page.rect)
            w, h = page.rect.width, page.rect.height
            text_len = font.text_length(text, fontsize)
            cx = max(0.0, w / 2 - text_len / 2)
            cy = h / 2 + fontsize * 0.35
            tw.append(fitz.Point(cx, cy), text, fontsize=fontsize, font=font)
            pivot = fitz.Point(w / 2, h / 2)
            mat = fitz.Matrix(-45)
            tw.write_text(page, color=rgb, opacity=opacity, morph=(pivot, mat))
        doc.save(dst, garbage=3, deflate=True)
    finally:
        doc.close()


def _run_pdf_to_pdfa(src: str, dst: str, kwargs: dict) -> None:
    from pdfa_tool import convert_to_pdfa

    conformance = kwargs.get("conformance", "PDF/A-2b")
    part_map = {"PDF/A-1b": ("1", "B"), "PDF/A-2b": ("2", "B"), "PDF/A-3b": ("3", "B")}
    if conformance not in part_map:
        raise ValueError(f"Unsupported conformance level: {conformance!r}")
    part, conf = part_map[conformance]
    convert_to_pdfa(src, dst, part=part, conformance=conf)


# ---------------------------------------------------------------------------
# Operation registry
# ---------------------------------------------------------------------------

BATCH_REGISTRY = {
    "compress": {
        "label": "Compress",
        "run": lambda src, dst, kw: _run_compress(src, dst, kw["preset_idx"]),
    },
    "rotate": {
        "label": "Rotate Pages",
        "run": lambda src, dst, kw: _run_rotate(src, dst, kw["degrees"]),
    },
    "add_page_numbers": {
        "label": "Add Page Numbers",
        "run": lambda src, dst, kw: _run_add_page_numbers(
            src, dst, kw["pos_idx"], kw["fmt_idx"], kw["start"]
        ),
    },
    "add_password": {
        "label": "Add Password",
        "run": lambda src, dst, kw: _run_add_password(
            src, dst, kw["password"], kw["enc_idx"]
        ),
    },
    "remove_password": {
        "label": "Remove Password",
        "run": lambda src, dst, kw: _run_remove_password(src, dst, kw["password"]),
    },
    "watermark": {
        "label": "Add Watermark",
        "run": _run_watermark,
    },
    "pdf_to_pdfa": {
        "label": "Convert to PDF/A",
        "run": _run_pdf_to_pdfa,
    },
}

_OPS = [(op_id, entry["label"]) for op_id, entry in BATCH_REGISTRY.items()]


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------


class _BatchWorker(QThread):
    file_done = Signal(int)
    file_failed = Signal(int, str)
    all_done = Signal()

    def __init__(self, tasks: list, op_id: str, settings: dict, out_dir: str):
        super().__init__()
        self._tasks = tasks
        self._op_id = op_id
        self._settings = settings
        self._out_dir = out_dir

    def run(self) -> None:
        for i, src in enumerate(self._tasks):
            stem = Path(src).stem
            dst = str(Path(self._out_dir) / f"{stem}_batch.pdf")
            try:
                assert_file_writable(Path(dst))
                backup_original(Path(src))
                self._process(src, dst)
                self.file_done.emit(i)
            except PermissionError as exc:
                self.file_failed.emit(i, str(exc))
            except Exception as exc:
                logger.exception("batch failed: %s", src)
                self.file_failed.emit(i, str(exc))
        self.all_done.emit()

    def _process(self, src: str, dst: str) -> None:
        entry = BATCH_REGISTRY.get(self._op_id)
        if entry is None:
            raise ValueError(f"Unknown operation: {self._op_id}")
        entry["run"](src, dst, self._settings)


class _BatchItemWorker(QThread):
    done = Signal(int)
    failed = Signal(int, str)

    def __init__(self, index: int, src: str, dst: str, op_id: str, settings: dict):
        super().__init__()
        self._index = index
        self._src = src
        self._dst = dst
        self._op_id = op_id
        self._settings = settings

    def run(self) -> None:
        import worker_semaphore

        worker_semaphore.acquire()
        try:
            entry = BATCH_REGISTRY[self._op_id]
            entry["run"](self._src, self._dst, self._settings)
            self.done.emit(self._index)
        except Exception as exc:
            logger.exception("batch item failed: %s", self._src)
            self.failed.emit(self._index, str(exc))
        finally:
            worker_semaphore.release()


class _BatchCoordinator(QObject):
    all_done = Signal()

    def __init__(
        self, tasks: list, op_id: str, settings: dict, out_dir: str, on_done, on_failed
    ):
        super().__init__()
        self._tasks = tasks
        self._op_id = op_id
        self._settings = settings
        self._out_dir = out_dir
        self._on_done = on_done
        self._on_failed = on_failed
        self._workers: list[_BatchItemWorker] = []
        self._pending = len(tasks)

    def start(self) -> None:
        for i, src in enumerate(self._tasks):
            stem = Path(src).stem
            dst = str(Path(self._out_dir) / f"{stem}_batch.pdf")
            w = _BatchItemWorker(i, src, dst, self._op_id, self._settings)
            w.done.connect(self._item_done)
            w.failed.connect(self._item_failed)
            self._workers.append(w)
            w.start()
            w.finished.connect(w.deleteLater)

    def _item_done(self, index: int) -> None:
        self._on_done(index)
        self._check_complete()

    def _item_failed(self, index: int, msg: str) -> None:
        self._on_failed(index, msg)
        self._check_complete()

    def _check_complete(self) -> None:
        self._pending -= 1
        if self._pending <= 0:
            self.all_done.emit()


# ---------------------------------------------------------------------------
# File row widget
# ---------------------------------------------------------------------------


class _FileRow(QFrame):
    remove_requested = Signal(int)

    _STATUS_STYLES = {
        "pending": (G400, "Pending"),
        "running": (BLUE, "Processing..."),
        "done": (EMERALD, "Done"),
        "error": (RED, "Error"),
    }

    def __init__(self, index: int, path: str, page_count: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.setFixedHeight(52)
        self.setStyleSheet(f"background: {WHITE}; border-bottom: 1px solid {G100};")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(10)

        icon = QLabel()
        icon.setPixmap(svg_pixmap("file-text", G400, 18))
        icon.setFixedWidth(20)
        icon.setStyleSheet("border: none; background: transparent;")
        lay.addWidget(icon)

        name_lbl = QLabel(Path(path).name)
        name_lbl.setStyleSheet(
            f"color: {G900}; font: 13px; border: none; background: transparent;"
        )
        name_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        name_lbl.setToolTip(path)
        lay.addWidget(name_lbl, 1)

        pages_lbl = QLabel(f"{page_count}p")
        pages_lbl.setFixedWidth(34)
        pages_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        pages_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )
        lay.addWidget(pages_lbl)

        self._status_lbl = QLabel("Pending")
        self._status_lbl.setFixedWidth(80)
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(
            f"color: {G400}; font: 11px; border: 1px solid {G200};"
            " border-radius: 4px; padding: 1px 4px; background: transparent;"
        )
        lay.addWidget(self._status_lbl)

        self._remove_btn = QPushButton()
        self._remove_btn.setFixedSize(24, 24)
        self._remove_btn.setIcon(svg_icon("x", G400, 14))
        self._remove_btn.setStyleSheet(
            f"border: none; background: transparent; border-radius: 4px;"
            f" QPushButton:hover {{ background: {G100}; }}"
        )
        self._remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.index))
        lay.addWidget(self._remove_btn)

    def set_status(self, status: str, msg: str = "") -> None:
        color, label = self._STATUS_STYLES.get(status, (G400, status))
        display = msg[:16] if (status == "error" and msg) else label
        self._status_lbl.setText(display)
        self._status_lbl.setStyleSheet(
            f"color: {color}; font: 11px; border: 1px solid {color};"
            " border-radius: 4px; padding: 1px 4px; background: transparent;"
        )
        self._status_lbl.setToolTip(msg if status == "error" else "")

    def set_interactive(self, enabled: bool) -> None:
        self._remove_btn.setVisible(enabled)


# ---------------------------------------------------------------------------
# BatchTool
# ---------------------------------------------------------------------------


class BatchTool(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._modified = False
        self._worker = None
        self._files: list[str] = []
        self._file_rows: list[_FileRow] = []

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
        icon_box.setPixmap(svg_pixmap("layers", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)
        title_lbl = QLabel("Batch Process")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 20px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        # Operation selector
        op_sec = QLabel("OPERATION")
        op_sec.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(op_sec)
        lay.addSpacing(8)

        self._op_combo = QComboBox()
        for _, label in _OPS:
            self._op_combo.addItem(label)
        self._op_combo.setFixedHeight(36)
        self._op_combo.setStyleSheet(
            f"QComboBox {{ border: 1px solid {G200}; border-radius: 6px;"
            f" padding: 0 10px; font: 13px; color: {G900}; background: {WHITE}; }}"
            f"QComboBox::drop-down {{ border: none; }}"
            f"QComboBox QAbstractItemView {{ border: 1px solid {G200}; }}"
        )
        self._op_combo.currentIndexChanged.connect(self._set_operation)
        lay.addWidget(self._op_combo)
        lay.addSpacing(20)

        # Settings stacked widget
        settings_sec = QLabel("SETTINGS")
        settings_sec.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(settings_sec)
        lay.addSpacing(8)

        self._settings_stack = QStackedWidget()
        self._settings_stack.addWidget(self._build_compress_settings())
        self._settings_stack.addWidget(self._build_rotate_settings())
        self._settings_stack.addWidget(self._build_pn_settings())
        self._settings_stack.addWidget(self._build_add_password_settings())
        self._settings_stack.addWidget(self._build_remove_password_settings())
        lay.addWidget(self._settings_stack)
        lay.addSpacing(20)

        # Output folder
        out_sec = QLabel("OUTPUT FOLDER")
        out_sec.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(out_sec)
        lay.addSpacing(8)

        out_row = QHBoxLayout()
        out_row.setSpacing(6)
        out_row.setContentsMargins(0, 0, 0, 0)
        self._out_entry = QLineEdit()
        self._out_entry.setPlaceholderText("Same folder as input files")
        self._out_entry.setFixedHeight(36)
        self._out_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        self._out_entry.textChanged.connect(self._update_run_btn)
        out_row.addWidget(self._out_entry, 1)
        browse_out = _btn(
            "Browse", G100, G200, text_color=G700, border=True, h=36, w=70
        )
        browse_out.clicked.connect(self._browse_out_dir)
        out_row.addWidget(browse_out)
        lay.addLayout(out_row)

        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # Bottom action area
        bottom = QWidget()
        bottom.setStyleSheet(f"background: {WHITE}; border-top: 1px solid {G200};")
        bot_lay = QVBoxLayout(bottom)
        bot_lay.setContentsMargins(24, 16, 24, 20)
        bot_lay.setSpacing(10)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )
        bot_lay.addWidget(self._status_lbl)

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

        self._run_btn = _btn("Run Batch", GREEN, GREEN_HOVER, h=42)
        self._run_btn.setEnabled(False)
        self._run_btn.clicked.connect(self._run_batch)
        bot_lay.addWidget(self._run_btn)

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
        tb.setSpacing(8)

        self._file_count_lbl = QLabel("No files added")
        self._file_count_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._file_count_lbl)
        tb.addStretch()

        clear_btn = _btn(
            "Clear All", G100, G200, text_color=G700, border=True, h=30, w=70
        )
        clear_btn.clicked.connect(self._clear_files)
        tb.addWidget(clear_btn)

        add_btn = _btn("Add Files", BLUE, BLUE_HOVER, h=30)
        add_btn.clicked.connect(self._add_files)
        tb.addWidget(add_btn)

        v.addWidget(toolbar)

        # Drop area / file list
        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setStyleSheet("border: none; background: transparent;")

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet(f"background: {WHITE};")
        self._list_lay = QVBoxLayout(self._list_widget)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(0)
        self._list_lay.addStretch()

        self._empty_lbl = QLabel("Drop PDF files here\nor click Add Files")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color: {G400}; font: 15px; border: none; background: transparent;"
        )
        self._list_lay.insertWidget(0, self._empty_lbl)

        self._list_scroll.setWidget(self._list_widget)
        v.addWidget(self._list_scroll, 1)
        return right

    # -----------------------------------------------------------------------
    # Per-operation settings panels
    # -----------------------------------------------------------------------

    def _settings_combo(self, items: list) -> QComboBox:
        cb = QComboBox()
        for item in items:
            cb.addItem(item)
        cb.setFixedHeight(34)
        cb.setStyleSheet(
            f"QComboBox {{ border: 1px solid {G200}; border-radius: 6px;"
            f" padding: 0 10px; font: 13px; color: {G900}; background: {WHITE}; }}"
            f"QComboBox::drop-down {{ border: none; }}"
            f"QComboBox QAbstractItemView {{ border: 1px solid {G200}; }}"
        )
        return cb

    def _settings_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {G700}; font: 12px; background: transparent; border: none;"
        )
        return lbl

    def _build_compress_settings(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {WHITE};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(self._settings_label("Preset"))
        self._compress_combo = self._settings_combo(_COMPRESS_PRESETS)
        lay.addWidget(self._compress_combo)
        lay.addStretch()
        return w

    def _build_rotate_settings(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {WHITE};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(self._settings_label("Direction"))
        self._rotate_combo = self._settings_combo(_ROTATE_OPTIONS)
        lay.addWidget(self._rotate_combo)
        lay.addStretch()
        return w

    def _build_pn_settings(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {WHITE};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(self._settings_label("Position"))
        self._pn_pos_combo = self._settings_combo(_PN_POSITIONS)
        lay.addWidget(self._pn_pos_combo)
        lay.addWidget(self._settings_label("Format"))
        self._pn_fmt_combo = self._settings_combo(_PN_FORMATS)
        lay.addWidget(self._pn_fmt_combo)
        lay.addWidget(self._settings_label("Start number"))
        self._pn_start = QSpinBox()
        self._pn_start.setRange(1, 9999)
        self._pn_start.setValue(1)
        self._pn_start.setFixedHeight(34)
        self._pn_start.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 8px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        lay.addWidget(self._pn_start)
        lay.addStretch()
        return w

    def _build_add_password_settings(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {WHITE};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(self._settings_label("Password"))
        self._add_pw_entry = QLineEdit()
        self._add_pw_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self._add_pw_entry.setPlaceholderText("Enter password")
        self._add_pw_entry.setFixedHeight(34)
        self._add_pw_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        self._add_pw_entry.textChanged.connect(self._update_run_btn)
        lay.addWidget(self._add_pw_entry)
        lay.addWidget(self._settings_label("Encryption"))
        self._enc_combo = self._settings_combo(_ENC_OPTIONS)
        lay.addWidget(self._enc_combo)
        lay.addStretch()
        return w

    def _build_remove_password_settings(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {WHITE};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(self._settings_label("Password"))
        self._rm_pw_entry = QLineEdit()
        self._rm_pw_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self._rm_pw_entry.setPlaceholderText("Enter current password")
        self._rm_pw_entry.setFixedHeight(34)
        self._rm_pw_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        self._rm_pw_entry.textChanged.connect(self._update_run_btn)
        lay.addWidget(self._rm_pw_entry)
        lay.addStretch()
        return w

    # -----------------------------------------------------------------------
    # File management
    # -----------------------------------------------------------------------

    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add PDF Files", "", "PDF Files (*.pdf)"
        )
        for path in paths:
            self._add_file(path)

    def _add_file(self, path: str) -> None:
        if path in self._files:
            return
        try:
            doc = fitz.open(path)
            page_count = doc.page_count
            doc.close()
        except Exception as exc:
            logger.exception("could not open pdf for batch: %s", path)
            QMessageBox.warning(self, "Error", f"Could not open PDF:\n{exc}")
            return

        idx = len(self._files)
        self._files.append(path)

        row = _FileRow(idx, path, page_count)
        row.remove_requested.connect(self._remove_file)
        self._file_rows.append(row)

        # Insert before the stretch
        stretch_idx = self._list_lay.count() - 1
        self._list_lay.insertWidget(stretch_idx, row)

        self._empty_lbl.setVisible(False)
        self._update_file_count()
        self._update_run_btn()

    def _remove_file(self, index: int) -> None:
        if index >= len(self._files):
            return
        self._files.pop(index)
        row = self._file_rows.pop(index)
        row.deleteLater()
        # Re-index remaining rows
        for i, r in enumerate(self._file_rows):
            r.index = i
        self._empty_lbl.setVisible(len(self._files) == 0)
        self._update_file_count()
        self._update_run_btn()

    def _clear_files(self) -> None:
        for row in self._file_rows:
            row.deleteLater()
        self._files.clear()
        self._file_rows.clear()
        self._empty_lbl.setVisible(True)
        self._update_file_count()
        self._update_run_btn()

    def _update_file_count(self) -> None:
        n = len(self._files)
        if n == 0:
            self._file_count_lbl.setText("No files added")
        elif n == 1:
            self._file_count_lbl.setText("1 file")
        else:
            self._file_count_lbl.setText(f"{n} files")

    # -----------------------------------------------------------------------
    # Settings / validation
    # -----------------------------------------------------------------------

    def _set_operation(self, idx: int) -> None:
        self._settings_stack.setCurrentIndex(idx)
        self._update_run_btn()

    def _browse_out_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self._out_entry.setText(path)

    def _update_run_btn(self) -> None:
        op_idx = self._op_combo.currentIndex()
        op_id = _OPS[op_idx][0]
        valid = bool(self._files)
        if op_id == "add_password" and not self._add_pw_entry.text():
            valid = False
        self._run_btn.setEnabled(valid)

    def _get_settings(self) -> dict:
        op_idx = self._op_combo.currentIndex()
        op_id = _OPS[op_idx][0]
        if op_id == "compress":
            return {"preset_idx": self._compress_combo.currentIndex()}
        if op_id == "rotate":
            return {"degrees": _ROTATE_DEGREES[self._rotate_combo.currentIndex()]}
        if op_id == "add_page_numbers":
            return {
                "pos_idx": self._pn_pos_combo.currentIndex(),
                "fmt_idx": self._pn_fmt_combo.currentIndex(),
                "start": self._pn_start.value(),
            }
        if op_id == "add_password":
            return {
                "password": self._add_pw_entry.text(),
                "enc_idx": self._enc_combo.currentIndex(),
            }
        if op_id == "remove_password":
            return {"password": self._rm_pw_entry.text()}
        return {}

    # -----------------------------------------------------------------------
    # Batch execution
    # -----------------------------------------------------------------------

    def _run_batch(self) -> None:
        op_idx = self._op_combo.currentIndex()
        op_id = _OPS[op_idx][0]

        out_dir = self._out_entry.text().strip()
        if not out_dir:
            # default: same directory as first file
            out_dir = str(Path(self._files[0]).parent)

        if not Path(out_dir).is_dir():
            QMessageBox.warning(self, "Invalid folder", "Output folder does not exist.")
            return

        settings = self._get_settings()
        for row in self._file_rows:
            row.set_status("pending")
            row.set_interactive(False)

        self._run_btn.setEnabled(False)
        self._op_combo.setEnabled(False)
        self._progress.setValue(0)
        self._progress.show()
        self._done_count = 0
        self._status_lbl.setText("Running…")

        self._worker = _BatchCoordinator(
            list(self._files),
            op_id,
            settings,
            out_dir,
            on_done=self._on_file_done,
            on_failed=self._on_file_failed,
        )
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _on_file_done(self, idx: int) -> None:
        self._file_rows[idx].set_status("done")
        self._done_count += 1
        pct = int(self._done_count / len(self._files) * 100)
        self._progress.setValue(pct)
        self._status_lbl.setText(f"Processed {self._done_count} / {len(self._files)}")

    def _on_file_failed(self, idx: int, msg: str) -> None:
        self._file_rows[idx].set_status("error", msg)
        self._done_count += 1
        pct = int(self._done_count / len(self._files) * 100)
        self._progress.setValue(pct)

    def _on_all_done(self) -> None:
        errors = sum(
            1 for r in self._file_rows if r._status_lbl.text() not in ("Done",)
        )
        ok = len(self._files) - errors
        self._status_lbl.setText(
            f"Done: {ok} succeeded, {errors} failed"
            if errors
            else f"All {ok} files processed successfully."
        )
        self._status_lbl.setStyleSheet(
            f"color: {'red' if errors else EMERALD}; font: 12px;"
            " border: none; background: transparent;"
        )
        for row in self._file_rows:
            row.set_interactive(True)
        self._run_btn.setEnabled(bool(self._files))
        self._op_combo.setEnabled(True)

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
                self._add_file(path)

    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------

    def cleanup(self) -> None:
        if self._worker is None:
            return
        if isinstance(self._worker, _BatchCoordinator):
            for w in self._worker._workers:
                if w.isRunning():
                    w.wait(5000)
        elif self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(3000)
