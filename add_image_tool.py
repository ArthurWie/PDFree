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
    QSizePolicy,
    QApplication,
    QSpinBox,
    QComboBox,
    QCheckBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import (
    QPainter,
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
)
from icons import svg_pixmap
from utils import _fitz_pix_to_qpixmap

try:
    import fitz
except ImportError:
    fitz = None

MM_TO_PT = 2.83465

POSITION_PRESETS = {
    "Full Page":     lambda w, h: fitz.Rect(0, 0, w, h),
    "Top Left":      lambda w, h: fitz.Rect(0, 0, w * 0.4, h * 0.3),
    "Top Right":     lambda w, h: fitz.Rect(w * 0.6, 0, w, h * 0.3),
    "Top Center":    lambda w, h: fitz.Rect(w * 0.25, 0, w * 0.75, h * 0.3),
    "Bottom Left":   lambda w, h: fitz.Rect(0, h * 0.7, w * 0.4, h),
    "Bottom Right":  lambda w, h: fitz.Rect(w * 0.6, h * 0.7, w, h),
    "Bottom Center": lambda w, h: fitz.Rect(w * 0.25, h * 0.7, w * 0.75, h),
    "Center":        lambda w, h: fitz.Rect(w * 0.25, h * 0.35, w * 0.75, h * 0.65),
}

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


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


