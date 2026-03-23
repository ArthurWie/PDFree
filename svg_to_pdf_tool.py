import logging
import os
import tempfile
from pathlib import Path
from utils import assert_file_writable

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
    QProgressBar,
    QSizePolicy,
    QComboBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
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
    BLUE_MED,)
from icons import svg_pixmap

try:
    import fitz
except ImportError:
    fitz = None

try:
    import cairosvg as _cairosvg
except ImportError:
    _cairosvg = None

try:
    from svglib import svglib as _svglib
    from reportlab.graphics import renderPDF as _renderPDF
except ImportError:
    _svglib = None
    _renderPDF = None

try:
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtCore import QByteArray
    _HAS_QTSVG = True
except ImportError:
    _HAS_QTSVG = False

logger = logging.getLogger(__name__)

SUPPORTED_EXT = {".svg"}

PAGE_SIZES = {
    "A4":     (595, 842),
    "Letter": (612, 792),
    "A3":     (842, 1191),
}

_BACKEND = "cairosvg" if _cairosvg else ("svglib" if _svglib else None)


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


def _combo(options):
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


class _SvgRow(QFrame):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self._selected = False
        self.setFixedHeight(52)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"background: {WHITE}; border: 1px solid {G200}; border-radius: 8px;"
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(10)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(32, 32)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("border: none; background: transparent;")
        icon_lbl.setPixmap(svg_pixmap("file-code", G400, 20))
        lay.addWidget(icon_lbl)

        info = QVBoxLayout()
        info.setSpacing(2)
        info.setContentsMargins(0, 0, 0, 0)
        name = Path(path).name
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color: {G900}; font: 13px; border: none; background: transparent;"
        )
        name_lbl.setMinimumWidth(0)
        name_lbl.setMaximumWidth(160)
        fm = name_lbl.fontMetrics()
        name_lbl.setText(fm.elidedText(name, Qt.TextElideMode.ElideMiddle, 160))
        name_lbl.setToolTip(name)
        info.addWidget(name_lbl)
        lay.addLayout(info, 1)

        _arrow_ss = (
            f"QPushButton {{ border: 1px solid {G200}; border-radius: 5px;"
            f" background: {WHITE}; color: {G700}; font: bold 13px; }}"
            f"QPushButton:hover {{ background: {G100}; }}"
            f"QPushButton:disabled {{ color: {G300}; background: {G100}; }}"
        )

        self._up_btn = QPushButton("\u2191")
        self._up_btn.setFixedSize(26, 26)
        self._up_btn.setStyleSheet(_arrow_ss)
        self._up_btn.setToolTip("Move up")
        lay.addWidget(self._up_btn)

        self._down_btn = QPushButton("\u2193")
        self._down_btn.setFixedSize(26, 26)
        self._down_btn.setStyleSheet(_arrow_ss)
        self._down_btn.setToolTip("Move down")
        lay.addWidget(self._down_btn)

        self._del_btn = QPushButton("\u2715")
        self._del_btn.setFixedSize(26, 26)
        self._del_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid {G200}; border-radius: 5px;"
            f" background: {WHITE}; color: {RED}; font: bold 11px; }}"
            f"QPushButton:hover {{ background: #FEF2F2; border-color: {RED}; }}"
        )
        self._del_btn.setToolTip("Remove")
        lay.addWidget(self._del_btn)

    def set_selected(self, v):
        self._selected = v
        if v:
            self.setStyleSheet(
                f"background: #EFF6FF; border: 1.5px solid {BLUE}; border-radius: 8px;"
            )
        else:
            self.setStyleSheet(
                f"background: {WHITE}; border: 1px solid {G200}; border-radius: 8px;"
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            tool = self._find_tool()
            if tool:
                tool._on_row_clicked(self)

    def _find_tool(self):
        w = self.parent()
        while w:
            if isinstance(w, SvgToPdfTool):
                return w
            w = w.parent()
        return None


class _PreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._svg_data = None
        self._placeholder = True
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_svg(self, path):
        if not _HAS_QTSVG or not path:
            self._svg_data = None
            self._placeholder = True
            self.update()
            return
        try:
            data = Path(path).read_bytes()
            renderer = QSvgRenderer(QByteArray(data))
            if renderer.isValid():
                self._svg_data = data
                self._placeholder = False
            else:
                self._svg_data = None
                self._placeholder = True
        except Exception:
            self._svg_data = None
            self._placeholder = True
        self.update()

    def clear(self):
        self._svg_data = None
        self._placeholder = True
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(G100))

        if self._placeholder or self._svg_data is None:
            p.setPen(QColor(G400))
            p.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Add SVG files on the left to preview.",
            )
            return

        cw, ch = self.width(), self.height()
        pad = 36

        renderer = QSvgRenderer(QByteArray(self._svg_data))
        default_size = renderer.defaultSize()
        if default_size.width() <= 0 or default_size.height() <= 0:
            p.setPen(QColor(G400))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Cannot render SVG.")
            return

        aspect = default_size.width() / default_size.height()
        max_w = cw - pad * 2
        max_h = ch - pad * 2
        if max_w / aspect <= max_h:
            draw_w = max_w
            draw_h = int(max_w / aspect)
        else:
            draw_h = max_h
            draw_w = int(max_h * aspect)

        draw_x = (cw - draw_w) // 2
        draw_y = (ch - draw_h) // 2

        # Drop shadow
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 30))
        p.drawRoundedRect(draw_x + 4, draw_y + 4, draw_w, draw_h, 4, 4)

        # White page background
        p.setBrush(QColor(WHITE))
        p.setPen(QPen(QColor(G200), 1))
        p.drawRect(draw_x, draw_y, draw_w, draw_h)

        from PySide6.QtCore import QRectF
        renderer.render(p, QRectF(draw_x, draw_y, draw_w, draw_h))


