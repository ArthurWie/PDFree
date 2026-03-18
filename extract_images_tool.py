"""Extract Images Tool – extract all embedded images from a PDF to a folder.

PySide6. Loaded by main.py when the user clicks "Extract Images".
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
    QGridLayout,
    QFileDialog,
    QMessageBox,
    QProgressBar,
    QApplication,
    QComboBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import (
    QPixmap,
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

FORMAT_OPTIONS = ["PNG", "JPEG"]
GRID_COLS = 4
THUMB_SIZE = 96


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 ** 2:.2f} MB"


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


def _combo(options: list) -> QComboBox:
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


# ===========================================================================
# ExtractImagesTool
# ===========================================================================


class ExtractImagesTool(QWidget):
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
        self._images: list = []  # list of (page_idx, xref, w, h)
        self._thumb_timer = QTimer(self)
        self._thumb_timer.setSingleShot(True)
        self._thumb_timer.timeout.connect(self._render_thumbs_deferred)
        self._thumb_queue: list = []

        self._build_ui()
        self.setAcceptDrops(True)

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self):
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
        icon_box.setPixmap(svg_pixmap("image", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet("background: #DBEAFE; border-radius: 8px;")
        title_row.addWidget(icon_box)

        title_lbl = QLabel("Extract Images")
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

        drop_zone = QFrame()
        drop_zone.setFixedHeight(56)
        drop_zone.setStyleSheet(
            f"background: rgba(249,250,251,128);"
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

        # Export format
        lay.addWidget(_section("EXPORT FORMAT"))
        lay.addSpacing(8)
        self._fmt_combo = _combo(FORMAT_OPTIONS)
        lay.addWidget(self._fmt_combo)
        lay.addSpacing(24)

        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # Bottom action area
        bottom = QWidget()
        bottom.setStyleSheet(f"background: {WHITE}; border-top: 1px solid {G200};")
        bot_lay = QVBoxLayout(bottom)
        bot_lay.setContentsMargins(24, 16, 24, 20)
        bot_lay.setSpacing(10)

        bot_lay.addWidget(_section("OUTPUT FOLDER"))

        out_row = QHBoxLayout()
        out_row.setSpacing(6)
        self._folder_entry = QLineEdit()
        self._folder_entry.setPlaceholderText("Same as PDF")
        self._folder_entry.setFixedHeight(36)
        self._folder_entry.setReadOnly(True)
        self._folder_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
            f" font: 12px; color: {G700}; background: {G100};"
        )
        out_row.addWidget(self._folder_entry, 1)
        folder_btn = _btn("…", G100, G200, G700, border=True, h=36, w=36)
        folder_btn.clicked.connect(self._browse_folder)
        out_row.addWidget(folder_btn)
        bot_lay.addLayout(out_row)

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

        self._extract_btn = _btn("Extract Images", GREEN, GREEN_HOVER, h=42)
        self._extract_btn.setEnabled(False)
        self._extract_btn.clicked.connect(self._extract)
        bot_lay.addWidget(self._extract_btn)

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
        tb.setSpacing(0)
        self._toolbar_lbl = QLabel("Load a PDF to begin")
        self._toolbar_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._toolbar_lbl)
        tb.addStretch()
        v.addWidget(toolbar)

        self._grid_scroll = QScrollArea()
        self._grid_scroll.setWidgetResizable(True)
        self._grid_scroll.setStyleSheet("border: none; background: transparent;")
        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet(f"background: {G100};")
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setContentsMargins(20, 20, 20, 20)
        self._grid_layout.setSpacing(12)
        self._grid_scroll.setWidget(self._grid_widget)
        v.addWidget(self._grid_scroll, 1)
        return right

    # -----------------------------------------------------------------------
    # File loading
    # -----------------------------------------------------------------------

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF Files (*.pdf)"
        )
        if path:
            self._load_file(path)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self._folder_entry.setText(folder)

    def _load_file(self, path: str):
        try:
            doc = fitz.open(path)
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Could not open PDF:\n{exc}")
            return

        self._pdf_path = path
        self._folder_entry.setText(str(Path(path).parent))
        self._status_lbl.setText("")

        self._images = self._discover_images(doc)
        doc.close()

        n = len(self._images)
        name = Path(path).name
        self._toolbar_lbl.setText(f"{n} image{'s' if n != 1 else ''} found in {name}")
        self._extract_btn.setEnabled(n > 0)
        self._build_grid()

    def _discover_images(self, doc) -> list:
        images = []
        for page_idx in range(doc.page_count):
            for img_info in doc.get_page_images(page_idx, full=True):
                xref = img_info[0]
                images.append((page_idx, xref, img_info[2], img_info[3]))

        seen = set()
        unique = []
        for item in images:
            if item[1] not in seen:
                seen.add(item[1])
                unique.append(item)
        return unique

    def _build_grid(self):
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._images:
            empty_lbl = QLabel("No embedded images found.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet(
                f"color: {G400}; font: 14px; background: transparent; border: none;"
            )
            self._grid_layout.addWidget(empty_lbl, 0, 0, 1, GRID_COLS)
            return

        self._thumb_cells: list = []
        for i, (page_idx, xref, w, h) in enumerate(self._images):
            cell = self._make_thumb_cell(i, page_idx, w, h)
            row, col = divmod(i, GRID_COLS)
            self._grid_layout.addWidget(cell, row, col)
            self._thumb_cells.append(cell)

        self._thumb_queue = list(range(len(self._images)))
        self._thumb_timer.start(0)

    def _make_thumb_cell(self, idx: int, page_idx: int, w: int, h: int) -> QFrame:
        cell = QFrame()
        cell.setFixedSize(THUMB_SIZE + 16, THUMB_SIZE + 36)
        cell.setStyleSheet(
            f"background: {WHITE}; border: 1px solid {G200}; border-radius: 6px;"
        )
        cell_lay = QVBoxLayout(cell)
        cell_lay.setContentsMargins(4, 4, 4, 4)
        cell_lay.setSpacing(4)

        img_lbl = QLabel()
        img_lbl.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_lbl.setStyleSheet("border: none; background: transparent;")
        img_lbl.setProperty("img_idx", idx)
        cell_lay.addWidget(img_lbl)

        cap_lbl = QLabel(f"Page {page_idx + 1} · {w}×{h}")
        cap_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap_lbl.setStyleSheet(
            f"color: {G500}; font: 10px; border: none; background: transparent;"
        )
        cap_lbl.setWordWrap(False)
        cell_lay.addWidget(cap_lbl)

        cell.setProperty("img_lbl_ref", img_lbl)
        return cell

    def _render_thumbs_deferred(self):
        if not self._thumb_queue or not self._pdf_path:
            return
        batch = self._thumb_queue[:6]
        self._thumb_queue = self._thumb_queue[6:]
        try:
            doc = fitz.open(self._pdf_path)
            for idx in batch:
                if idx >= len(self._images):
                    continue
                _, xref, _, _ = self._images[idx]
                try:
                    img_data = doc.extract_image(xref)
                    pix = QPixmap()
                    pix.loadFromData(img_data["image"])
                    if not pix.isNull():
                        thumb = pix.scaled(
                            THUMB_SIZE,
                            THUMB_SIZE,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        if idx < len(self._thumb_cells):
                            img_lbl = self._thumb_cells[idx].property("img_lbl_ref")
                            if img_lbl:
                                img_lbl.setPixmap(thumb)
                except Exception:
                    pass
            doc.close()
        except Exception:
            pass
        if self._thumb_queue:
            self._thumb_timer.start(0)

    # -----------------------------------------------------------------------
    # Extraction
    # -----------------------------------------------------------------------

    def _extract(self):
        if not self._pdf_path or not self._images:
            return

        out_dir = Path(self._folder_entry.text().strip() or str(Path(self._pdf_path).parent))
        fmt = self._fmt_combo.currentText().lower()
        ext = "jpg" if fmt == "jpeg" else "png"

        self._progress.setValue(0)
        self._progress.show()
        self._extract_btn.setEnabled(False)
        self._status_lbl.setText("Extracting...")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )
        QApplication.processEvents()

        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            doc = fitz.open(self._pdf_path)
            try:
                for i, (page_idx, xref, w, h) in enumerate(self._images):
                    img_data = doc.extract_image(xref)
                    raw = img_data["image"]
                    out_file = out_dir / f"image_{i + 1:04d}_p{page_idx + 1}.{ext}"
                    src_ext = img_data.get("ext", "")
                    if ext == src_ext or (ext == "jpg" and src_ext in ("jpg", "jpeg")):
                        out_file.write_bytes(raw)
                    else:
                        pix = fitz.Pixmap(raw)
                        if pix.alpha:
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                        pix.save(str(out_file))
                    self._progress.setValue(int((i + 1) / len(self._images) * 100))
                    QApplication.processEvents()
            finally:
                doc.close()

            n = len(self._images)
            self._status_lbl.setText(
                f"Extracted {n} image{'s' if n != 1 else ''} to {out_dir.name}."
            )
            self._status_lbl.setStyleSheet(
                f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Extraction failed", str(exc))
            self._status_lbl.setText("Extraction failed.")
            self._status_lbl.setStyleSheet(
                "color: red; font: 12px; border: none; background: transparent;"
            )
        finally:
            self._extract_btn.setEnabled(bool(self._images))
            self._progress.hide()

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

    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------

    def cleanup(self):
        self._thumb_timer.stop()