class AddImageTool(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        if fitz is None:
            lay = QVBoxLayout(self)
            lbl = QLabel("Missing dependency.\n\nInstall with:\n  pip install pymupdf")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {G500}; font: 16px;")
            lay.addWidget(lbl)
            return

        self._pdf_path = ""
        self._img_path = ""
        self._page_count = 0

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._refresh_preview)

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
        icon_box.setPixmap(svg_pixmap("file-plus", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet("background: #DBEAFE; border-radius: 8px;")
        title_row.addWidget(icon_box)

        title_lbl = QLabel("Add Image")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 20px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        # SOURCE PDF section
        sec_pdf = QLabel("SOURCE PDF")
        sec_pdf.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_pdf)
        lay.addSpacing(8)

        pdf_drop = QFrame()
        pdf_drop.setFixedHeight(56)
        pdf_drop.setStyleSheet(
            f"background: rgba(249,250,251,128);"
            f" border: 2px dashed {G200}; border-radius: 12px;"
        )
        pdz_lay = QHBoxLayout(pdf_drop)
        pdz_lay.setContentsMargins(10, 0, 10, 0)
        pdz_lay.setSpacing(8)

        pdz_icon = QLabel()
        pdz_icon.setPixmap(svg_pixmap("file-text", G400, 20))
        pdz_icon.setStyleSheet("border: none; background: transparent;")
        pdz_lay.addWidget(pdz_icon)

        pdz_lbl = QLabel("Drop PDF here or")
        pdz_lbl.setStyleSheet(
            f"color: {G500}; font: 13px; border: none; background: transparent;"
        )
        pdz_lay.addWidget(pdz_lbl)

        pdf_browse_btn = _btn("Browse", BLUE, BLUE_HOVER, h=32, w=80)
        pdf_browse_btn.clicked.connect(self._browse_file)
        pdz_lay.addWidget(pdf_browse_btn)
        pdz_lay.addStretch()
        lay.addWidget(pdf_drop)
        lay.addSpacing(24)

        # IMAGE FILE section
        sec_img = QLabel("IMAGE FILE")
        sec_img.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_img)
        lay.addSpacing(8)

        img_drop = QFrame()
        img_drop.setFixedHeight(56)
        img_drop.setStyleSheet(
            f"background: rgba(249,250,251,128);"
            f" border: 2px dashed {G200}; border-radius: 12px;"
        )
        idz_lay = QHBoxLayout(img_drop)
        idz_lay.setContentsMargins(10, 0, 10, 0)
        idz_lay.setSpacing(8)

        idz_icon = QLabel()
        idz_icon.setPixmap(svg_pixmap("image", G400, 20))
        idz_icon.setStyleSheet("border: none; background: transparent;")
        idz_lay.addWidget(idz_icon)

        idz_lbl = QLabel("Drop image here or")
        idz_lbl.setStyleSheet(
            f"color: {G500}; font: 13px; border: none; background: transparent;"
        )
        idz_lay.addWidget(idz_lbl)

        img_browse_btn = _btn("Browse", BLUE, BLUE_HOVER, h=32, w=80)
        img_browse_btn.clicked.connect(self._browse_image)
        idz_lay.addWidget(img_browse_btn)
        idz_lay.addStretch()
        lay.addWidget(img_drop)
        lay.addSpacing(10)

        # Image preview row
        img_preview_row = QHBoxLayout()
        img_preview_row.setContentsMargins(0, 0, 0, 0)
        img_preview_row.setSpacing(10)

        self._img_thumb = QLabel()
        self._img_thumb.setFixedSize(64, 64)
        self._img_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_thumb.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; background: {G100};"
        )
        img_preview_row.addWidget(self._img_thumb)

        self._img_name_lbl = QLabel("No image selected")
        self._img_name_lbl.setWordWrap(True)
        self._img_name_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        img_preview_row.addWidget(self._img_name_lbl, 1)
        lay.addLayout(img_preview_row)
        lay.addSpacing(24)

        # TARGET PAGE section
        sec_page = QLabel("TARGET PAGE")
        sec_page.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_page)
        lay.addSpacing(8)

        page_row = QHBoxLayout()
        page_row.setContentsMargins(0, 0, 0, 0)
        page_row.setSpacing(10)

        page_lbl = QLabel("Page")
        page_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        page_row.addWidget(page_lbl)

        self._page_spin = QSpinBox()
        self._page_spin.setRange(1, 1)
        self._page_spin.setValue(1)
        self._page_spin.setFixedHeight(32)
        self._page_spin.setEnabled(False)
        self._page_spin.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 8px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        self._page_spin.valueChanged.connect(
            lambda: self._preview_timer.start(400)
        )
        page_row.addWidget(self._page_spin)
        page_row.addStretch()
        lay.addLayout(page_row)
        lay.addSpacing(24)

        # POSITION & SIZE section
        sec_pos = QLabel("POSITION & SIZE")
        sec_pos.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_pos)
        lay.addSpacing(8)

        self._pos_combo = QComboBox()
        self._pos_combo.addItems([
            "Full Page", "Top Left", "Top Right", "Top Center",
            "Bottom Left", "Bottom Right", "Bottom Center", "Center", "Custom",
        ])
        self._pos_combo.setFixedHeight(32)
        self._pos_combo.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 8px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        self._pos_combo.currentIndexChanged.connect(self._on_preset_changed)
        lay.addWidget(self._pos_combo)
        lay.addSpacing(10)

        # Custom fields (2x2 grid)
        self._custom_widget = QWidget()
        self._custom_widget.setStyleSheet("background: transparent;")
        cust_grid = QGridLayout(self._custom_widget)
        cust_grid.setContentsMargins(0, 0, 0, 0)
        cust_grid.setSpacing(8)

        def _entry_field(placeholder):
            e = QLineEdit()
            e.setPlaceholderText(placeholder)
            e.setFixedHeight(32)
            e.setStyleSheet(
                f"border: 1px solid {G200}; border-radius: 6px; padding: 0 8px;"
                f" font: 13px; color: {G900}; background: {WHITE};"
            )
            return e

        x_lbl = QLabel("X (mm)")
        x_lbl.setStyleSheet(f"color: {G700}; font: 12px; background: transparent; border: none;")
        y_lbl = QLabel("Y (mm)")
        y_lbl.setStyleSheet(f"color: {G700}; font: 12px; background: transparent; border: none;")
        w_lbl = QLabel("W (mm)")
        w_lbl.setStyleSheet(f"color: {G700}; font: 12px; background: transparent; border: none;")
        h_lbl = QLabel("H (mm)")
        h_lbl.setStyleSheet(f"color: {G700}; font: 12px; background: transparent; border: none;")

        self._x_entry = _entry_field("20")
        self._y_entry = _entry_field("20")
        self._w_entry = _entry_field("50")
        self._h_entry = _entry_field("50")

        for entry in (self._x_entry, self._y_entry, self._w_entry, self._h_entry):
            entry.textChanged.connect(lambda: self._preview_timer.start(400))

        cust_grid.addWidget(x_lbl, 0, 0)
        cust_grid.addWidget(self._x_entry, 1, 0)
        cust_grid.addWidget(y_lbl, 0, 1)
        cust_grid.addWidget(self._y_entry, 1, 1)
        cust_grid.addWidget(w_lbl, 2, 0)
        cust_grid.addWidget(self._w_entry, 3, 0)
        cust_grid.addWidget(h_lbl, 2, 1)
        cust_grid.addWidget(self._h_entry, 3, 1)

        self._custom_widget.hide()
        lay.addWidget(self._custom_widget)
        lay.addSpacing(10)

        self._chk_aspect = QCheckBox("Keep aspect ratio")
        self._chk_aspect.setChecked(True)
        self._chk_aspect.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        self._chk_aspect.stateChanged.connect(
            lambda: self._preview_timer.start(400)
        )
        lay.addWidget(self._chk_aspect)

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
        self._out_entry.setPlaceholderText("output_img.pdf")
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

        self._add_btn = _btn("Add Image", GREEN, GREEN_HOVER, h=42)
        self._add_btn.setEnabled(False)
        self._add_btn.clicked.connect(self._add_image)
        bot_lay.addWidget(self._add_btn)

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

        self._prev_btn = _btn("‹", WHITE, G100, text_color=G700, border=True, h=32, w=32)
        self._prev_btn.setEnabled(False)
        self._prev_btn.clicked.connect(self._prev_page)
        tb.addWidget(self._prev_btn)

        self._toolbar_lbl = QLabel("Load a PDF to preview")
        self._toolbar_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._toolbar_lbl)

        self._next_btn = _btn("›", WHITE, G100, text_color=G700, border=True, h=32, w=32)
        self._next_btn.setEnabled(False)
        self._next_btn.clicked.connect(self._next_page)
        tb.addWidget(self._next_btn)

        tb.addStretch()
        v.addWidget(toolbar)

        # Canvas inside scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        canvas_container = QWidget()
        canvas_container.setStyleSheet(f"background: {G100};")
        c_lay = QVBoxLayout(canvas_container)
        c_lay.setContentsMargins(24, 24, 24, 24)
        c_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._canvas = QLabel("Load a PDF to preview")
        self._canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._canvas.setStyleSheet(
            f"color: {G400}; font: 16px; background: transparent; border: none;"
        )
        c_lay.addWidget(self._canvas)

        scroll.setWidget(canvas_container)
        v.addWidget(scroll, 1)
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

    def _load_file(self, path: str):
        try:
            doc = fitz.open(path)
            page_count = doc.page_count
            doc.close()
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Could not open PDF:\n{exc}")
            return

        self._pdf_path = path
        self._page_count = page_count
        stem = Path(path).stem
        self._out_entry.setText(f"{stem}_img.pdf")
        self._status_lbl.setText("")

        self._page_spin.setRange(1, page_count)
        self._page_spin.setValue(1)
        self._page_spin.setEnabled(True)

        self._toolbar_lbl.setText(Path(path).name)
        self._prev_btn.setEnabled(page_count > 1)
        self._next_btn.setEnabled(page_count > 1)

        self._update_add_btn()
        self._preview_timer.start(400)

    def _browse_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if path:
            self._load_image(path)

    def _load_image(self, path: str):
        self._img_path = path
        pix = QPixmap(path)
        if pix.isNull():
            QMessageBox.warning(self, "Error", "Could not load image.")
            self._img_path = ""
            return
        thumb = pix.scaled(
            64, 64,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._img_thumb.setPixmap(thumb)
        self._img_name_lbl.setText(Path(path).name)
        self._update_add_btn()
        self._preview_timer.start(400)

    def _update_add_btn(self):
        self._add_btn.setEnabled(bool(self._pdf_path) and bool(self._img_path))

    # -----------------------------------------------------------------------
    # Preset / custom fields
    # -----------------------------------------------------------------------

    def _on_preset_changed(self):
        is_custom = self._pos_combo.currentText() == "Custom"
        self._custom_widget.setVisible(is_custom)
        self._preview_timer.start(400)

    # -----------------------------------------------------------------------
    # Page navigation
    # -----------------------------------------------------------------------

    def _prev_page(self):
        v = self._page_spin.value()
        if v > 1:
            self._page_spin.setValue(v - 1)

    def _next_page(self):
        v = self._page_spin.value()
        if v < self._page_count:
            self._page_spin.setValue(v + 1)

    # -----------------------------------------------------------------------
    # Preview
    # -----------------------------------------------------------------------

    def _get_rect(self, page_w: float, page_h: float):
        preset = self._pos_combo.currentText()
        if preset == "Custom":
            try:
                x = float(self._x_entry.text() or "20")
                y = float(self._y_entry.text() or "20")
                ww = float(self._w_entry.text() or "50")
                hh = float(self._h_entry.text() or "50")
            except ValueError:
                x, y, ww, hh = 20.0, 20.0, 50.0, 50.0
            return fitz.Rect(
                x * MM_TO_PT,
                y * MM_TO_PT,
                (x + ww) * MM_TO_PT,
                (y + hh) * MM_TO_PT,
            )
        return POSITION_PRESETS[preset](page_w, page_h)

    def _refresh_preview(self):
        if not self._pdf_path:
            self._canvas.setText("Load a PDF to preview")
            self._canvas.setPixmap(QPixmap())
            return

        page_idx = self._page_spin.value() - 1

        try:
            doc = fitz.open(self._pdf_path)
            try:
                mat = fitz.Matrix(1.2, 1.2)
                page = doc[page_idx]
                page_w = page.rect.width
                page_h = page.rect.height
                pix = page.get_pixmap(matrix=mat)
                page_qpix = _fitz_pix_to_qpixmap(pix)
            finally:
                doc.close()
        except Exception:
            return

        result = QPixmap(page_qpix)

        if self._img_path:
            rect = self._get_rect(page_w, page_h)
            p = QPainter(result)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            scale = result.width() / page_w
            rx0 = int(rect.x0 * scale)
            ry0 = int(rect.y0 * scale)
            rw = max(1, int(rect.width * scale))
            rh = max(1, int(rect.height * scale))
            img_pix = QPixmap(self._img_path).scaled(
                rw, rh,
                Qt.AspectRatioMode.KeepAspectRatio if self._chk_aspect.isChecked()
                else Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            p.drawPixmap(rx0, ry0, img_pix)
            p.end()

        self._canvas.setText("")
        self._canvas.setPixmap(
            result.scaled(
                self._canvas.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pdf_path:
            self._preview_timer.start(400)

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------

    def _add_image(self):
        if not self._pdf_path or not self._img_path:
            return

        out_name = self._out_entry.text().strip() or "output_img.pdf"
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

        self._progress.setValue(0)
        self._progress.show()
        self._add_btn.setEnabled(False)
        self._status_lbl.setText("Adding image...")
        QApplication.processEvents()

        try:
            doc = fitz.open(self._pdf_path)
            try:
                page_idx = self._page_spin.value() - 1
                page = doc[page_idx]
                w, h = page.rect.width, page.rect.height
                rect = self._get_rect(w, h)
                keep_aspect = self._chk_aspect.isChecked()
                page.insert_image(rect, filename=self._img_path, keep_proportion=keep_aspect)
                self._progress.setValue(80)
                QApplication.processEvents()
                doc.save(out_path, garbage=3, deflate=True)
                self._progress.setValue(100)
            finally:
                doc.close()

            self._status_lbl.setText("Image added successfully.")
            self._status_lbl.setStyleSheet(
                f"color: {GREEN}; font: 12px; border: none; background: transparent;"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Failed", str(exc))
            self._status_lbl.setText("Failed to add image.")
            self._status_lbl.setStyleSheet(
                "color: red; font: 12px; border: none; background: transparent;"
            )
        finally:
            self._add_btn.setEnabled(True)
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
            ext = Path(path).suffix.lower()
            if ext == ".pdf":
                self._load_file(path)
                break
            if ext in _IMAGE_EXTS:
                self._load_image(path)
                break

    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------

    def cleanup(self):
        self._preview_timer.stop()