class _SvgToPdfWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)
    progress = Signal(int)

    def __init__(self, paths, out_path, page_size):
        super().__init__()
        self._paths = paths
        self._out_path = out_path
        self._page_size = page_size

    def run(self):
        if not self._paths:
            self.failed.emit("No SVG files provided.")
            return

        if _BACKEND is None:
            self.failed.emit(
                "cairosvg is not installed.\n\n"
                "Install it with:\n  pip install cairosvg\n\n"
                "Or install svglib+reportlab:\n  pip install svglib reportlab"
            )
            return

        if fitz is None:
            self.failed.emit(
                "PyMuPDF is not installed.\n\nInstall with:\n  pip install pymupdf"
            )
            return

        try:
            assert_file_writable(Path(self._out_path))
        except PermissionError as exc:
            self.failed.emit(str(exc))
            return

        tmp_pdfs = []
        total = len(self._paths)
        try:
            for i, svg_path in enumerate(self._paths):
                if not os.path.exists(svg_path):
                    raise FileNotFoundError(f"File not found: {svg_path}")

                fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
                os.close(fd)
                tmp_pdfs.append(tmp_path)

                if _BACKEND == "cairosvg":
                    pw, ph = self._page_size
                    _cairosvg.svg2pdf(
                        url=svg_path,
                        write_to=tmp_path,
                        output_width=pw,
                        output_height=ph,
                    )
                else:
                    drawing = _svglib.svg2rlg(svg_path)
                    if drawing is None:
                        raise ValueError(f"svglib could not parse: {svg_path}")
                    _renderPDF.drawToFile(drawing, tmp_path)

                self.progress.emit(int((i + 1) / total * 90))

            merged = fitz.open()
            for tmp_path in tmp_pdfs:
                src = fitz.open(tmp_path)
                merged.insert_pdf(src)
                src.close()

            merged.save(self._out_path, garbage=3, deflate=True)
            merged.close()
            self.progress.emit(100)
            self.finished.emit(self._out_path)

        except PermissionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            logger.exception("SVG to PDF worker failed")
            self.failed.emit(str(exc))
        finally:
            for tmp_path in tmp_pdfs:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass


