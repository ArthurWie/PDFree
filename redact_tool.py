"""Redact Tool – permanently black out sensitive content in a PDF.

PySide6. Loaded by main.py when the user clicks "Manual Redaction".
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
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QCursor,
    QDragEnterEvent,
    QDropEvent,
)

from colors import (
    BLUE,
    BLUE_HOVER,
    GREEN,
    GREEN_HOVER,
    RED,
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
from utils import _fitz_pix_to_qpixmap

try:
    import fitz
except ImportError:
    fitz = None

RENDER_SCALE = 1.5


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


# ===========================================================================
# Redact Canvas
# ===========================================================================


class _RedactCanvas(QWidget):
    rects_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = None
        self._page_w = 1.0
        self._page_h = 1.0
        # list of (x0,y0,x1,y1) in page coords
        self._rects: list[tuple] = []
        self._dragging = False
        self._drag_sx = 0
        self._drag_sy = 0
        self._drag_ex = 0
        self._drag_ey = 0
        self._ox = 0
        self._oy = 0
        self._dw = 1
        self._dh = 1

        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    def set_page(self, pixmap, page_w, page_h):
        self._pixmap = pixmap
        self._page_w = max(page_w, 1.0)
        self._page_h = max(page_h, 1.0)
        self._rects = []
        self.update()

    def set_rects(self, rects):
        self._rects = list(rects)
        self.update()

    def get_rects(self):
        return list(self._rects)

    def clear_rects(self):
        self._rects.clear()
        self.rects_changed.emit()
        self.update()

    def _screen_to_page(self, sx, sy):
        px = (sx - self._ox) / self._dw * self._page_w
        py = (sy - self._oy) / self._dh * self._page_h
        return (
            max(0.0, min(self._page_w, px)),
            max(0.0, min(self._page_h, py)),
        )

    def _page_to_screen(self, px, py):
        return (
            self._ox + px / self._page_w * self._dw,
            self._oy + py / self._page_h * self._dh,
        )

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(G100))

        if self._pixmap is None or self._pixmap.isNull():
            p.setPen(QColor(G400))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Load a PDF, then drag to\nmark redaction areas")
            return

        cw, ch = self.width(), self.height()
        pw, ph = self._pixmap.width(), self._pixmap.height()
        scale = min((cw - 48) / pw, (ch - 48) / ph, 1.0)
        dw, dh = int(pw * scale), int(ph * scale)
        ox = (cw - dw) // 2
        oy = (ch - dh) // 2
        self._ox, self._oy, self._dw, self._dh = ox, oy, dw, dh

        # Shadow + page
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 28))
        p.drawRoundedRect(ox + 4, oy + 4, dw, dh, 4, 4)
        scaled = self._pixmap.scaled(dw, dh,
                                     Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap(ox, oy, scaled)

        # Draw existing redaction boxes (solid black)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0))
        for (rx0, ry0, rx1, ry1) in self._rects:
            sx0, sy0 = self._page_to_screen(rx0, ry0)
            sx1, sy1 = self._page_to_screen(rx1, ry1)
            p.drawRect(int(sx0), int(sy0), int(sx1 - sx0), int(sy1 - sy0))

        # Draw in-progress drag rect (red outline + semi-transparent black fill)
        if self._dragging:
            xs = sorted([self._drag_sx, self._drag_ex])
            ys = sorted([self._drag_sy, self._drag_ey])
            rx, ry = xs[0], ys[0]
            rw, rh = xs[1] - xs[0], ys[1] - ys[0]
            p.setBrush(QColor(0, 0, 0, 160))
            p.setPen(QPen(QColor(RED), 2))
            p.drawRect(rx, ry, rw, rh)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._pixmap:
            pos = event.position()
            sx = max(self._ox, min(self._ox + self._dw, int(pos.x())))
            sy = max(self._oy, min(self._oy + self._dh, int(pos.y())))
            self._dragging = True
            self._drag_sx = sx
            self._drag_sy = sy
            self._drag_ex = sx
            self._drag_ey = sy
            self.update()

    def mouseMoveEvent(self, event):
        if self._dragging:
            pos = event.position()
            self._drag_ex = max(self._ox, min(self._ox + self._dw, int(pos.x())))
            self._drag_ey = max(self._oy, min(self._oy + self._dh, int(pos.y())))
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            pos = event.position()
            self._drag_ex = max(self._ox, min(self._ox + self._dw, int(pos.x())))
            self._drag_ey = max(self._oy, min(self._oy + self._dh, int(pos.y())))

            xs = sorted([self._drag_sx, self._drag_ex])
            ys = sorted([self._drag_sy, self._drag_ey])
            if xs[1] - xs[0] < 4 or ys[1] - ys[0] < 4:
                self.update()
                return

            x0, y0 = self._screen_to_page(xs[0], ys[0])
            x1, y1 = self._screen_to_page(xs[1], ys[1])
            self._rects.append((x0, y0, x1, y1))
            self.rects_changed.emit()
            self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._pixmap:
            pos = event.position()
            px, py = self._screen_to_page(int(pos.x()), int(pos.y()))
            # Remove the first rect containing this point
            for i, (rx0, ry0, rx1, ry1) in enumerate(self._rects):
                if rx0 <= px <= rx1 and ry0 <= py <= ry1:
                    self._rects.pop(i)
                    self.rects_changed.emit()
                    self.update()
                    break


# ===========================================================================
# RedactTool
# ===========================================================================


class RedactTool(QWidget):
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
        self._doc = None
        self._total_pages = 0
        self._current_page = 0
        # per-page redaction rects in page coordinates
        self._all_rects: dict[int, list] = {}
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
        left.setFixedWidth(300)
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
        icon_box.setPixmap(svg_pixmap("eraser", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet("background: #DBEAFE; border-radius: 8px;")
        title_row.addWidget(icon_box)
        title_lbl = QLabel("Redact PDF")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 18px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        # File
        lay.addWidget(_section("SOURCE FILE"))
        lay.addSpacing(8)
        dz = QFrame()
        dz.setFixedHeight(52)
        dz.setStyleSheet(
            f"background: rgba(249,250,251,128);"
            f" border: 2px dashed {G200}; border-radius: 12px;"
        )
        dz_h = QHBoxLayout(dz)
        dz_h.setContentsMargins(10, 0, 10, 0)
        dz_h.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(svg_pixmap("file-text", G400, 18))
        ic.setStyleSheet("border: none; background: transparent;")
        dz_h.addWidget(ic)
        dz_lbl = QLabel("Drop PDF or")
        dz_lbl.setStyleSheet(
            f"color: {G500}; font: 13px; border: none; background: transparent;"
        )
        dz_h.addWidget(dz_lbl)
        browse_btn = _btn("Browse", BLUE, BLUE_HOVER, h=30, w=80)
        browse_btn.clicked.connect(self._browse)
        dz_h.addWidget(browse_btn)
        dz_h.addStretch()
        lay.addWidget(dz)
        lay.addSpacing(8)
        self._file_lbl = QLabel("No file loaded")
        self._file_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        self._file_lbl.setWordWrap(True)
        lay.addWidget(self._file_lbl)
        lay.addSpacing(24)

        # Instructions
        lay.addWidget(_section("HOW TO REDACT"))
        lay.addSpacing(8)
        steps_lbl = QLabel(
            "1. Drag to draw black boxes over content.\n"
            "2. Double-click a box to remove it.\n"
            "3. Navigate pages with ‹ › buttons.\n"
            "4. Click Apply — content is permanently removed."
        )
        steps_lbl.setWordWrap(True)
        steps_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        lay.addWidget(steps_lbl)
        lay.addSpacing(20)

        # Clear controls
        self._rect_lbl = QLabel("No redactions on this page")
        self._rect_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        lay.addWidget(self._rect_lbl)
        lay.addSpacing(8)

        self._clear_page_btn = _btn("Clear This Page", WHITE, "#FEE2E2", RED,
                                    border=True, h=32)
        self._clear_page_btn.setEnabled(False)
        self._clear_page_btn.clicked.connect(self._clear_page)
        lay.addWidget(self._clear_page_btn)

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
        self._out_entry.setPlaceholderText("output_redacted.pdf")
        self._out_entry.setFixedHeight(36)
        self._out_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        bot.addWidget(self._out_entry)

        warn_lbl = QLabel("Redaction is permanent and cannot be undone.")
        warn_lbl.setWordWrap(True)
        warn_lbl.setStyleSheet(
            f"color: {RED}; font: 11px; border: none; background: transparent;"
        )
        bot.addWidget(warn_lbl)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )
        bot.addWidget(self._status_lbl)

        self._save_btn = _btn("Apply Redactions & Save", GREEN, GREEN_HOVER, h=42)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save)
        bot.addWidget(self._save_btn)

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
        tb.setSpacing(12)

        self._toolbar_lbl = QLabel("Draw over content to redact it")
        self._toolbar_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._toolbar_lbl)
        tb.addStretch()

        _arrow_ss = (
            f"QPushButton {{ border: 1px solid {G200}; border-radius: 6px;"
            f" background: {WHITE}; color: {G700}; font: bold 15px; }}"
            f"QPushButton:hover {{ background: {G100}; }}"
            f"QPushButton:disabled {{ color: {G300}; background: {G100}; }}"
        )
        prev_btn = QPushButton("‹")
        prev_btn.setFixedSize(32, 32)
        prev_btn.setStyleSheet(_arrow_ss)
        prev_btn.clicked.connect(self._prev_page)
        tb.addWidget(prev_btn)

        self._page_lbl = QLabel("")
        self._page_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        tb.addWidget(self._page_lbl)

        next_btn = QPushButton("›")
        next_btn.setFixedSize(32, 32)
        next_btn.setStyleSheet(_arrow_ss)
        next_btn.clicked.connect(self._next_page)
        tb.addWidget(next_btn)

        v.addWidget(toolbar)

        self._canvas = _RedactCanvas()
        self._canvas.rects_changed.connect(self._on_rects_changed)
        v.addWidget(self._canvas, 1)
        return right

    # -----------------------------------------------------------------------
    # File loading
    # -----------------------------------------------------------------------

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if path:
            self._load_file(path)

    def _load_file(self, path):
        if self._doc:
            try:
                self._doc.close()
            except Exception:
                pass
        try:
            self._doc = fitz.open(path)
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Could not open PDF:\n{exc}")
            return

        self._pdf_path = path
        self._total_pages = self._doc.page_count
        self._current_page = 0
        self._all_rects.clear()
        self._file_lbl.setText(Path(path).name)
        self._out_entry.setText(f"{Path(path).stem}_redacted.pdf")
        self._save_btn.setEnabled(True)
        self._show_page()

    def _show_page(self):
        if not self._doc:
            return
        page = self._doc[self._current_page]
        mat = fitz.Matrix(RENDER_SCALE, RENDER_SCALE)
        pix = page.get_pixmap(matrix=mat)
        pm = _fitz_pix_to_qpixmap(pix)
        self._canvas.set_page(pm, page.rect.width, page.rect.height)
        rects = self._all_rects.get(self._current_page, [])
        self._canvas.set_rects(rects)
        self._page_lbl.setText(f"{self._current_page + 1} / {self._total_pages}")
        self._toolbar_lbl.setText(
            f"{Path(self._pdf_path).name} — page {self._current_page + 1}"
        )
        self._update_rect_label()

    def _prev_page(self):
        self._save_current_rects()
        if self._current_page > 0:
            self._current_page -= 1
            self._show_page()

    def _next_page(self):
        self._save_current_rects()
        if self._current_page < self._total_pages - 1:
            self._current_page += 1
            self._show_page()

    def _save_current_rects(self):
        rects = self._canvas.get_rects()
        if rects:
            self._all_rects[self._current_page] = rects
        elif self._current_page in self._all_rects:
            del self._all_rects[self._current_page]

    # -----------------------------------------------------------------------
    # Redaction controls
    # -----------------------------------------------------------------------

    def _on_rects_changed(self):
        self._save_current_rects()
        self._update_rect_label()

    def _update_rect_label(self):
        n = len(self._canvas.get_rects())
        if n == 0:
            self._rect_lbl.setText("No redactions on this page")
            self._clear_page_btn.setEnabled(False)
        else:
            self._rect_lbl.setText(f"{n} redaction{'s' if n != 1 else ''} on this page")
            self._clear_page_btn.setEnabled(True)

    def _clear_page(self):
        self._canvas.clear_rects()

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------

    def _save(self):
        self._save_current_rects()
        total_rects = sum(len(v) for v in self._all_rects.values())
        if total_rects == 0:
            QMessageBox.warning(self, "No redactions",
                                "Draw at least one redaction box before saving.")
            return

        out_name = self._out_entry.text().strip() or "redacted.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        default_dir = str(Path(self._pdf_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save Redacted PDF",
            str(Path(default_dir) / out_name),
            "PDF Files (*.pdf)",
        )
        if not out_path:
            return

        self._save_btn.setEnabled(False)
        self._status_lbl.setText("Applying redactions...")
        QApplication.processEvents()

        try:
            doc = fitz.open(self._pdf_path)
            for page_idx, rects in self._all_rects.items():
                page = doc[page_idx]
                for (x0, y0, x1, y1) in rects:
                    page.add_redact_annot(
                        fitz.Rect(x0, y0, x1, y1),
                        fill=(0, 0, 0),
                    )
                page.apply_redactions()
            doc.save(out_path, garbage=3, deflate=True)
            doc.close()
            self._status_lbl.setText(f"Saved: {Path(out_path).name}")
            self._status_lbl.setStyleSheet(
                f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
            )
            self._modified = False
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            self._status_lbl.setText("Save failed.")
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
        if self._doc:
            try:
                self._doc.close()
            except Exception:
                pass
            self._doc = None
