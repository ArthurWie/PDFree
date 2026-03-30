"""PDFree – PDF Toolbox Application (PySide6).

Run this single file to start the app:
    python main.py
"""

from __future__ import annotations

import atexit
import logging
import os
import pathlib
import sys

from logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

_TEMP_FILES: list[str] = []


def _register_temp(path: str) -> str:
    _TEMP_FILES.append(path)
    return path


def _cleanup_temps() -> None:
    for p in _TEMP_FILES:
        try:
            if os.path.exists(p):
                os.unlink(p)
        except OSError:
            pass


atexit.register(_cleanup_temps)


def resource_path(relative_path: str) -> str:
    """Return absolute path to a resource — works both in dev and in a PyInstaller .exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


_translator = None


def _install_translator(app) -> None:
    global _translator
    locale_name = QLocale.system().name()
    lang = locale_name.split("_")[0]
    translations_dir = pathlib.Path(resource_path("translations"))

    candidates = [
        translations_dir / f"pdffree_{locale_name}.qm",
        translations_dir / f"pdffree_{lang}.qm",
        translations_dir / "pdffree_en.qm",
    ]

    qm_path = None
    for candidate in candidates:
        if candidate.exists():
            qm_path = candidate
            break

    if qm_path is None:
        logger.debug("no .qm translation file found; using English fallback")
        return

    translator = QTranslator(app)
    if translator.load(str(qm_path)):
        app.installTranslator(translator)
        _translator = translator
        logger.info("loaded translation: %s", qm_path.name)
    else:
        logger.warning("could not load translation: %s", qm_path)


from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QMainWindow,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QLineEdit,
    QScrollArea,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QFileDialog,
    QMessageBox,
    QSizePolicy,
    QStackedWidget,
)
from PySide6.QtCore import Qt, QTimer, QSize, Signal, QTranslator, QLocale  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QPainter,
    QColor,
    QFont,
    QPen,
    QPainterPath,
    QCursor,
    QIcon,
    QPixmap,
    QKeySequence,
    QShortcut,
)
from icons import svg_pixmap, svg_icon, is_svg_icon  # noqa: E402
from utils import _make_back_button  # noqa: E402
from i18n import QT_TRANSLATE_NOOP, tr  # noqa: E402
import colors  # noqa: E402
from colors import (  # noqa: E402
    BG,
    WHITE,
    G100,
    G200,
    G300,
    G400,
    G500,
    G700,
    G900,
    TEAL,
    BLUE,
    GREEN,
    CORAL,
    RED,
    BLUE_ACCENT,
)

# ---------------------------------------------------------------------------
# Implemented tools  (add tool IDs here as you build them)
# ---------------------------------------------------------------------------
IMPLEMENTED = {
    "split",
    "view",
    "excerpt",
    "merge",
    "remove",
    "rotate",
    "compress",
    "add_password",
    "remove_password",
    "img_to_pdf",
    "pdf_to_img",
    "add_page_numbers",
    "change_metadata",
    "add_watermark",
    "crop",
    "pdf_to_word",
    "ocr_pdf",
    "flatten",
    "sanitize",
    "extract_images",
    "adjust_size",
    "headers_footers",
    "nup",
    "pdf_to_excel",
    "compare",
    "remove_annotations",
    "reorder",
    "manual_redaction",
    "add_image",
    "batch",
    "page_labels",
    "bookmarks",
    "pdfa",
    "sign",
    "html_to_pdf",
    "office_to_pdf",
    "pdf_to_csv",
    "form_unlock",
    "form_export",
    "validate_signature",
    "font_info",
    "svg_to_pdf",
}

# ---------------------------------------------------------------------------
# Tool definitions  –  id · display name · icon char
# ---------------------------------------------------------------------------
CATEGORIES = [
    {
        "title": QT_TRANSLATE_NOOP("PDFree", "Core"),
        "color": BLUE_ACCENT,
        "tools": [
            ("view", QT_TRANSLATE_NOOP("PDFree", "View PDF"), "eye"),
            ("excerpt", QT_TRANSLATE_NOOP("PDFree", "Excerpt Tool"), "copy"),
            ("split", QT_TRANSLATE_NOOP("PDFree", "Split"), "scissors"),
        ],
    },
    {
        "title": QT_TRANSLATE_NOOP("PDFree", "Organize"),
        "color": TEAL,
        "tools": [
            (
                "adjust_size",
                QT_TRANSLATE_NOOP("PDFree", "Adjust Page Size"),
                "maximize",
            ),
            ("crop", QT_TRANSLATE_NOOP("PDFree", "Crop PDF"), "scan-line"),
            ("merge", QT_TRANSLATE_NOOP("PDFree", "Merge"), "merge"),
            ("nup", QT_TRANSLATE_NOOP("PDFree", "N-Up Layout"), "layers"),
            ("remove", QT_TRANSLATE_NOOP("PDFree", "Remove Pages"), "file-minus"),
            ("reorder", QT_TRANSLATE_NOOP("PDFree", "Reorder Pages"), "layers"),
            ("rotate", QT_TRANSLATE_NOOP("PDFree", "Rotate"), "rotate-cw"),
        ],
    },
    {
        "title": QT_TRANSLATE_NOOP("PDFree", "Convert to PDF"),
        "color": BLUE,
        "tools": [
            ("img_to_pdf", QT_TRANSLATE_NOOP("PDFree", "Image to PDF"), "image"),
            ("html_to_pdf", QT_TRANSLATE_NOOP("PDFree", "HTML to PDF"), "file-output"),
            (
                "office_to_pdf",
                QT_TRANSLATE_NOOP("PDFree", "Office to PDF"),
                "file-text",
            ),
            ("svg_to_pdf", QT_TRANSLATE_NOOP("PDFree", "SVG to PDF"), "image"),
        ],
    },
    {
        "title": QT_TRANSLATE_NOOP("PDFree", "Convert from PDF"),
        "color": BLUE,
        "tools": [
            ("pdf_to_img", QT_TRANSLATE_NOOP("PDFree", "PDF to Image"), "image"),
            ("pdf_to_word", QT_TRANSLATE_NOOP("PDFree", "PDF to Word"), "file-text"),
            ("pdf_to_excel", QT_TRANSLATE_NOOP("PDFree", "PDF to Excel"), "file-text"),
            ("pdf_to_csv", QT_TRANSLATE_NOOP("PDFree", "PDF to CSV"), "table"),
            ("ocr_pdf", QT_TRANSLATE_NOOP("PDFree", "OCR PDF"), "scan-line"),
        ],
    },
    {
        "title": QT_TRANSLATE_NOOP("PDFree", "Sign & Security"),
        "color": GREEN,
        "tools": [
            ("add_password", QT_TRANSLATE_NOOP("PDFree", "Add Password"), "lock"),
            ("sign", QT_TRANSLATE_NOOP("PDFree", "Sign PDF"), "pen-line"),
            ("add_watermark", QT_TRANSLATE_NOOP("PDFree", "Add Watermark"), "droplets"),
            (
                "manual_redaction",
                QT_TRANSLATE_NOOP("PDFree", "Manual Redaction"),
                "eraser",
            ),
            (
                "remove_password",
                QT_TRANSLATE_NOOP("PDFree", "Remove Password"),
                "unlock",
            ),
            ("sanitize", QT_TRANSLATE_NOOP("PDFree", "Sanitize"), "eraser"),
            (
                "form_unlock",
                QT_TRANSLATE_NOOP("PDFree", "Unlock Form Fields"),
                "unlock",
            ),
            ("form_export", QT_TRANSLATE_NOOP("PDFree", "Export Form Data"), "table"),
            (
                "validate_signature",
                QT_TRANSLATE_NOOP("PDFree", "Validate Signature"),
                "shield-check",
            ),
        ],
    },
    {
        "title": QT_TRANSLATE_NOOP("PDFree", "View & Edit"),
        "color": CORAL,
        "tools": [
            ("add_image", QT_TRANSLATE_NOOP("PDFree", "Add Image"), "file-plus"),
            (
                "add_page_numbers",
                QT_TRANSLATE_NOOP("PDFree", "Add Page Numbers"),
                "file-plus",
            ),
            (
                "change_metadata",
                QT_TRANSLATE_NOOP("PDFree", "Change Metadata"),
                "pen-line",
            ),
            ("page_labels", QT_TRANSLATE_NOOP("PDFree", "Page Labels"), "file-plus"),
            ("bookmarks", QT_TRANSLATE_NOOP("PDFree", "Bookmark Editor"), "list"),
            ("compare", QT_TRANSLATE_NOOP("PDFree", "Compare PDFs"), "file-search"),
            ("extract_images", QT_TRANSLATE_NOOP("PDFree", "Extract Images"), "image"),
            ("flatten", QT_TRANSLATE_NOOP("PDFree", "Flatten"), "minimize"),
            (
                "headers_footers",
                QT_TRANSLATE_NOOP("PDFree", "Headers & Footers"),
                "pen-line",
            ),
            (
                "remove_annotations",
                QT_TRANSLATE_NOOP("PDFree", "Remove Annotations"),
                "eraser",
            ),
            ("font_info", QT_TRANSLATE_NOOP("PDFree", "Font Info"), "file-search"),
        ],
    },
    {
        "title": QT_TRANSLATE_NOOP("PDFree", "Advanced"),
        "color": RED,
        "tools": [
            ("batch", QT_TRANSLATE_NOOP("PDFree", "Batch Process"), "layers"),
            ("compress", QT_TRANSLATE_NOOP("PDFree", "Compress"), "layers"),
            ("pdfa", QT_TRANSLATE_NOOP("PDFree", "PDF/A Export"), "shield"),
        ],
    },
]

# ---------------------------------------------------------------------------
# Short descriptions for every tool (shown on cards)
# ---------------------------------------------------------------------------
TOOL_DESCRIPTIONS = {
    "view": QT_TRANSLATE_NOOP("PDFree", "Open and read any PDF file."),
    "excerpt": QT_TRANSLATE_NOOP("PDFree", "Capture regions from multiple PDFs."),
    "split": QT_TRANSLATE_NOOP(
        "PDFree", "Split by range, N pages, half, or chapter bookmarks."
    ),
    "adjust_size": QT_TRANSLATE_NOOP(
        "PDFree", "Resize pages to A4, Letter, A3, or custom dimensions."
    ),
    "crop": QT_TRANSLATE_NOOP("PDFree", "Trim pages to a custom region."),
    "merge": QT_TRANSLATE_NOOP("PDFree", "Combine multiple PDFs into one."),
    "nup": QT_TRANSLATE_NOOP(
        "PDFree", "Combine multiple pages onto each printed sheet."
    ),
    "remove": QT_TRANSLATE_NOOP("PDFree", "Delete selected pages from a PDF."),
    "reorder": QT_TRANSLATE_NOOP("PDFree", "Drag and drop pages into a new order."),
    "rotate": QT_TRANSLATE_NOOP("PDFree", "Rotate pages to any angle."),
    "img_to_pdf": QT_TRANSLATE_NOOP("PDFree", "Convert images into a PDF file."),
    "pdf_to_img": QT_TRANSLATE_NOOP("PDFree", "Export pages as PNG or JPEG files."),
    "pdf_to_word": QT_TRANSLATE_NOOP(
        "PDFree", "Convert PDF to an editable Word document."
    ),
    "pdf_to_excel": QT_TRANSLATE_NOOP(
        "PDFree", "Extract tables from PDF into an Excel file."
    ),
    "ocr_pdf": QT_TRANSLATE_NOOP(
        "PDFree", "Add a searchable text layer to scanned PDFs."
    ),
    "add_password": QT_TRANSLATE_NOOP("PDFree", "Encrypt PDF with a password."),
    "add_watermark": QT_TRANSLATE_NOOP(
        "PDFree", "Overlay custom text or image on every page."
    ),
    "manual_redaction": QT_TRANSLATE_NOOP(
        "PDFree", "Permanently black out selected regions."
    ),
    "remove_password": QT_TRANSLATE_NOOP(
        "PDFree", "Remove password protection from a PDF."
    ),
    "sanitize": QT_TRANSLATE_NOOP(
        "PDFree", "Strip JavaScript, metadata, and hidden data."
    ),
    "sign": QT_TRANSLATE_NOOP(
        "PDFree", "Sign a PDF with a PKCS#12 digital certificate."
    ),
    "add_image": QT_TRANSLATE_NOOP("PDFree", "Insert a PNG or JPEG image onto a page."),
    "add_page_numbers": QT_TRANSLATE_NOOP(
        "PDFree", "Stamp page numbers on every page."
    ),
    "change_metadata": QT_TRANSLATE_NOOP("PDFree", "Edit title, author, and keywords."),
    "compare": QT_TRANSLATE_NOOP(
        "PDFree", "Side-by-side visual or text diff of two PDFs."
    ),
    "extract_images": QT_TRANSLATE_NOOP(
        "PDFree", "Pull all embedded images out of a PDF."
    ),
    "flatten": QT_TRANSLATE_NOOP(
        "PDFree", "Bake annotations and form fields into static content."
    ),
    "headers_footers": QT_TRANSLATE_NOOP(
        "PDFree", "Stamp custom headers and footers on every page."
    ),
    "remove_annotations": QT_TRANSLATE_NOOP(
        "PDFree", "Strip all comments and markup from a PDF."
    ),
    "compress": QT_TRANSLATE_NOOP(
        "PDFree", "Reduce file size with lossless or lossy presets."
    ),
    "batch": QT_TRANSLATE_NOOP(
        "PDFree", "Apply one operation to multiple PDFs at once."
    ),
    "page_labels": QT_TRANSLATE_NOOP(
        "PDFree", "Define custom page numbering ranges (Roman, Arabic, prefix)."
    ),
    "bookmarks": QT_TRANSLATE_NOOP(
        "PDFree", "Add, remove, rename, and reorder PDF bookmarks."
    ),
    "pdfa": QT_TRANSLATE_NOOP(
        "PDFree", "Export a best-effort PDF/A-1b, -2b, or -3b archive file."
    ),
    "html_to_pdf": QT_TRANSLATE_NOOP(
        "PDFree", "Convert an HTML file or URL to a PDF document."
    ),
    "office_to_pdf": QT_TRANSLATE_NOOP(
        "PDFree", "Convert Word, PowerPoint, or Excel files to PDF via LibreOffice."
    ),
    "pdf_to_csv": QT_TRANSLATE_NOOP(
        "PDFree", "Extract tables from a PDF and export them as CSV."
    ),
    "form_unlock": QT_TRANSLATE_NOOP(
        "PDFree", "Remove read-only restrictions from all AcroForm fields."
    ),
    "form_export": QT_TRANSLATE_NOOP(
        "PDFree", "Export form field names, types, and values as JSON or CSV."
    ),
    "validate_signature": QT_TRANSLATE_NOOP(
        "PDFree", "Verify digital signatures — trust, integrity, and timestamp."
    ),
    "font_info": QT_TRANSLATE_NOOP("PDFree", "Inspect all fonts embedded in a PDF."),
    "svg_to_pdf": QT_TRANSLATE_NOOP("PDFree", "Convert SVG vector files to PDF."),
}

# ---------------------------------------------------------------------------
# Tab filter mapping  (None = show all)
# ---------------------------------------------------------------------------
TAB_CATEGORIES = {
    QT_TRANSLATE_NOOP("PDFree", "All Tools"): None,
    QT_TRANSLATE_NOOP("PDFree", "Convert"): {"Convert to PDF", "Convert from PDF"},
    QT_TRANSLATE_NOOP("PDFree", "Edit"): {
        "Core",
        "Organize",
        "View & Edit",
        "Advanced",
    },
    QT_TRANSLATE_NOOP("PDFree", "Protect"): {"Sign & Security"},
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lighten(hex_color: str, factor: float = 0.55) -> str:
    c = QColor(hex_color)
    r = int(c.red() + (255 - c.red()) * factor)
    g = int(c.green() + (255 - c.green()) * factor)
    b = int(c.blue() + (255 - c.blue()) * factor)
    return QColor(r, g, b).name()


# ---------------------------------------------------------------------------
# Custom paint widgets
# ---------------------------------------------------------------------------


class PDFIconWidget(QWidget):
    """Line-art PDF page icon drawn with QPainter (no external assets).

    When *draw_arrow* is True the icon occupies 72% of the widget height and
    a small down-arrow is drawn in the remaining space below (used in the
    Quick-Start drop zone).
    """

    _PAGE_H_RATIO = 0.72  # used only when draw_arrow=True

    def __init__(
        self,
        w: int = 28,
        h: int = 34,
        color: str = BLUE_ACCENT,
        bg: str = BG,
        draw_arrow: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._color = QColor(color)
        self._bg = QColor(bg)
        self._draw_arrow = draw_arrow
        self.setFixedSize(w, h)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), self._bg)

        W = self.width()
        H_page = (
            int(self.height() * self._PAGE_H_RATIO)
            if self._draw_arrow
            else self.height()
        )
        fold = W * 0.30
        p.setPen(QPen(self._color, 1.5))
        p.setBrush(QColor(WHITE))

        page = QPainterPath()
        page.moveTo(0, 0)
        page.lineTo(W - fold, 0)
        page.lineTo(W, fold)
        page.lineTo(W, H_page)
        page.lineTo(0, H_page)
        page.closeSubpath()
        p.drawPath(page)

        p.setBrush(Qt.BrushStyle.NoBrush)
        ear = QPainterPath()
        ear.moveTo(W - fold, 0)
        ear.lineTo(W - fold, fold)
        ear.lineTo(W, fold)
        p.drawPath(ear)

        lx0, lx1 = int(W * 0.18), int(W * 0.78)
        for ly in [H_page * 0.44, H_page * 0.57, H_page * 0.70]:
            p.drawLine(lx0, int(ly), lx1, int(ly))

        if self._draw_arrow:
            ax, ay = W // 2, H_page + 4
            p.drawLine(ax, ay, ax, ay + 10)
            p.drawLine(ax - 5, ay + 5, ax, ay + 10)
            p.drawLine(ax + 5, ay + 5, ax, ay + 10)


class RoundedIconWidget(QWidget):
    """Colored rounded-square with an SVG icon or emoji/char centred inside."""

    def __init__(self, icon: str, color: str, size: int = 46, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._color = QColor(color)
        self.setFixedSize(size, size)
        icon_px = int(size * 0.52)
        self._pixmap = (
            svg_pixmap(icon, "#FFFFFF", icon_px) if is_svg_icon(icon) else None
        )

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._color)
        p.drawRoundedRect(self.rect(), 8, 8)
        if self._pixmap and not self._pixmap.isNull():
            x = (self.width() - self._pixmap.width()) // 2
            y = (self.height() - self._pixmap.height()) // 2
            p.drawPixmap(x, y, self._pixmap)
        else:
            p.setPen(QColor(WHITE))
            p.setFont(QFont("Segoe UI Emoji", 16, QFont.Weight.Bold))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._icon)


class QuickStartZone(QWidget):
    """Drag-and-drop / click-to-browse zone."""

    file_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAcceptDrops(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 16, 0, 10)
        lay.setSpacing(0)

        icon = PDFIconWidget(
            38, 64, color=colors.BLUE_ACCENT, bg=colors.QS_BG, draw_arrow=True
        )
        lay.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(4)

        drag_lbl = QLabel(tr("Drag & Drop your PDF here"))
        drag_lbl.setStyleSheet(
            f"color: {colors.G700}; font: bold 14px 'Segoe UI'; background: transparent;"
        )
        drag_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(drag_lbl, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(6)

        browse_btn = QPushButton(tr("Or click to browse"))
        browse_btn.setFixedSize(160, 30)
        browse_btn.setStyleSheet(f"""
            QPushButton {{
                background: {colors.WHITE};
                color: {colors.G600};
                border: 1px solid {colors.G300};
                border-radius: 15px;
                font: 11px 'Segoe UI';
            }}
            QPushButton:hover {{ background: {colors.G100}; }}
        """)
        browse_btn.clicked.connect(self._browse)
        lay.addWidget(browse_btn, 0, Qt.AlignmentFlag.AlignHCenter)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(colors.QS_BG))
        pen = QPen(QColor(colors.BLUE_ACCENT), 1, Qt.PenStyle.CustomDashLine)
        pen.setDashPattern([6.0, 4.0])
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        pad = 6
        path = QPainterPath()
        path.addRoundedRect(
            pad, pad, self.width() - 2 * pad, self.height() - 2 * pad, 12, 12
        )
        p.drawPath(path)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF files (*.pdf)")
        if path:
            self.file_selected.emit(path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            if url.toLocalFile().lower().endswith(".pdf"):
                event.acceptProposedAction()

    def dropEvent(self, event):
        path = event.mimeData().urls()[0].toLocalFile()
        if path.lower().endswith(".pdf"):
            self.file_selected.emit(path)


class ToolCard(QFrame):
    """A single tool card in the grid."""

    clicked = Signal(str)  # emits tool_id

    def __init__(
        self,
        tool_id: str,
        name: str,
        icon: str,
        color: str,
        implemented: bool,
        parent=None,
    ):
        super().__init__(parent)
        self._tool_id = tool_id
        self._implemented = implemented

        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setObjectName("ToolCard")
        self._style_normal = f"""
            QFrame#ToolCard {{
                background: {colors.WHITE}; border-radius: 12px; border: 1px solid {colors.G200};
            }}"""
        self._style_hovered = f"""
            QFrame#ToolCard {{
                background: {colors.WHITE}; border-radius: 12px; border: 1px solid {colors.G300};
            }}"""
        self.setStyleSheet(self._style_normal)

        if implemented:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        icon_color = color if implemented else _lighten(color, 0.55)
        lay.addWidget(
            RoundedIconWidget(icon, icon_color, 46), 0, Qt.AlignmentFlag.AlignTop
        )

        text_lay = QVBoxLayout()
        text_lay.setSpacing(2)
        text_lay.setContentsMargins(0, 0, 0, 0)

        name_lbl = QLabel(tr(name))
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet(
            f"color: {colors.G700 if implemented else colors.G400}; "
            f"font: bold 13px 'Segoe UI'; background: transparent;"
        )
        text_lay.addWidget(name_lbl)

        desc_text = (
            tr(TOOL_DESCRIPTIONS.get(tool_id, "")) if implemented else tr("Coming Soon")
        )
        desc_color = colors.G500 if implemented else colors.SOON_TXT
        desc_lbl = QLabel(desc_text)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(
            f"color: {desc_color}; font: 11px 'Segoe UI'; background: transparent;"
        )
        text_lay.addWidget(desc_lbl)
        text_lay.addStretch()

        lay.addLayout(text_lay, 1)

    def enterEvent(self, _event):
        self.setStyleSheet(self._style_hovered)

    def leaveEvent(self, _event):
        self.setStyleSheet(self._style_normal)

    def mousePressEvent(self, event):
        if self._implemented and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._tool_id)


class RecentCard(QFrame):
    """Card shown in the Recently Used row."""

    clicked = Signal(str)

    def __init__(self, tool_id: str, name: str, icon: str, color: str, parent=None):
        super().__init__(parent)
        self._tool_id = tool_id

        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setObjectName("RecentCard")
        self._style_normal = f"""
            QFrame#RecentCard {{
                background: {colors.WHITE}; border-radius: 12px; border: 1px solid {colors.G200};
            }}"""
        self._style_hovered = f"""
            QFrame#RecentCard {{
                background: {colors.WHITE}; border-radius: 12px; border: 1px solid {colors.G300};
            }}"""
        self.setStyleSheet(self._style_normal)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        lay.addWidget(RoundedIconWidget(icon, color, 46))

        text_lay = QVBoxLayout()
        text_lay.setSpacing(2)
        text_lay.setContentsMargins(0, 0, 0, 0)

        name_lbl = QLabel(tr(name))
        name_lbl.setStyleSheet(
            f"color: {colors.G700}; font: bold 13px 'Segoe UI'; background: transparent;"
        )
        text_lay.addWidget(name_lbl)

        desc = tr(TOOL_DESCRIPTIONS.get(tool_id, ""))
        if desc:
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet(
                f"color: {colors.G500}; font: 11px 'Segoe UI'; background: transparent;"
            )
            text_lay.addWidget(desc_lbl)

        lay.addLayout(text_lay)

    def enterEvent(self, _event):
        self.setStyleSheet(self._style_hovered)

    def leaveEvent(self, _event):
        self.setStyleSheet(self._style_normal)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._tool_id)


# ═══════════════════════════════════════════════════════════════════════════
# Main Application
# ═══════════════════════════════════════════════════════════════════════════


class PDFreeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDFree")
        self.resize(1420, 880)
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(f"QMainWindow {{ background: {BG}; }}")
        _logo_path = resource_path("LOGO.svg")
        if not os.path.exists(_logo_path):
            _logo_path = resource_path("LOGO.png")
        if os.path.exists(_logo_path):
            if _logo_path.endswith(".svg"):
                from PySide6.QtSvg import QSvgRenderer

                _svg_r = QSvgRenderer(_logo_path)
                _ico_pm = QPixmap(256, 256)
                _ico_pm.fill(Qt.GlobalColor.transparent)
                _ico_p = QPainter(_ico_pm)
                _svg_r.render(_ico_p)
                _ico_p.end()
                self.setWindowIcon(QIcon(_ico_pm))
            else:
                self.setWindowIcon(QIcon(_logo_path))

        self._current_tool: object = None
        self._active_tab = "All Tools"
        self._tab_buttons: dict[str, tuple[QPushButton, QFrame]] = {}
        self._all_tool_data: list = []
        self._grid_widget: QWidget | None = None
        self._search_entry: QLineEdit | None = None
        self._home_nav_btns: dict = {}
        self._home_active_nav: str = "dashboard"

        # Library view state
        self._lib_nav_key: str = "all_files"
        self._lib_search_q: str = ""
        self._lib_scroll = None  # QScrollArea (library index 2)
        self._sel_wrap = None  # QWidget selection bar
        self._sel_count_lbl = None  # QLabel in sel bar
        self._lib_search_edit = None  # QLineEdit in header
        self._selected_files: set = set()
        self._fol_list_lay = None  # QVBoxLayout of sidebar folder list

        self._lib_search_timer = QTimer(self)
        self._lib_search_timer.setSingleShot(True)
        self._lib_search_timer.timeout.connect(self._refresh_library)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._render_tool_grid)

        # F11 fullscreen toggle
        fs_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F11), self)
        fs_shortcut.activated.connect(self._toggle_fullscreen)

        # Index 0 = home,  Index 1 = tool view
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self.show_home()

    # ==================================================================
    # NAVIGATION
    # ==================================================================

    def _cleanup_tool(self):
        if self._current_tool is not None:
            fn = getattr(self._current_tool, "cleanup", None)
            if callable(fn):
                try:
                    fn()
                except RuntimeError:
                    pass
            self._current_tool = None

    def _has_unsaved_changes(self) -> bool:
        """Return True if the current tool has unsaved modifications."""
        tool = self._current_tool
        if tool is None:
            return False
        return bool(getattr(tool, "_modified", False))

    def _prompt_save(self) -> bool:
        """Ask the user whether to save unsaved changes.

        Returns True if it is safe to continue (saved, discarded, or no changes).
        Returns False if the user cancelled.
        """
        if not self._has_unsaved_changes():
            return True

        tool = self._current_tool
        pdf_name = getattr(tool, "pdf_path", "") or "this PDF"
        import os as _os

        pdf_name = _os.path.basename(pdf_name) if pdf_name else "this PDF"

        box = QMessageBox(self)
        box.setWindowTitle("Unsaved Changes")
        box.setText(f"<b>{pdf_name}</b> has unsaved changes.")
        box.setInformativeText("Do you want to save before closing?")
        box.setIcon(QMessageBox.Icon.Warning)
        save_btn = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save_btn)
        box.exec()

        clicked = box.clickedButton()
        if clicked is cancel_btn:
            return False
        if clicked is save_btn:
            fn = getattr(tool, "_save_pdf", None)
            if callable(fn):
                fn()
        return True

    def closeEvent(self, event):
        if self._prompt_save():
            event.accept()
        else:
            event.ignore()

    def _back_to_home(self):
        if self._prompt_save():
            self.show_home()

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _toggle_theme(self) -> None:
        from theme import apply_theme, is_dark

        apply_theme(not is_dark())
        QApplication.instance().setStyleSheet(_scrollbar_css())
        self._rebuild_home()

    def _rebuild_home(self) -> None:
        # Reset home-screen state so the freshly built widgets start clean.
        self._search_timer.stop()
        self._tab_buttons.clear()
        self._all_tool_data.clear()
        self._active_tab = "All Tools"
        self._grid_widget = None
        self._search_entry = None
        self._home_nav_btns = {}
        self._home_active_nav = "dashboard"
        self._lib_nav_key = "all_files"
        self._lib_search_q = ""
        self._lib_scroll = None
        self._sel_wrap = None
        self._sel_count_lbl = None
        self._lib_search_edit = None
        self._selected_files = set()
        self._fol_list_lay = None

        old_home = self._stack.widget(0)
        new_home = self._build_home()
        self._stack.insertWidget(0, new_home)
        self._stack.removeWidget(old_home)
        old_home.deleteLater()
        # Stay on whichever screen was active (home or tool)
        if self._stack.currentIndex() != 1:
            self._stack.setCurrentIndex(0)

    def show_home(self):
        self._cleanup_tool()
        self._search_timer.stop()
        self._tab_buttons.clear()
        self._all_tool_data.clear()
        self._active_tab = "All Tools"
        self._grid_widget = None
        self._search_entry = None
        self._home_nav_btns = {}
        self._home_active_nav = "dashboard"
        self._lib_nav_key = "all_files"
        self._lib_search_q = ""
        self._lib_scroll = None
        self._sel_wrap = None
        self._sel_count_lbl = None
        self._lib_search_edit = None
        self._selected_files = set()
        self._fol_list_lay = None

        while self._stack.count():
            w = self._stack.widget(0)
            if w is not None:
                self._stack.removeWidget(w)
                w.deleteLater()

        self._stack.addWidget(self._build_home())
        self._stack.setCurrentIndex(0)

    def show_library(self):
        """Redirect to the integrated All Files view."""
        self._set_home_nav("all_files")

    def show_tool(self, tool_id: str, path: str = ""):
        if path:
            try:
                from library_page import LibraryState

                LibraryState().track(path)
            except OSError:
                pass

        if tool_id not in IMPLEMENTED:
            QMessageBox.information(
                self,
                "Coming Soon",
                "This tool is not yet implemented.\nStay tuned for future updates!",
            )
            return

        try:
            from library_page import LibraryState

            LibraryState().track_tool(tool_id)
        except Exception:
            pass

        self._cleanup_tool()

        if self._stack.count() > 1:
            w = self._stack.widget(1)
            if w is not None:
                self._stack.removeWidget(w)
                w.deleteLater()

        self._stack.addWidget(self._build_tool_view(tool_id, path))
        self._stack.setCurrentIndex(1)

    # ==================================================================
    # HOME SCREEN
    # ==================================================================

    def _build_home(self) -> QWidget:
        root = QWidget()
        root.setStyleSheet(f"background: {colors.WHITE};")
        root_lay = QHBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        sidebar = self._build_home_sidebar()
        root_lay.addWidget(sidebar)

        right = QWidget()
        right.setStyleSheet(f"background: {colors.WHITE};")
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        right_lay.addWidget(self._build_home_header())

        self._home_stack = QStackedWidget()
        self._home_stack.setStyleSheet(f"background: {colors.WHITE};")
        self._home_stack.addWidget(self._build_dashboard_content())  # 0: dashboard
        self._home_stack.addWidget(self._build_tools_content())  # 1: all tools
        self._home_stack.addWidget(self._build_library_page())  # 2: library views
        right_lay.addWidget(self._home_stack, 1)

        root_lay.addWidget(right, 1)

        self._home_active_nav = "dashboard"
        self._home_stack.setCurrentIndex(0)
        return root

    def _build_home_header(self) -> QWidget:
        """Top header: search bar + Upload New + notification + avatar."""
        bar = QFrame()
        bar.setFixedHeight(64)
        bar.setStyleSheet(f"QFrame {{ background: {colors.WHITE}; border: none; }}")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(32, 0, 32, 0)
        lay.setSpacing(0)

        # Search
        search_frame = QFrame()
        search_frame.setFixedHeight(42)
        search_frame.setStyleSheet(
            f"QFrame {{ background: {colors.HOME_SEARCH_BG}; border: 1.5px solid {colors.HOME_BORDER}; border-radius: 8px; }}"
        )
        search_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        sf_lay = QHBoxLayout(search_frame)
        sf_lay.setContentsMargins(12, 0, 12, 0)
        sf_lay.setSpacing(8)

        search_icon = QLabel()
        search_icon.setPixmap(svg_pixmap("search", colors.G500, 16))
        search_icon.setStyleSheet("background: transparent; border: none;")
        sf_lay.addWidget(search_icon)

        search_input = QLineEdit()
        search_input.setPlaceholderText("Search for documents...")
        search_input.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: none; color: {colors.HOME_SEARCH_TXT}; font: 14px 'Segoe UI'; }}"
        )
        search_input.textChanged.connect(self._on_lib_search)
        self._lib_search_edit = search_input
        sf_lay.addWidget(search_input, 1)
        search_frame.mousePressEvent = lambda e: search_input.setFocus()
        lay.addWidget(search_frame, 1)
        lay.addSpacing(32)

        # Right controls
        upload_btn = QPushButton("  Upload New")
        upload_btn.setIcon(svg_icon("upload", colors.WHITE, 15))
        upload_btn.setIconSize(QSize(15, 15))
        upload_btn.setFixedHeight(36)
        upload_btn.setStyleSheet(
            f"QPushButton {{ background: {colors.BRAND}; color: {colors.WHITE}; border: none; "
            f"border-radius: 4px; font: bold 14px 'Segoe UI'; padding: 0 16px; }}"
            f"QPushButton:hover {{ background: {colors.BRAND_HOVER}; }}"
        )
        upload_btn.clicked.connect(self._upload_new)
        lay.addWidget(upload_btn)

        theme_btn = QPushButton()
        theme_btn.setFixedSize(36, 36)
        theme_btn.setToolTip("Toggle dark/light theme")
        _is_dark = False
        try:
            from theme import is_dark as _id

            _is_dark = _id()
        except Exception:
            pass
        theme_btn.setIcon(svg_icon("moon" if not _is_dark else "sun", colors.G500, 18))
        theme_btn.setIconSize(QSize(18, 18))
        theme_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {colors.HOME_BORDER};"
            f" border-radius: 6px; }}"
            f"QPushButton:hover {{ background: {colors.G100}; }}"
        )
        theme_btn.clicked.connect(self._toggle_theme)
        lay.addSpacing(8)
        lay.addWidget(theme_btn)
        return bar

    def _build_home_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setFixedWidth(256)
        sidebar.setStyleSheet(
            f"QFrame {{ background: {colors.SIDEBAR_BG}; border: none; }}"
        )
        sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        outer_lay = QVBoxLayout(sidebar)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(0)

        # Logo header
        logo_wrap = QFrame()
        logo_wrap.setStyleSheet("QFrame { background: transparent; border: none; }")
        lw_lay = QHBoxLayout(logo_wrap)
        lw_lay.setContentsMargins(16, 16, 16, 16)
        lw_lay.setSpacing(0)

        _lp_svg = resource_path("LOGO.svg")
        _lp_png = resource_path("LOGO.png")
        if os.path.exists(_lp_svg):
            from PySide6.QtSvgWidgets import QSvgWidget

            logo_badge = QSvgWidget(_lp_svg)
            logo_badge.setFixedSize(56, 56)
            logo_badge.setStyleSheet("background: transparent; border: none;")
        else:
            logo_badge = QLabel()
            logo_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_badge.setStyleSheet("background: transparent; border: none;")
            if os.path.exists(_lp_png):
                logo_badge.setPixmap(
                    QPixmap(_lp_png).scaled(
                        160,
                        60,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        lw_lay.setSpacing(10)
        lw_lay.addWidget(logo_badge)
        logo_txt = QLabel("PDFree")
        logo_txt.setStyleSheet(
            f"color: {colors.G900}; font: bold 18px 'Segoe UI';"
            " background: transparent; border: none;"
        )
        lw_lay.addWidget(logo_txt)
        lw_lay.addStretch()
        outer_lay.addWidget(logo_wrap)

        # Scrollable nav area
        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )
        nav_widget = QWidget()
        nav_widget.setStyleSheet("background: transparent;")
        nav_lay = QVBoxLayout(nav_widget)
        nav_lay.setContentsMargins(16, 16, 16, 16)
        nav_lay.setSpacing(24)
        nav_scroll.setWidget(nav_widget)

        self._home_nav_btns = {}

        def _sec(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setContentsMargins(12, 0, 12, 0)
            lbl.setStyleSheet(
                f"color: {colors.G500}; font: bold 10px 'Segoe UI'; letter-spacing: 0.5px; background: transparent;"
            )
            return lbl

        def _nav(key: str, label: str) -> QPushButton:
            btn = QPushButton(label)
            btn.setFixedHeight(36)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda _=False, k=key: self._set_home_nav(k))
            btn.setProperty("navKey", key)
            self._home_nav_btns[key] = btn
            btn.setStyleSheet(self._home_nav_style(key))
            return btn

        # Main Navigation — 4 items only
        mn = QWidget()
        mn.setStyleSheet("background: transparent;")
        mn_lay = QVBoxLayout(mn)
        mn_lay.setContentsMargins(0, 0, 0, 0)
        mn_lay.setSpacing(8)
        mn_lay.addWidget(_sec("MAIN NAVIGATION"))
        grp = QWidget()
        grp.setStyleSheet("background: transparent;")
        grp_lay = QVBoxLayout(grp)
        grp_lay.setContentsMargins(0, 0, 0, 0)
        grp_lay.setSpacing(4)
        for key, label in [
            ("dashboard", "Dashboard"),
            ("all_files", "All Files"),
            ("recent", "Recent"),
            ("favorites", "Favorites"),
        ]:
            grp_lay.addWidget(_nav(key, label))
        mn_lay.addWidget(grp)
        nav_lay.addWidget(mn)

        # Folders section
        fol = QWidget()
        fol.setStyleSheet("background: transparent;")
        fol_lay = QVBoxLayout(fol)
        fol_lay.setContentsMargins(0, 0, 0, 0)
        fol_lay.setSpacing(8)

        fol_hdr_w = QWidget()
        fol_hdr_w.setStyleSheet("background: transparent;")
        fh_lay = QHBoxLayout(fol_hdr_w)
        fh_lay.setContentsMargins(12, 0, 12, 0)
        fh_lay.setSpacing(0)
        fh_lbl = QLabel("FOLDERS")
        fh_lbl.setStyleSheet(
            f"color: {colors.G500}; font: bold 10px 'Segoe UI'; letter-spacing: 0.5px; background: transparent;"
        )
        fh_lay.addWidget(fh_lbl)
        fh_lay.addStretch()
        fh_add = QPushButton("+")
        fh_add.setFixedSize(18, 18)
        fh_add.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {colors.G500}; border: none; font: bold 14px; }}"
            f"QPushButton:hover {{ color: {colors.HOME_TEXT}; }}"
        )
        fh_add.clicked.connect(self._add_folder)
        fh_lay.addWidget(fh_add)
        fol_lay.addWidget(fol_hdr_w)

        # Folder list (dynamic — stored so _rebuild_folder_nav can update it)
        fol_list = QWidget()
        fol_list.setStyleSheet("background: transparent;")
        self._fol_list_lay = QVBoxLayout(fol_list)
        self._fol_list_lay.setContentsMargins(0, 0, 0, 0)
        self._fol_list_lay.setSpacing(4)
        self._rebuild_folder_nav()  # populate from LibraryState

        fol_lay.addWidget(fol_list)
        nav_lay.addWidget(fol)
        nav_lay.addStretch()
        outer_lay.addWidget(nav_scroll, 1)

        # New Folder button pinned at bottom
        footer_w = QWidget()
        footer_w.setStyleSheet("background: rgba(226,232,240,0.2);")
        fw_lay = QVBoxLayout(footer_w)
        fw_lay.setContentsMargins(16, 16, 16, 16)
        nf_btn = QPushButton("  New Folder")
        nf_btn.setIcon(svg_icon("folder", "#FFFFFF", 15))
        nf_btn.setIconSize(QSize(15, 15))
        nf_btn.setFixedHeight(40)
        nf_btn.setStyleSheet(
            f"QPushButton {{ background: {colors.BRAND}; color: {colors.WHITE}; border: none; "
            f"border-radius: 4px; font: bold 14px 'Segoe UI'; }}"
            f"QPushButton:hover {{ background: {colors.BRAND_HOVER}; }}"
        )
        nf_btn.clicked.connect(self._add_folder)
        fw_lay.addWidget(nf_btn)
        outer_lay.addWidget(footer_w)

        return sidebar

    def _home_nav_style(self, key: str) -> str:
        import colors as _c

        is_active = getattr(self, "_home_active_nav", "dashboard") == key
        if is_active:
            return (
                f"QPushButton {{ background: {_c.WHITE}; color: {_c.HOME_TEXT}; "
                f"font: bold 14px 'Segoe UI'; border: 1px solid {_c.HOME_BORDER}; "
                "border-radius: 4px; text-align: left; padding: 0 13px; }"
            )
        return (
            f"QPushButton {{ background: transparent; color: {_c.HOME_TEXT}; "
            "font: 14px 'Segoe UI'; border: none; "
            f"border-radius: 4px; text-align: left; padding: 0 12px; }}"
            f"QPushButton:hover {{ background: {_c.G100}; }}"
        )

    def _set_home_nav(self, key: str):
        self._home_active_nav = key
        for k, btn in self._home_nav_btns.items():
            btn.setStyleSheet(self._home_nav_style(k))
        if key == "dashboard":
            self._refresh_quick_tools()
            self._home_stack.setCurrentIndex(0)
        elif key == "all_tools":
            self._home_stack.setCurrentIndex(1)
        else:
            # All library views (all_files, recent, favorites, folder:…)
            self._lib_nav_key = key
            self._refresh_library()
            self._home_stack.setCurrentIndex(2)

    # ------------------------------------------------------------------
    # Dashboard content (Quick Tools + Recent Folders + Recent Files)
    # ------------------------------------------------------------------

    def _build_dashboard_content(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {colors.WHITE}; border: none; }}"
        )
        content = QWidget()
        content.setStyleSheet(f"background: {colors.WHITE};")
        scroll.setWidget(content)

        lay = QVBoxLayout(content)
        lay.setContentsMargins(32, 32, 32, 32)
        lay.setSpacing(40)

        lay.addWidget(self._build_quick_tools_section())
        lay.addWidget(self._build_recent_folders_section())
        lay.addWidget(self._build_recent_files_section())
        lay.addStretch()
        return scroll

    def _build_quick_tools_section(self) -> QWidget:
        section = QWidget()
        section.setStyleSheet("background: transparent;")
        s_lay = QVBoxLayout(section)
        s_lay.setContentsMargins(0, 0, 0, 0)
        s_lay.setSpacing(16)

        hdr = QWidget()
        hdr.setStyleSheet("background: transparent;")
        h_lay = QHBoxLayout(hdr)
        h_lay.setContentsMargins(0, 0, 0, 0)
        t = QLabel("Quick Tools")
        t.setStyleSheet(
            f"color: {colors.HOME_TEXT}; font: bold 16px 'Segoe UI'; background: transparent;"
        )
        h_lay.addWidget(t)
        h_lay.addStretch()
        va = QPushButton("VIEW ALL TOOLS")
        va.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {colors.BRAND}; border: none; "
            f"font: bold 12px 'Segoe UI'; letter-spacing: 0.6px; }}"
            f"QPushButton:hover {{ color: {colors.HOME_TEXT}; }}"
        )
        va.clicked.connect(lambda: self._home_stack.setCurrentIndex(1))
        h_lay.addWidget(va)
        s_lay.addWidget(hdr)

        self._quick_tools_row = QWidget()
        self._quick_tools_row.setStyleSheet("background: transparent;")
        s_lay.addWidget(self._quick_tools_row)
        self._refresh_quick_tools()
        return section

    def _tool_meta(self, tool_id: str) -> tuple[str, str, str]:
        """Return (display_name, icon, category_color) for a tool_id."""
        for cat in CATEGORIES:
            for tid, tname, ticon in cat["tools"]:
                if tid == tool_id:
                    return tname, ticon, cat["color"]
        return tool_id, "file-text", BLUE_ACCENT

    def _refresh_quick_tools(self) -> None:
        if not hasattr(self, "_quick_tools_row") or self._quick_tools_row is None:
            return
        old_lay = self._quick_tools_row.layout()
        if old_lay is not None:
            while old_lay.count():
                item = old_lay.takeAt(0)
                if item and item.widget():
                    item.widget().deleteLater()
        else:
            old_lay = QHBoxLayout(self._quick_tools_row)
            old_lay.setContentsMargins(0, 0, 0, 0)
            old_lay.setSpacing(16)

        try:
            from library_page import LibraryState

            top = LibraryState().top_tools(4)
        except Exception:
            top = ["view", "split", "merge", "excerpt"]

        for tid in top:
            tname, ticon, color = self._tool_meta(tid)
            desc = tr(TOOL_DESCRIPTIONS.get(tid, ""))
            old_lay.addWidget(
                self._make_quick_tool_card(tid, tname, ticon, color, desc), 1
            )

    def _make_quick_tool_card(
        self, tid: str, name: str, icon: str, color: str, desc: str
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("QTCard")
        card.setMinimumHeight(157)
        card.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        card._style_normal = f"QFrame#QTCard {{ background: {colors.WHITE}; border: 1px solid {colors.HOME_BORDER}; border-radius: 8px; }}"
        card._style_hovered = f"QFrame#QTCard {{ background: {colors.WHITE}; border: 1px solid {colors.G300}; border-radius: 8px; }}"
        card.setStyleSheet(card._style_normal)
        card.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(21, 21, 21, 21)
        c_lay.setSpacing(12)

        c_lay.addWidget(
            RoundedIconWidget(icon, color, 46), 0, Qt.AlignmentFlag.AlignLeft
        )

        n_lbl = QLabel(tr(name))
        n_lbl.setStyleSheet(
            f"color: {colors.G900}; font: bold 14px 'Segoe UI'; background: transparent;"
        )
        c_lay.addWidget(n_lbl)

        d_lbl = QLabel(desc)
        d_lbl.setWordWrap(True)
        d_lbl.setStyleSheet(
            f"color: {colors.G500}; font: 12px 'Segoe UI'; background: transparent;"
        )
        c_lay.addWidget(d_lbl)
        c_lay.addStretch()

        card.enterEvent = lambda e, c=card: c.setStyleSheet(c._style_hovered)
        card.leaveEvent = lambda e, c=card: c.setStyleSheet(c._style_normal)
        card.mousePressEvent = lambda e, t=tid: (
            self.show_tool(t) if e.button() == Qt.MouseButton.LeftButton else None
        )
        return card

    def _build_recent_folders_section(self) -> QWidget:
        section = QWidget()
        section.setStyleSheet("background: transparent;")
        s_lay = QVBoxLayout(section)
        s_lay.setContentsMargins(0, 0, 0, 0)
        s_lay.setSpacing(16)

        hdr = QWidget()
        hdr.setStyleSheet("background: transparent;")
        h_lay = QHBoxLayout(hdr)
        h_lay.setContentsMargins(0, 0, 0, 0)
        t = QLabel("Recent Folders")
        t.setStyleSheet(
            f"color: {colors.HOME_TEXT}; font: bold 16px 'Segoe UI'; background: transparent;"
        )
        h_lay.addWidget(t)
        h_lay.addStretch()
        s_lay.addWidget(hdr)

        # Folder cards — real data from LibraryState
        from library_page import LibraryState, _fmt_size

        state = LibraryState()
        folders = state.folders()

        row_w = QWidget()
        row_w.setStyleSheet("background: transparent;")
        rw = QHBoxLayout(row_w)
        rw.setContentsMargins(0, 0, 0, 0)
        rw.setSpacing(16)

        if folders:
            for fd in folders[:5]:
                cnt, sz = state.folder_stats(fd["path"])
                meta = f"{cnt} file{'s' if cnt != 1 else ''} · {_fmt_size(sz)}"
                rw.addWidget(
                    self._make_folder_card(
                        fd["name"], meta, fd.get("color", "#3b82f6"), fd["path"]
                    ),
                    1,
                )
        else:
            empty = QLabel("No folders yet — add one with the + button in the sidebar.")
            empty.setStyleSheet(
                f"color: {colors.G500}; font: 13px 'Segoe UI'; background: transparent;"
            )
            rw.addWidget(empty)

        s_lay.addWidget(row_w)
        return section

    def _make_folder_card(
        self, name: str, meta: str, color: str, path: str = ""
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("FolderCard")
        card.setFixedHeight(125)
        card.setMinimumWidth(80)
        style_normal = f"QFrame#FolderCard {{ background: {colors.WHITE}; border: 1px solid {colors.HOME_BORDER}; border-radius: 8px; }}"
        style_hovered = f"QFrame#FolderCard {{ background: {colors.WHITE}; border: 1px solid {colors.G300}; border-radius: 8px; }}"
        card.setStyleSheet(style_normal)
        card.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        card.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        # Colored top bar — resizes with the card
        bar = QFrame(card)
        bar.setFixedHeight(6)
        bar.setStyleSheet(
            f"background: {color}; border-radius: 0px; border-top-left-radius: 8px; "
            "border-top-right-radius: 8px; border: none;"
        )
        bar.setGeometry(0, 0, max(card.minimumWidth(), 200), 6)
        orig_resize = card.resizeEvent

        def _resize(event, b=bar):
            b.setGeometry(0, 0, event.size().width(), 6)
            if callable(orig_resize):
                orig_resize(event)

        card.resizeEvent = _resize

        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(16, 18, 16, 12)
        c_lay.setSpacing(0)

        top_row = QWidget()
        top_row.setStyleSheet("background: transparent;")
        tr_lay = QHBoxLayout(top_row)
        tr_lay.setContentsMargins(0, 0, 0, 0)
        tr_lay.setSpacing(0)
        fi = QLabel()
        fi.setPixmap(svg_pixmap("folder", color, 22))
        fi.setFixedSize(30, 24)
        fi.setStyleSheet("background: transparent;")
        tr_lay.addWidget(fi)
        tr_lay.addStretch()
        dots = QLabel("···")
        dots.setStyleSheet(
            f"color: {colors.G400}; font: bold 14px; background: transparent;"
        )
        tr_lay.addWidget(dots)
        c_lay.addWidget(top_row)

        c_lay.addStretch()

        n_lbl = QLabel(name)
        n_lbl.setWordWrap(False)
        n_lbl.setStyleSheet(
            f"color: {colors.HOME_TEXT}; font: bold 13px 'Segoe UI'; background: transparent;"
        )
        c_lay.addWidget(n_lbl)

        m_lbl = QLabel(meta)
        m_lbl.setStyleSheet(
            f"color: {colors.G500}; font: 10px 'Segoe UI'; background: transparent;"
        )
        c_lay.addWidget(m_lbl)

        card.enterEvent = lambda e, c=card, s=style_hovered: c.setStyleSheet(s)
        card.leaveEvent = lambda e, c=card, s=style_normal: c.setStyleSheet(s)
        card.mousePressEvent = lambda e, p=path: (
            self._set_home_nav(f"folder:{p}")
            if e.button() == Qt.MouseButton.LeftButton and p
            else None
        )
        return card

    def _build_recent_files_section(self) -> QWidget:
        section = QWidget()
        section.setStyleSheet("background: transparent;")
        s_lay = QVBoxLayout(section)
        s_lay.setContentsMargins(0, 0, 0, 0)
        s_lay.setSpacing(16)

        hdr = QWidget()
        hdr.setStyleSheet("background: transparent;")
        h_lay = QHBoxLayout(hdr)
        h_lay.setContentsMargins(0, 0, 0, 0)
        t = QLabel("Recent Files")
        t.setStyleSheet(
            f"color: {colors.HOME_TEXT}; font: bold 16px 'Segoe UI'; background: transparent;"
        )
        h_lay.addWidget(t)
        h_lay.addStretch()

        # Table container
        tbl = QFrame()
        tbl.setStyleSheet(
            f"QFrame {{ background: {colors.WHITE}; border: 1px solid {colors.G200}; border-radius: 0; }}"
        )
        tbl_lay = QVBoxLayout(tbl)
        tbl_lay.setContentsMargins(0, 0, 0, 0)
        tbl_lay.setSpacing(0)

        # Table header
        th = QWidget()
        th.setFixedHeight(38)
        th.setStyleSheet(
            f"background: {colors.G50}; border-bottom: 1px solid {colors.G200}; border-radius: 0;"
        )
        th_lay = QHBoxLayout(th)
        th_lay.setContentsMargins(20, 0, 12, 0)
        th_lay.setSpacing(0)
        # spacer to align with row icon column (badge 30 + gap 10)
        th_lay.addSpacing(30 + 10)
        tbl_lay.addWidget(th)

        # header cells — must mirror row structure exactly
        for lbl, w in [
            ("NAME", 0),
            ("DATE MODIFIED", 140),
            ("SIZE", 100),
            ("", 28),
        ]:
            cell = QLabel(lbl)
            cell.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            cell.setStyleSheet(
                f"color: {colors.G400}; font: bold 10px 'Segoe UI'; "
                "letter-spacing: 1px; background: transparent; border: none; padding: 0; margin: 0;"
            )
            if w:
                cell.setFixedWidth(w)
            else:
                cell.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
                )
            th_lay.addWidget(cell)

        # Rows — real data from LibraryState
        from library_page import LibraryState, _fmt_size, _age_str

        recent_files = LibraryState().recent(8)
        FILE_COLORS = {"pdf": "#ef4444", "docx": "#3b82f6", "xlsx": "#16a34a"}

        if recent_files:
            for i, entry in enumerate(recent_files):
                name = entry.get("name", "")
                ext = name.rsplit(".", 1)[-1].lower() if "." in name else "pdf"
                color = FILE_COLORS.get(ext, "#9ca3af")
                age = _age_str(entry.get("last_opened", "")) or "—"
                size = _fmt_size(entry.get("size", 0))
                row = self._make_file_row(
                    ext,
                    name,
                    age,
                    size,
                    entry["path"],
                    first=(i == 0),
                    color=color,
                    entry=entry,
                )
                tbl_lay.addWidget(row)
        else:
            empty = QLabel("No files yet — upload a PDF to get started.")
            empty.setContentsMargins(16, 20, 16, 20)
            empty.setStyleSheet(
                f"color: {colors.G500}; font: 13px 'Segoe UI'; background: transparent;"
            )
            tbl_lay.addWidget(empty)

        s_lay.addWidget(tbl)
        return section

    def _make_file_row(
        self,
        ftype: str,
        fname: str,
        fdate: str,
        fsize: str,
        path: str = "",
        first: bool = False,
        color: str = "#9ca3af",
        entry: dict | None = None,
    ) -> QWidget:
        import os as _os

        exists = path and _os.path.exists(path)

        row = QWidget()
        row.setFixedHeight(48)
        row.setStyleSheet(
            f"QWidget {{ background: {colors.WHITE}; border-bottom: 1px solid {colors.G100}; }}"
        )
        row.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        row.enterEvent = lambda e, r=row: r.setStyleSheet(
            f"QWidget {{ background: {colors.G50}; border-bottom: 1px solid {colors.G100}; }}"
        )
        row.leaveEvent = lambda e, r=row: r.setStyleSheet(
            f"QWidget {{ background: {colors.WHITE}; border-bottom: 1px solid {colors.G100}; }}"
        )

        r_lay = QHBoxLayout(row)
        r_lay.setContentsMargins(20, 0, 12, 0)
        r_lay.setSpacing(0)

        # PDF badge
        badge = QLabel("PDF")
        badge.setFixedSize(30, 30)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {colors.RED_HOVER},stop:1 {colors.RED_DARK});"
            "color: white; font: bold 7px 'Segoe UI'; border-radius: 5px; border: none;"
        )
        r_lay.addWidget(badge)
        r_lay.addSpacing(10)

        # File name
        fn_lbl = QLabel(fname)
        fn_lbl.setStyleSheet(
            f"color: {colors.G900 if exists else colors.G400}; font: 500 13px 'Segoe UI'; background: transparent;"
        )
        fn_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        r_lay.addWidget(fn_lbl, 1)

        date_lbl = QLabel(fdate)
        date_lbl.setFixedWidth(140)
        date_lbl.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        date_lbl.setStyleSheet(
            f"color: {colors.G500}; font: 13px 'Segoe UI'; background: transparent; padding: 0; margin: 0;"
        )
        r_lay.addWidget(date_lbl)

        size_lbl = QLabel(fsize)
        size_lbl.setFixedWidth(100)
        size_lbl.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        size_lbl.setStyleSheet(
            f"color: {colors.G700}; font: 13px 'Segoe UI'; background: transparent; padding: 0; margin: 0;"
        )
        r_lay.addWidget(size_lbl)

        # ── Star ──────────────────────────────────────────────────────
        fav = (entry or {}).get("favorited", False)
        star = QPushButton("★" if fav else "☆")
        star.setFixedSize(28, 28)
        star.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; "
            f"color: {colors.AMBER if fav else colors.G300}; font: 15px; border-radius: 6px; }}"
            f"QPushButton:hover {{ color: {colors.AMBER}; background: {colors.AMBER_BG}; }}"
        )
        if entry:
            star.clicked.connect(
                lambda _=False, p=path, v=fav: self._toggle_fav(p, not v)
            )
        r_lay.addWidget(star)

        # Click to open
        if exists:
            row.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            row.mousePressEvent = lambda e, p=path: (
                self.show_tool("view", p)
                if e.button() == Qt.MouseButton.LeftButton
                else None
            )

        return row

    # ==================================================================
    # LIBRARY VIEW  (home_stack index 2)
    # ==================================================================

    def _build_library_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background: {colors.WHITE};")
        p_lay = QVBoxLayout(page)
        p_lay.setContentsMargins(0, 0, 0, 0)
        p_lay.setSpacing(0)

        self._lib_scroll = QScrollArea()
        self._lib_scroll.setWidgetResizable(True)
        self._lib_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._lib_scroll.setStyleSheet(
            f"QScrollArea {{ background: {colors.WHITE}; border: none; }}"
        )
        p_lay.addWidget(self._lib_scroll, 1)

        # Selection bar (hidden until files are selected)
        self._sel_wrap = QFrame()
        self._sel_wrap.setFixedHeight(52)
        self._sel_wrap.setStyleSheet(
            f"QFrame {{ background: {colors.WHITE}; border-top: 1px solid {colors.HOME_BORDER}; }}"
        )
        self._sel_wrap.hide()
        sw = QHBoxLayout(self._sel_wrap)
        sw.setContentsMargins(32, 0, 32, 0)
        sw.setSpacing(12)
        self._sel_count_lbl = QLabel("")
        self._sel_count_lbl.setStyleSheet(
            f"color: {colors.HOME_TEXT}; font: bold 13px 'Segoe UI'; background: transparent;"
        )
        sw.addWidget(self._sel_count_lbl)
        sw.addStretch()
        for lbl, danger, slot in [
            ("Open", False, self._sel_open),
            ("Show in Explorer", False, self._sel_explorer),
            ("Delete", True, self._sel_trash),
        ]:
            b = QPushButton(lbl)
            b.setFixedHeight(34)
            b.setStyleSheet(
                f"QPushButton {{ background: {colors.RED_DIM if danger else colors.G100}; "
                f"color: {colors.RED if danger else colors.G700}; border: none; "
                "border-radius: 6px; font: 12px 'Segoe UI'; padding: 0 14px; }"
                f"QPushButton:hover {{ background: {colors.RED_MED if danger else colors.G200}; }}"
            )
            b.clicked.connect(slot)
            sw.addWidget(b)
        close_b = QPushButton("×")
        close_b.setFixedSize(32, 32)
        close_b.setStyleSheet(
            f"QPushButton {{ background: {colors.G100}; color: {colors.G600}; border-radius: 16px; font: bold 16px; border: none; }}"
            f"QPushButton:hover {{ background: {colors.G200}; }}"
        )
        close_b.clicked.connect(self._sel_clear)
        sw.addWidget(close_b)
        p_lay.addWidget(self._sel_wrap)

        return page

    def _refresh_library(self):
        if self._lib_scroll is None:
            return
        from library_page import LibraryState

        state = LibraryState()
        q = self._lib_search_q

        content = QWidget()
        content.setStyleSheet(f"background: {colors.WHITE};")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(32, 32, 32, 32)
        lay.setSpacing(28)

        key = self._lib_nav_key
        if key == "all_files":
            self._build_lib_all(lay, state, q)
        elif key == "recent":
            self._build_lib_recent(lay, state, q)
        elif key == "favorites":
            self._build_lib_favorites(lay, state, q)
        elif key.startswith("folder:"):
            self._build_lib_folder(lay, state, key[7:], q)

        lay.addStretch()
        self._lib_scroll.setWidget(content)

    def _lib_hdr(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {colors.HOME_TEXT}; font: bold 16px 'Segoe UI'; background: transparent;"
        )
        return lbl

    def _lib_empty(self, text: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        wl = QVBoxLayout(w)
        wl.setContentsMargins(0, 32, 0, 32)
        wl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color: {colors.G500}; font: 14px 'Segoe UI'; background: transparent;"
        )
        wl.addWidget(lbl)
        return w

    def _build_lib_all(self, lay, state, q: str):
        from library_page import HeroBanner, FolderCard, _NewFolderCard

        # Hero banner
        recent1 = state.recent(1, q)
        hero = HeroBanner(recent1[0] if recent1 else None)
        hero.open_req.connect(self._open_file)
        lay.addWidget(hero)

        # Folders row
        hdr_row = QWidget()
        hdr_row.setStyleSheet("background: transparent;")
        hr = QHBoxLayout(hdr_row)
        hr.setContentsMargins(0, 0, 0, 0)
        hr.addWidget(self._lib_hdr("Folders"))
        hr.addStretch()
        add_btn = QPushButton("+ Add Folder")
        add_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {colors.BRAND}; border: none; font: bold 12px 'Segoe UI'; }}"
            f"QPushButton:hover {{ color: {colors.HOME_TEXT}; }}"
        )
        add_btn.clicked.connect(self._add_folder)
        hr.addWidget(add_btn)
        lay.addWidget(hdr_row)

        folder_row = QWidget()
        folder_row.setStyleSheet("background: transparent;")
        fr = QHBoxLayout(folder_row)
        fr.setContentsMargins(0, 0, 0, 0)
        fr.setSpacing(12)
        fr.setAlignment(Qt.AlignmentFlag.AlignLeft)
        for fd in state.folders():
            cnt, sz = state.folder_stats(fd["path"])
            card = FolderCard(
                fd["path"], fd["name"], fd.get("color", "#3b82f6"), cnt, sz
            )
            card.clicked.connect(lambda p: self._set_home_nav(f"folder:{p}"))
            card.delete_req.connect(self._delete_folder)
            fr.addWidget(card)
        nfc = _NewFolderCard()
        nfc.clicked.connect(self._add_folder)
        fr.addWidget(nfc)
        fr.addStretch()
        lay.addWidget(folder_row)

        # Recent files table
        lay.addWidget(self._lib_hdr("Recent Files"))
        files = state.recent(50, q)
        lay.addWidget(
            self._build_lib_file_table(files)
            if files
            else self._lib_empty("No files yet. Upload a PDF to get started.")
        )

    def _build_lib_recent(self, lay, state, q: str):
        from library_page import HeroBanner

        recent1 = state.recent(1, q)
        hero = HeroBanner(recent1[0] if recent1 else None)
        hero.open_req.connect(self._open_file)
        lay.addWidget(hero)
        lay.addWidget(self._lib_hdr("Recent Files"))
        files = state.recent(50, q)
        lay.addWidget(
            self._build_lib_file_table(files)
            if files
            else self._lib_empty("No recent files yet.")
        )

    def _build_lib_favorites(self, lay, state, q: str):
        lay.addWidget(self._lib_hdr("Favorites"))
        files = state.favorites(q)
        lay.addWidget(
            self._build_lib_file_table(files)
            if files
            else self._lib_empty("No favorites yet. Star a file to add it here.")
        )

    def _build_lib_folder(self, lay, state, folder_path: str, q: str):
        name = folder_path.replace("\\", "/").rsplit("/", 1)[-1] or folder_path
        lay.addWidget(self._lib_hdr(name))
        files = state.in_folder(folder_path, q)
        lay.addWidget(
            self._build_lib_file_table(files)
            if files
            else self._lib_empty("No PDFs found in this folder.")
        )

    def _build_lib_file_table(self, files: list) -> QWidget:

        tbl = QFrame()
        tbl.setStyleSheet(
            f"QFrame {{ background: {colors.WHITE}; border: 1px solid {colors.G200}; border-radius: 0; }}"
        )
        tbl_lay = QVBoxLayout(tbl)
        tbl_lay.setContentsMargins(0, 0, 0, 0)
        tbl_lay.setSpacing(0)

        # Header
        th = QWidget()
        th.setFixedHeight(38)
        th.setStyleSheet(
            f"background: {colors.G50}; border-bottom: 1px solid {colors.G200}; border-radius: 0;"
        )
        th_lay = QHBoxLayout(th)
        th_lay.setContentsMargins(20, 0, 12, 0)
        th_lay.setSpacing(0)
        # align with row: checkbox(15) + gap(14) + badge(30) + gap(10)
        th_lay.addSpacing(15 + 14 + 30 + 10)
        for lbl, w in [("NAME", 0), ("LAST OPENED", 140), ("SIZE", 100)]:
            cell = QLabel(lbl)
            cell.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            cell.setStyleSheet(
                f"color: {colors.G400}; font: bold 10px 'Segoe UI'; "
                "letter-spacing: 1px; background: transparent; border: none; padding: 0; margin: 0;"
            )
            if w:
                cell.setFixedWidth(w)
            else:
                cell.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
                )
            th_lay.addWidget(cell)
        tbl_lay.addWidget(th)

        for i, entry in enumerate(files):
            tbl_lay.addWidget(self._make_lib_row(entry))

        return tbl

    def _make_lib_row(self, entry: dict) -> QWidget:
        from library_page import _fmt_size, _age_str
        import os as _os

        is_sel = entry.get("path", "") in self._selected_files
        exists = _os.path.exists(entry.get("path", ""))
        fav = entry.get("favorited", False)
        bg = colors.BLUE_DIM if is_sel else colors.WHITE

        row = QWidget()
        row.setFixedHeight(48)
        row.setStyleSheet(
            f"QWidget {{ background: {bg}; border-bottom: 1px solid {colors.G100}; }}"
        )
        row.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        def _enter(e, r=row, s=is_sel):
            if not s:
                r.setStyleSheet(
                    f"QWidget {{ background: {colors.G50}; border-bottom: 1px solid {colors.G100}; }}"
                )

        def _leave(e, r=row, b=bg):
            r.setStyleSheet(
                f"QWidget {{ background: {b}; border-bottom: 1px solid {colors.G100}; }}"
            )

        row.enterEvent = _enter
        row.leaveEvent = _leave

        r = QHBoxLayout(row)
        r.setContentsMargins(20, 0, 12, 0)
        r.setSpacing(0)

        # ── Checkbox ──────────────────────────────────────────────────
        chk = QFrame()
        chk.setFixedSize(15, 15)
        if is_sel:
            chk.setStyleSheet(
                f"background: {colors.BLUE_ACCENT}; border: 1.5px solid {colors.BLUE_ACCENT}; border-radius: 3px;"
            )
        else:
            chk.setStyleSheet(
                f"background: {colors.WHITE}; border: 1.5px solid {colors.G300}; border-radius: 3px;"
            )
        chk_wrap = QWidget()
        chk_wrap.setFixedSize(15, 15)
        chk_wrap.setStyleSheet("background: transparent;")
        chk_wrap.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        chk_wrap.mousePressEvent = lambda e, p=entry.get("path", ""): self._toggle_sel(
            p
        )
        cw = QHBoxLayout(chk_wrap)
        cw.setContentsMargins(0, 0, 0, 0)
        cw.addWidget(chk)
        r.addWidget(chk_wrap)
        r.addSpacing(14)

        # ── PDF badge ─────────────────────────────────────────────────
        badge = QLabel("PDF")
        badge.setFixedSize(30, 30)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {colors.RED_HOVER},stop:1 {colors.RED_DARK});"
            "color: white; font: bold 7px 'Segoe UI'; border-radius: 5px; border: none;"
        )
        r.addWidget(badge)
        r.addSpacing(10)

        # ── Name ──────────────────────────────────────────────────────
        name_color = (
            colors.BLUE_DEEP if is_sel else (colors.G900 if exists else colors.G400)
        )
        fn = QLabel(entry.get("name", "Unknown"))
        fn.setStyleSheet(
            f"color: {name_color}; font: 500 13px 'Segoe UI'; background: transparent;"
        )
        fn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        r.addWidget(fn, 1)

        # ── Last Opened ───────────────────────────────────────────────
        age_lbl = QLabel(_age_str(entry.get("last_opened", "")) or "—")
        age_lbl.setFixedWidth(140)
        age_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        age_lbl.setStyleSheet(
            f"color: {colors.G500}; font: 13px 'Segoe UI'; background: transparent; padding: 0; margin: 0;"
        )
        r.addWidget(age_lbl)

        # ── Size ──────────────────────────────────────────────────────
        sz_lbl = QLabel(_fmt_size(entry.get("size", 0)))
        sz_lbl.setFixedWidth(100)
        sz_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        sz_lbl.setStyleSheet(
            f"color: {colors.G700}; font: 13px 'Segoe UI'; background: transparent; padding: 0; margin: 0;"
        )
        r.addWidget(sz_lbl)

        # ── Star ──────────────────────────────────────────────────────
        star = QPushButton("★" if fav else "☆")
        star.setFixedSize(28, 28)
        star.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; "
            f"color: {colors.AMBER if fav else colors.G300}; font: 15px; border-radius: 6px; }}"
            f"QPushButton:hover {{ color: {colors.AMBER}; background: {colors.AMBER_BG}; }}"
        )
        star.clicked.connect(
            lambda _=False, p=entry.get("path", ""), v=fav: self._toggle_fav(p, not v)
        )
        r.addWidget(star)

        # ── Menu "···" ────────────────────────────────────────────────
        menu_btn = QPushButton("···")
        menu_btn.setFixedSize(28, 28)
        menu_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {colors.G300}; "
            f"font: bold 14px 'Segoe UI'; border-radius: 6px; }}"
            f"QPushButton:hover {{ background: {colors.G100}; color: {colors.G500}; }}"
        )

        def _show_menu(_, p=entry.get("path", ""), e=exists):
            from PySide6.QtWidgets import QMenu as _QMenu

            m = _QMenu(row)
            m.setStyleSheet(
                f"QMenu {{ background: {colors.WHITE}; border: 1px solid {colors.G200}; border-radius: 8px; padding: 4px; }}"
                f"QMenu::item {{ padding: 6px 20px; color: {colors.G700}; font: 13px 'Segoe UI'; border-radius: 4px; }}"
                f"QMenu::item:selected {{ background: {colors.G100}; }}"
            )
            if e:
                m.addAction("Open", lambda: self._open_file(p))
            import sys as _sys

            if _sys.platform == "win32":
                m.addAction(
                    "Show in Explorer",
                    lambda: __import__("subprocess").Popen(["explorer", "/select,", p]),
                )
            elif _sys.platform == "darwin":
                m.addAction(
                    "Reveal in Finder",
                    lambda: __import__("subprocess").Popen(["open", "-R", p]),
                )
            fav_now = entry.get("favorited", False)
            m.addAction(
                "Remove from Favorites" if fav_now else "Add to Favorites",
                lambda: self._toggle_fav(p, not fav_now),
            )
            m.exec(menu_btn.mapToGlobal(menu_btn.rect().bottomLeft()))

        menu_btn.clicked.connect(_show_menu)
        r.addWidget(menu_btn)

        # Row click → open file
        if exists:
            row.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            row.mousePressEvent = lambda e, p=entry.get("path", ""): (
                self._open_file(p) if e.button() == Qt.MouseButton.LeftButton else None
            )

        return row

    # ---- Library actions --------------------------------------------------

    def _open_file(self, path: str):
        self.show_tool("view", path)

    def open_pdfs(self, paths: list) -> None:
        from view_tool import ViewTool

        if not paths:
            return
        if isinstance(self._current_tool, ViewTool):
            for p in paths:
                self._current_tool.open_file(p)
        else:
            self.show_tool("view", paths[0])
            if self._current_tool is not None:
                for p in paths[1:]:
                    self._current_tool.open_file(p)

    def _upload_new(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Upload PDF", "", "PDF files (*.pdf)"
        )
        if path:
            from library_page import LibraryState

            LibraryState().track(path)
            self._set_home_nav("all_files")

    def _add_folder(self):
        from PySide6.QtWidgets import QFileDialog as _QFD

        folder = _QFD.getExistingDirectory(self, "Add Folder")
        if folder:
            from library_page import LibraryState

            LibraryState().add_folder(folder)
            self._rebuild_folder_nav()
            self._refresh_library()

    def _delete_folder(self, path: str):
        from library_page import LibraryState

        LibraryState().delete_folder(path)
        self._rebuild_folder_nav()
        if self._lib_nav_key == f"folder:{path}":
            self._lib_nav_key = "all_files"
        self._refresh_library()

    def _toggle_fav(self, path: str, val: bool):
        from library_page import LibraryState

        LibraryState().set_favorite(path, val)
        self._refresh_library()

    def _trash_file(self, path: str):
        from library_page import LibraryState

        LibraryState().trash(path)
        self._selected_files.discard(path)
        self._update_sel_bar()
        self._refresh_library()

    def _on_lib_search(self):
        self._lib_search_q = (
            self._lib_search_edit.text().strip().lower()
            if self._lib_search_edit
            else ""
        )
        self._lib_search_timer.start(80)

    # ---- Selection --------------------------------------------------------

    def _toggle_sel(self, path: str):
        if path in self._selected_files:
            self._selected_files.discard(path)
        else:
            self._selected_files.add(path)
        self._update_sel_bar()
        self._refresh_library()

    def _update_sel_bar(self):
        if self._sel_wrap is None or self._sel_count_lbl is None:
            return
        n = len(self._selected_files)
        if n:
            self._sel_count_lbl.setText(f"{n} item{'s' if n > 1 else ''} selected")
            self._sel_wrap.show()
        else:
            self._sel_wrap.hide()

    def _sel_open(self):
        for p in list(self._selected_files)[:1]:
            self._open_file(p)

    def _sel_explorer(self):
        import subprocess
        import sys

        for p in list(self._selected_files)[:1]:
            try:
                if sys.platform == "win32":
                    subprocess.Popen(["explorer", "/select,", p])
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", "-R", p])
            except OSError:
                pass

    def _sel_trash(self):
        from library_page import LibraryState

        state = LibraryState()
        for p in list(self._selected_files):
            state.trash(p)
        self._selected_files.clear()
        self._update_sel_bar()
        self._refresh_library()

    def _sel_clear(self):
        self._selected_files.clear()
        self._update_sel_bar()
        self._refresh_library()

    # ---- Folder nav rebuild -----------------------------------------------

    def _rebuild_folder_nav(self):
        """Refresh the sidebar folder list without rebuilding the whole home page."""
        if self._fol_list_lay is None:
            return
        while self._fol_list_lay.count():
            item = self._fol_list_lay.takeAt(0)
            widget = item.widget() if item else None
            if widget:
                widget.deleteLater()
        from library_page import LibraryState

        clrs = ["#3b82f6", "#a855f7", "#f97316", "#8b5cf6", "#10b981"]
        for i, fd in enumerate(LibraryState().data.get("folders", [])[:8]):
            fname = fd.get("name", "Folder")
            fpath = fd.get("path", "")
            fcolor = fd.get("color", clrs[i % len(clrs)])
            row_w = QWidget()
            row_w.setStyleSheet("background: transparent;")
            rw_lay = QHBoxLayout(row_w)
            rw_lay.setContentsMargins(12, 4, 12, 4)
            rw_lay.setSpacing(8)
            chev = QLabel(">")
            chev.setFixedWidth(8)
            chev.setStyleSheet(
                f"color: {colors.G500}; font: 9px; background: transparent;"
            )
            rw_lay.addWidget(chev)
            fi = QLabel("📁")
            fi.setFixedWidth(16)
            fi.setStyleSheet(f"color: {fcolor}; font: 11px; background: transparent;")
            rw_lay.addWidget(fi)
            fn = QLabel(fname)
            fn.setStyleSheet(
                f"color: {colors.HOME_TEXT}; font: 14px 'Segoe UI'; background: transparent;"
            )
            rw_lay.addWidget(fn, 1)
            row_w.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            row_w.mousePressEvent = lambda e, p=fpath: (
                self._set_home_nav(f"folder:{p}")
                if e.button() == Qt.MouseButton.LeftButton
                else None
            )
            self._fol_list_lay.addWidget(row_w)

    def _build_tools_content(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {colors.WHITE}; border: none; }}"
        )

        content = QWidget()
        content.setStyleSheet(f"background: {colors.WHITE};")
        scroll.setWidget(content)

        lay = QVBoxLayout(content)
        lay.setContentsMargins(40, 16, 40, 30)
        lay.setSpacing(0)

        self._build_filter_row(lay)
        self._build_tool_grid(lay)
        self._build_footer(lay)

        return scroll

    # ---- header -------------------------------------------------------
    def _build_header(self, lay: QVBoxLayout):
        bar = QWidget()
        bar.setStyleSheet("background: transparent;")
        h = QHBoxLayout(bar)
        h.setContentsMargins(0, 0, 0, 4)
        h.setSpacing(8)

        h.addWidget(PDFIconWidget(28, 34, color=BLUE_ACCENT, bg=BG))

        title = QLabel("PDFree")
        title.setStyleSheet(
            f"color: {G900}; font: bold 22px 'Segoe UI'; background: transparent;"
        )
        h.addWidget(title)
        h.addStretch()

        lib_btn = QPushButton("📚  My Files")
        lib_btn.setFixedSize(130, 34)
        lib_btn.setStyleSheet(f"""
            QPushButton {{
                background:{WHITE}; color:{BLUE_ACCENT}; border:1px solid {G200};
                border-radius:17px; font:bold 12px 'Segoe UI';
            }}
            QPushButton:hover {{ background:{G100}; border-color:{G300}; }}
        """)
        lib_btn.clicked.connect(self.show_library)
        h.addWidget(lib_btn)

        lay.addWidget(bar)

    # ---- quick start --------------------------------------------------
    def _build_quickstart(self, lay: QVBoxLayout):
        lbl = QLabel("Quick Start")
        lbl.setStyleSheet(
            f"color: {G900}; font: bold 20px 'Segoe UI'; background: transparent;"
        )
        lay.addSpacing(20)
        lay.addWidget(lbl)
        lay.addSpacing(8)

        zone = QuickStartZone()
        zone.file_selected.connect(lambda p: self.show_tool("view", p))
        lay.addWidget(zone)
        lay.addSpacing(24)

    # ---- recently used ------------------------------------------------
    def _build_recently_used(self, lay: QVBoxLayout):
        impl_tools = [
            (tid, tname, ticon, cat["color"])
            for cat in CATEGORIES
            for tid, tname, ticon in cat["tools"]
            if tid in IMPLEMENTED
        ]
        if not impl_tools:
            return

        lbl = QLabel("Recently Used")
        lbl.setStyleSheet(
            f"color: {G500}; font: bold 14px 'Segoe UI'; background: transparent;"
        )
        lay.addWidget(lbl)
        lay.addSpacing(10)

        row_w = QWidget()
        row_w.setStyleSheet("background: transparent;")
        row = QHBoxLayout(row_w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        for tid, tname, ticon, color in impl_tools:
            card = RecentCard(tid, tname, ticon, color)
            card.clicked.connect(self.show_tool)
            row.addWidget(card)

        row.addStretch()
        lay.addWidget(row_w)
        lay.addSpacing(24)

    # ---- filter row (tabs + search) -----------------------------------
    def _build_filter_row(self, lay: QVBoxLayout):
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {G200}; border: none;")
        lay.addWidget(sep)
        lay.addSpacing(16)

        row_w = QWidget()
        row_w.setStyleSheet("background: transparent;")
        row = QHBoxLayout(row_w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        # Tab pills
        tabs_w = QWidget()
        tabs_w.setStyleSheet("background: transparent;")
        tabs_lay = QHBoxLayout(tabs_w)
        tabs_lay.setContentsMargins(0, 0, 0, 0)
        tabs_lay.setSpacing(4)

        for tab_name in TAB_CATEGORIES:
            wrap = QWidget()
            wrap.setStyleSheet("background: transparent;")
            v = QVBoxLayout(wrap)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(0)

            btn = QPushButton(tr(tab_name))
            btn.setFixedHeight(32)
            btn.clicked.connect(lambda _checked, t=tab_name: self._on_tab_click(t))
            v.addWidget(btn)

            underline = QFrame()
            underline.setFixedHeight(2)
            v.addWidget(underline)

            self._tab_buttons[tab_name] = (btn, underline)
            tabs_lay.addWidget(wrap)

        row.addWidget(tabs_w)
        row.addStretch()

        # Search bar
        search_frame = QFrame()
        search_frame.setFixedHeight(36)
        search_frame.setStyleSheet(
            f"QFrame {{ background: {colors.HOME_SEARCH_BG}; border: 1.5px solid {colors.G200}; border-radius: 8px; }}"
        )
        sf_lay = QHBoxLayout(search_frame)
        sf_lay.setContentsMargins(10, 0, 10, 0)
        sf_lay.setSpacing(8)

        mag = QLabel()
        mag.setPixmap(svg_pixmap("search", G400, 16))
        mag.setStyleSheet("background: transparent; border: none;")
        sf_lay.addWidget(mag)

        self._search_entry = QLineEdit()
        self._search_entry.setPlaceholderText(tr("Search tools..."))
        self._search_entry.setFixedWidth(200)
        self._search_entry.setStyleSheet(f"""
            QLineEdit {{
                background: transparent; border: none;
                color: {G700}; font: 13px 'Segoe UI';
            }}
        """)
        self._search_entry.textChanged.connect(self._on_search)
        sf_lay.addWidget(self._search_entry)
        search_frame.mousePressEvent = lambda e, w=self._search_entry: w.setFocus()

        row.addWidget(search_frame)
        lay.addWidget(row_w)
        lay.addSpacing(16)

        self._update_tab_styles()

    def _update_tab_styles(self):
        def _active_style():
            return f"""
            QPushButton {{
                background: transparent; color: {BLUE_ACCENT}; border: none;
                border-radius: 6px; padding: 0 10px; font: 13px 'Segoe UI';
            }}
            QPushButton:hover {{ background: {G100}; }}
        """

        def _inactive_style():
            return f"""
            QPushButton {{
                background: transparent; color: {G500}; border: none;
                border-radius: 6px; padding: 0 10px; font: 13px 'Segoe UI';
            }}
            QPushButton:hover {{ background: {G100}; }}
        """

        for tab_name, (btn, underline) in self._tab_buttons.items():
            if tab_name == self._active_tab:
                btn.setStyleSheet(_active_style())
                underline.setStyleSheet(
                    f"background: {BLUE_ACCENT}; border: none; border-radius: 1px;"
                )
            else:
                btn.setStyleSheet(_inactive_style())
                underline.setStyleSheet("background: transparent; border: none;")

    def _on_tab_click(self, tab_name: str):
        self._active_tab = tab_name
        self._update_tab_styles()
        self._render_tool_grid()

    # ---- tool grid  (4 columns, card layout) -------------------------
    def _build_tool_grid(self, lay: QVBoxLayout):
        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet("background: transparent;")
        self._grid_widget.setLayout(QVBoxLayout())
        self._grid_widget.layout().setContentsMargins(0, 0, 0, 0)
        self._grid_widget.layout().setSpacing(0)

        for cat in CATEGORIES:
            for tid, tname, ticon in cat["tools"]:
                self._all_tool_data.append(
                    (tid, tname, ticon, cat["color"], cat["title"])
                )

        self._render_tool_grid()
        lay.addWidget(self._grid_widget)
        lay.addSpacing(30)

    def _render_tool_grid(self):
        if self._grid_widget is None:
            return

        container_lay = self._grid_widget.layout()
        while container_lay.count():
            item = container_lay.takeAt(0)
            if item is not None:
                w = item.widget()
                if w:
                    w.deleteLater()

        q = self._search_entry.text().strip().lower() if self._search_entry else ""
        tab_filter = TAB_CATEGORIES.get(self._active_tab)

        gw = QWidget()
        gw.setStyleSheet("background: transparent;")
        gl = QGridLayout(gw)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(12)
        for i in range(4):
            gl.setColumnStretch(i, 1)

        col = row_idx = 0
        for tid, tname, ticon, color, cat_title in self._all_tool_data:
            if tab_filter is not None and cat_title not in tab_filter:
                continue
            if q and q not in tname.lower() and q not in cat_title.lower():
                continue
            card = ToolCard(tid, tname, ticon, color, tid in IMPLEMENTED)
            card.clicked.connect(self.show_tool)
            gl.addWidget(card, row_idx, col)
            col += 1
            if col == 4:
                col = 0
                row_idx += 1

        # Stretch row absorbs leftover vertical space so cards don't expand.
        stretch_row = row_idx + (1 if col > 0 else 0)
        gl.setRowStretch(stretch_row, 1)

        container_lay.addWidget(gw)
        container_lay.addStretch()

    # ---- footer -------------------------------------------------------
    def _build_footer(self, lay: QVBoxLayout):
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {G300}; border: none;")
        lay.addWidget(sep)
        lay.addSpacing(14)

        for text in (
            "Licenses  ·  Releases  ·  Privacy Policy  ·  Terms and Conditions",
            "Powered by PDFree",
        ):
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"color: {G400}; font: 11px 'Segoe UI'; background: transparent;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            lay.addWidget(lbl)
            lay.addSpacing(4)

    # ---- search -------------------------------------------------------
    def _on_search(self):
        self._search_timer.start(80)

    # ==================================================================
    # TOOL VIEW  (loads tool screen with back button)
    # ==================================================================

    def _tool_display_name(self, tool_id: str) -> str:
        for cat in CATEGORIES:
            for tid, tname, _ in cat["tools"]:
                if tid == tool_id:
                    return tr(tname)
        return tool_id.replace("_", " ").title()

    def _build_tool_view(self, tool_id: str, path: str = "") -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background: {WHITE};")
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Top bar
        topbar = QFrame()
        topbar.setFixedHeight(56)
        topbar.setStyleSheet(f"""
            QFrame {{
                background: {colors.WHITE};
                border-bottom: 1px solid {colors.G200};
            }}
        """)
        t_lay = QHBoxLayout(topbar)
        t_lay.setContentsMargins(16, 0, 16, 0)
        t_lay.setSpacing(8)

        back_btn = _make_back_button(tr("Back to Home"), self._back_to_home)
        t_lay.addWidget(back_btn)

        # Vertical divider
        divider = QFrame()
        divider.setFixedSize(1, 16)
        divider.setStyleSheet(f"background: {G300}; border: none;")
        t_lay.addWidget(divider)

        # Tool name label
        tool_name_lbl = QLabel(self._tool_display_name(tool_id))
        tool_name_lbl.setStyleSheet(
            f"color: {G900}; font: bold 16px 'Segoe UI'; background: transparent;"
        )
        t_lay.addWidget(tool_name_lbl)

        t_lay.addStretch()
        v.addWidget(topbar)

        # Tool area
        tool_area = QWidget()
        tool_area.setStyleSheet(f"background: {WHITE};")
        v.addWidget(tool_area, 1)

        self._load_tool(tool_id, path, tool_area)
        return page

    def _load_tool(self, tool_id: str, path: str, container: QWidget):
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        if tool_id == "view":
            from view_tool import ViewTool

            tool = ViewTool(initial_path=path)
            self._current_tool = tool
            lay.addWidget(tool)
            return

        if tool_id == "split":
            from split_tool import SplitTool

            tool = SplitTool()
            lay.addWidget(tool)
            return

        if tool_id == "excerpt":
            from excerpt_tool import ExcerptTool

            tool = ExcerptTool()
            lay.addWidget(tool)
            return

        if tool_id == "merge":
            from merge_tool import MergeTool

            tool = MergeTool()
            lay.addWidget(tool)
            return

        if tool_id == "remove":
            from remove_tool import RemoveTool

            tool = RemoveTool()
            lay.addWidget(tool)
            return

        if tool_id == "rotate":
            from rotate_tool import RotateTool

            tool = RotateTool()
            lay.addWidget(tool)
            return

        if tool_id == "batch":
            from batch_tool import BatchTool

            tool = BatchTool()
            lay.addWidget(tool)
            return

        if tool_id == "page_labels":
            from page_labels_tool import PageLabelsTool

            tool = PageLabelsTool()
            lay.addWidget(tool)
            return

        if tool_id == "bookmarks":
            from bookmarks_tool import BookmarksTool

            tool = BookmarksTool()
            lay.addWidget(tool)
            return

        if tool_id == "pdfa":
            from pdfa_tool import PDFATool

            tool = PDFATool()
            lay.addWidget(tool)
            return

        if tool_id == "compress":
            from compress_tool import CompressTool

            tool = CompressTool()
            lay.addWidget(tool)
            return

        if tool_id == "add_password":
            from add_password_tool import AddPasswordTool

            tool = AddPasswordTool()
            lay.addWidget(tool)
            return

        if tool_id == "remove_password":
            from remove_password_tool import RemovePasswordTool

            tool = RemovePasswordTool()
            lay.addWidget(tool)
            return

        if tool_id == "img_to_pdf":
            from img_to_pdf_tool import ImgToPDFTool

            tool = ImgToPDFTool()
            lay.addWidget(tool)
            return

        if tool_id == "pdf_to_img":
            from pdf_to_img_tool import PDFToImgTool

            tool = PDFToImgTool()
            lay.addWidget(tool)
            return

        if tool_id == "add_page_numbers":
            from add_page_numbers_tool import AddPageNumbersTool

            tool = AddPageNumbersTool()
            lay.addWidget(tool)
            return

        if tool_id == "change_metadata":
            from change_metadata_tool import ChangeMetadataTool

            tool = ChangeMetadataTool()
            lay.addWidget(tool)
            return

        if tool_id == "add_watermark":
            from watermark_tool import WatermarkTool

            tool = WatermarkTool()
            lay.addWidget(tool)
            return

        if tool_id == "crop":
            from crop_tool import CropTool

            tool = CropTool()
            lay.addWidget(tool)
            return

        if tool_id == "pdf_to_word":
            from pdf_to_word_tool import PDFToWordTool

            tool = PDFToWordTool()
            lay.addWidget(tool)
            return

        if tool_id == "ocr_pdf":
            from ocr_tool import OCRTool

            tool = OCRTool()
            lay.addWidget(tool)
            return

        if tool_id == "flatten":
            from flatten_tool import FlattenTool

            tool = FlattenTool()
            lay.addWidget(tool)
            return

        if tool_id == "sanitize":
            from sanitize_tool import SanitizeTool

            tool = SanitizeTool()
            lay.addWidget(tool)
            return

        if tool_id == "extract_images":
            from extract_images_tool import ExtractImagesTool

            tool = ExtractImagesTool()
            lay.addWidget(tool)
            return

        if tool_id == "adjust_size":
            from scale_pages_tool import ScalePagesTool

            tool = ScalePagesTool()
            lay.addWidget(tool)
            return

        if tool_id == "headers_footers":
            from headers_footers_tool import HeadersFootersTool

            tool = HeadersFootersTool()
            lay.addWidget(tool)
            return

        if tool_id == "nup":
            from nup_tool import NUpTool

            tool = NUpTool()
            lay.addWidget(tool)
            return

        if tool_id == "pdf_to_excel":
            from pdf_to_excel_tool import PDFToExcelTool

            tool = PDFToExcelTool()
            lay.addWidget(tool)
            return

        if tool_id == "compare":
            from compare_tool import CompareTool

            tool = CompareTool()
            lay.addWidget(tool)
            return

        if tool_id == "reorder":
            from reorder_tool import ReorderTool

            tool = ReorderTool()
            lay.addWidget(tool)
            return

        if tool_id == "manual_redaction":
            from redact_tool import RedactTool

            tool = RedactTool()
            lay.addWidget(tool)
            return

        if tool_id == "remove_annotations":
            from remove_annotations_tool import RemoveAnnotationsTool

            tool = RemoveAnnotationsTool()
            lay.addWidget(tool)
            return

        if tool_id == "add_image":
            from add_image_tool import AddImageTool

            tool = AddImageTool()
            lay.addWidget(tool)
            return

        if tool_id == "html_to_pdf":
            from html_to_pdf_tool import HTMLToPDFTool

            tool = HTMLToPDFTool()
            lay.addWidget(tool)
            return

        if tool_id == "office_to_pdf":
            from office_to_pdf_tool import OfficeToPDFTool

            tool = OfficeToPDFTool()
            lay.addWidget(tool)
            return

        if tool_id == "pdf_to_csv":
            from pdf_to_csv_tool import PDFtoCSVTool

            tool = PDFtoCSVTool()
            lay.addWidget(tool)
            return

        if tool_id == "form_unlock":
            from form_unlock_tool import FormUnlockTool

            tool = FormUnlockTool()
            lay.addWidget(tool)
            return

        if tool_id == "form_export":
            from form_export_tool import FormExportTool

            tool = FormExportTool()
            lay.addWidget(tool)
            return

        if tool_id == "font_info":
            from font_info_tool import FontInfoTool

            tool = FontInfoTool()
            lay.addWidget(tool)
            return

        if tool_id == "validate_signature":
            from validate_signature_tool import ValidateSignatureTool

            tool = ValidateSignatureTool()
            lay.addWidget(tool)
            return

        if tool_id == "svg_to_pdf":
            from svg_to_pdf_tool import SvgToPdfTool

            tool = SvgToPdfTool()
            lay.addWidget(tool)
            return

        # Other tools (still being migrated)
        label = QLabel(
            f"⚙  '{tool_id}' is queued for PySide6 migration.\n"
            "Return here once the tool file has been ported."
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            f"color: {G500}; font: 15px 'Segoe UI'; background: transparent;"
        )
        lay.addWidget(label, 1, Qt.AlignmentFlag.AlignCenter)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def _scrollbar_css() -> str:
    from colors import SCROLLBAR_HANDLE, G400

    return f"""