class SvgToPdfTool(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._paths = []
        self._rows = []
        self._selected_idx = -1
        self._worker = None

        self._build_ui()
        self.setAcceptDrops(True)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)
        body_lay.addWidget(self._build_left_panel())
        body_lay.addWidget(self._build_right_panel(), 1)
        root.addWidget(body, 1)

    def _build_left_panel(self):
        left = QWidget()
        left.setFixedWidth(320)
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

        title_row = QHBoxLayout()
        title_row.setSpacing(12)
        title_row.setContentsMargins(0, 0, 0, 0)
        icon_box = QLabel()
        icon_box.setFixedSize(40, 40)
        icon_box.setPixmap(svg_pixmap("file-code", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)
        title_lbl = QLabel("SVG to PDF")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 20px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        lay.addWidget(_section("SVG FILES"))
        lay.addSpacing(8)

        dz = QFrame()
        dz.setFixedHeight(52)
        dz.setStyleSheet(
            f"background: {G100};"
            f" border: 2px dashed {G200}; border-radius: 12px;"
        )
        dz_h = QHBoxLayout(dz)
        dz_h.setContentsMargins(10, 0, 10, 0)
        dz_h.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(svg_pixmap("file-code", G400, 18))
        ic.setStyleSheet("border: none; background: transparent;")
        dz_h.addWidget(ic)
        dz_lbl = QLabel("Drop SVG files here or")
        dz_lbl.setStyleSheet(
            f"color: {G500}; font: 13px; border: none; background: transparent;"
        )
        dz_h.addWidget(dz_lbl)
        add_btn = _btn("Add", BLUE, BLUE_HOVER, h=30, w=60)
        add_btn.clicked.connect(self._browse_svgs)
        dz_h.addWidget(add_btn)
        dz_h.addStretch()
        lay.addWidget(dz)
        lay.addSpacing(10)

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet(f"background: {WHITE};")
        self._list_lay = QVBoxLayout(self._list_widget)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(5)
        self._list_lay.addStretch()
        lay.addWidget(self._list_widget)
        lay.addSpacing(8)

        rm_row = QHBoxLayout()
        rm_row.setSpacing(8)
        self._rm_btn = _btn("Remove selected", G100, G200, text_color=G700, border=True, h=30)
        self._rm_btn.setEnabled(False)
        self._rm_btn.clicked.connect(self._remove_selected)
        rm_row.addWidget(self._rm_btn)
        self._clear_btn = _btn("Clear all", G100, G200, text_color=G700, border=True, h=30)
        self._clear_btn.setEnabled(False)
        self._clear_btn.clicked.connect(self._clear_all)
        rm_row.addWidget(self._clear_btn)
        lay.addLayout(rm_row)
        lay.addSpacing(20)

        lay.addWidget(_section("PAGE SIZE"))
        lay.addSpacing(8)
        self._size_combo = _combo(list(PAGE_SIZES.keys()))
        lay.addWidget(self._size_combo)

        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        bottom = QWidget()
        bottom.setStyleSheet(f"background: {WHITE}; border-top: 1px solid {G200};")
        bot = QVBoxLayout(bottom)
        bot.setContentsMargins(24, 16, 24, 20)
        bot.setSpacing(10)

        bot.addWidget(_section("OUTPUT FILE"))
        out_row = QHBoxLayout()
        out_row.setSpacing(8)
        self._out_entry = QLineEdit("output.pdf")
        self._out_entry.setFixedHeight(36)
        self._out_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        out_row.addWidget(self._out_entry, 1)
        browse_out_btn = _btn("...", G100, G200, text_color=G700, border=True, h=36, w=36)
        browse_out_btn.clicked.connect(self._browse_output)
        out_row.addWidget(browse_out_btn)
        bot.addLayout(out_row)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )
        bot.addWidget(self._status_lbl)

        self._progress = QProgressBar()
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 100)
        self._progress.setStyleSheet(
            f"QProgressBar {{ background: {G200}; border-radius: 3px; border: none; }}"
            f"QProgressBar::chunk {{ background: {GREEN}; border-radius: 3px; }}"
        )
        self._progress.hide()
        bot.addWidget(self._progress)

        self._convert_btn = _btn("Convert to PDF", GREEN, GREEN_HOVER, h=42)
        self._convert_btn.setEnabled(False)
        self._convert_btn.clicked.connect(self._convert)
        bot.addWidget(self._convert_btn)

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
        self._toolbar_lbl = QLabel("No SVG files added")
        self._toolbar_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._toolbar_lbl)
        tb.addStretch()
        v.addWidget(toolbar)

        self._preview = _PreviewWidget()
        v.addWidget(self._preview, 1)
        return right

    def _browse_svgs(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add SVG Files", "", "SVG Files (*.svg)"
        )
        for p in paths:
            self._add_svg(p)

    def _browse_output(self):
        default = self._out_entry.text().strip() or "output.pdf"
        if self._paths:
            default = str(Path(self._paths[0]).parent / Path(default).name)
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF As", default, "PDF Files (*.pdf)"
        )
        if path:
            self._out_entry.setText(path)

    def _add_svg(self, path):
        if Path(path).suffix.lower() not in SUPPORTED_EXT:
            return
        if path in self._paths:
            return
        self._paths.append(path)
        self._rebuild_list()
        if self._selected_idx == -1:
            self._select(0)
        self._update_btn()

    def _rebuild_list(self):
        for row in self._rows:
            self._list_lay.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        self._list_lay.takeAt(self._list_lay.count() - 1)

        for i, path in enumerate(self._paths):
            row = _SvgRow(path, self._list_widget)
            row.set_selected(i == self._selected_idx)
            row._up_btn.clicked.connect(lambda _=False, idx=i: self._move_up(idx))
            row._down_btn.clicked.connect(lambda _=False, idx=i: self._move_down(idx))
            row._del_btn.clicked.connect(lambda _=False, idx=i: self._remove(idx))
            self._list_lay.addWidget(row)
            self._rows.append(row)

        self._list_lay.addStretch()

        for i, row in enumerate(self._rows):
            row._up_btn.setEnabled(i > 0)
            row._down_btn.setEnabled(i < len(self._rows) - 1)

        n = len(self._paths)
        self._toolbar_lbl.setText(
            f"{n} file{'s' if n != 1 else ''}" if n else "No SVG files added"
        )
        self._rm_btn.setEnabled(self._selected_idx >= 0 and n > 0)
        self._clear_btn.setEnabled(n > 0)

    def _move_up(self, idx):
        if idx <= 0:
            return
        self._paths[idx], self._paths[idx - 1] = self._paths[idx - 1], self._paths[idx]
        if self._selected_idx == idx:
            self._selected_idx = idx - 1
        elif self._selected_idx == idx - 1:
            self._selected_idx = idx
        self._rebuild_list()

    def _move_down(self, idx):
        if idx >= len(self._paths) - 1:
            return
        self._paths[idx], self._paths[idx + 1] = self._paths[idx + 1], self._paths[idx]
        if self._selected_idx == idx:
            self._selected_idx = idx + 1
        elif self._selected_idx == idx + 1:
            self._selected_idx = idx
        self._rebuild_list()

    def _remove(self, idx):
        self._paths.pop(idx)
        if self._selected_idx >= len(self._paths):
            self._selected_idx = len(self._paths) - 1
        self._rebuild_list()
        if self._selected_idx >= 0:
            self._select(self._selected_idx)
        else:
            self._preview.clear()
        self._update_btn()

    def _remove_selected(self):
        if self._selected_idx >= 0:
            self._remove(self._selected_idx)

    def _clear_all(self):
        self._paths.clear()
        self._selected_idx = -1
        self._rebuild_list()
        self._preview.clear()
        self._update_btn()

    def _on_row_clicked(self, row):
        idx = self._rows.index(row) if row in self._rows else -1
        if idx != -1:
            self._select(idx)

    def _select(self, idx):
        self._selected_idx = idx
        for i, row in enumerate(self._rows):
            row.set_selected(i == idx)
        if 0 <= idx < len(self._paths):
            self._preview.set_svg(self._paths[idx])
        self._rm_btn.setEnabled(True)

    def _update_btn(self):
        self._convert_btn.setEnabled(len(self._paths) > 0)

    def _convert(self):
        if not self._paths:
            return

        out_name = self._out_entry.text().strip() or "output.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        if not os.path.isabs(out_name) and self._paths:
            out_name = str(Path(self._paths[0]).parent / out_name)

        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF", out_name, "PDF Files (*.pdf)"
        )
        if not out_path:
            return

        size_key = self._size_combo.currentText()
        page_size = PAGE_SIZES[size_key]

        self._progress.setValue(0)
        self._progress.show()
        self._convert_btn.setEnabled(False)
        self._status_lbl.setText("Converting...")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )

        self._worker = _SvgToPdfWorker(list(self._paths), out_path, page_size)
        self._worker.finished.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.progress.connect(self._progress.setValue)
        self._worker.start()

    def _on_done(self, out_path):
        self._status_lbl.setText(f"Saved: {Path(out_path).name}")
        self._status_lbl.setStyleSheet(
            f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
        )
        self._convert_btn.setEnabled(len(self._paths) > 0)
        self._progress.hide()

    def _on_failed(self, msg):
        QMessageBox.critical(self, "Conversion failed", msg)
        self._status_lbl.setText("Conversion failed.")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )
        self._convert_btn.setEnabled(len(self._paths) > 0)
        self._progress.hide()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if Path(path).suffix.lower() in SUPPORTED_EXT:
                self._add_svg(path)

    def cleanup(self):
        pass