QScrollBar:vertical {{
    background: transparent; width: 6px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {SCROLLBAR_HANDLE}; border-radius: 3px; min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {G400}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; background: none; }}
QScrollBar::add-page:vertical,  QScrollBar::sub-page:vertical  {{ background: none; }}

QScrollBar:horizontal {{
    background: transparent; height: 6px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {SCROLLBAR_HANDLE}; border-radius: 3px; min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{ background: {G400}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; background: none; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
"""


def _on_update_available(tag: str, url: str) -> None:
    from PySide6.QtWidgets import QMessageBox
    import webbrowser

    msg = QMessageBox()
    msg.setWindowTitle("Update Available")
    msg.setText(f"PDFree {tag} is available.")
    msg.setInformativeText("Download the latest version from GitHub?")
    msg.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    msg.setDefaultButton(QMessageBox.StandardButton.Yes)
    if msg.exec() == QMessageBox.StandardButton.Yes:
        webbrowser.open(url)


def _install_crash_reporter(app: "QApplication") -> None:
    import traceback

    _original_hook = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            _original_hook(exc_type, exc_value, exc_tb)
            return
        logger.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_tb),
        )
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

        msg = QMessageBox(app.activeWindow())
        msg.setWindowTitle("PDFree crashed")
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText(
            "PDFree encountered an unexpected error.\n\n"
            "Click 'Copy details' to copy the error to your clipboard, "
            "then paste it into a GitHub issue."
        )
        msg.setDetailedText(tb_text)
        copy_btn = msg.addButton("Copy details", QMessageBox.ButtonRole.ActionRole)
        msg.addButton("Close", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        if msg.clickedButton() is copy_btn:
            QApplication.clipboard().setText(
                f"PDFree crash report\n{'=' * 40}\n{tb_text}"
            )

        _original_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


if __name__ == "__main__":
    from updater import UpdateChecker
    from PySide6.QtNetwork import QLocalServer, QLocalSocket

    argv_paths = [
        p for p in sys.argv[1:] if p.lower().endswith(".pdf") and os.path.isfile(p)
    ]

    app = QApplication(sys.argv)

    # If another instance is already running, forward paths to it and exit.
    _probe = QLocalSocket()
    _probe.connectToServer("PDFree")
    if _probe.waitForConnected(500):
        if argv_paths:
            _probe.write("\n".join(argv_paths).encode())
            _probe.flush()
            _probe.waitForBytesWritten(1000)
        _probe.close()
        sys.exit(0)
    _probe.close()

    # Claim the server slot immediately so no second instance slips in.
    QLocalServer.removeServer("PDFree")
    _server = QLocalServer()
    if not _server.listen("PDFree"):
        logger.warning(
            "single-instance server could not bind: %s", _server.errorString()
        )

    _install_crash_reporter(app)
    _install_translator(app)
    app.setStyle("Fusion")
    app.setStyleSheet(_scrollbar_css())
    app.aboutToQuit.connect(_cleanup_temps)
    window = PDFreeApp()
    from theme import apply_theme, is_dark

    apply_theme(is_dark())
    window.show()

    if argv_paths:
        window.open_pdfs(argv_paths)

    def _on_new_connection():
        conn = _server.nextPendingConnection()
        if conn is None:
            return
        conn.waitForReadyRead(1000)
        raw = conn.readAll().data().decode(errors="ignore")
        conn.close()
        paths = [
            p
            for p in raw.split("\n")
            if p and p.lower().endswith(".pdf") and os.path.isfile(p)
        ]
        if paths:
            window.open_pdfs(paths)
        if window.isMinimized():
            window.showNormal()
        window.raise_()
        window.activateWindow()

    _server.newConnection.connect(_on_new_connection)

    _checker = UpdateChecker()
    _checker.update_available.connect(_on_update_available)
    QTimer.singleShot(3000, _checker.start)

    sys.exit(app.exec())
