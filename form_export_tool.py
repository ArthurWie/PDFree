"""Form Export Tool – extract AcroForm field data to JSON or CSV.

Iterates every widget on every page using fitz.Page.widgets(), collects
field name, type, value, and page number, displays them in a table, and
lets the user export the dataset as JSON or CSV.
"""

import csv
import json
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QFileDialog,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QAbstractItemView,
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
    import fitz
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


class _ExtractWorker(QThread):
    finished = Signal(list)  # list of dicts
    failed = Signal(str)

    def __init__(self, pdf_path: str):
        super().__init__()
        self._pdf_path = pdf_path

    def run(self):
        try:
            rows = []
            doc = fitz.open(self._pdf_path)
            try:
                for pg_idx in range(doc.page_count):
                    page = doc[pg_idx]
                    for w in page.widgets():
                        rows.append(
                            {
                                "page": pg_idx + 1,
                                "field_name": w.field_name or "",
                                "field_type": w.field_type_string or "",
                                "field_value": str(w.field_value)
                                if w.field_value is not None
                                else "",
                            }
                        )
            finally:
                doc.close()
            self.finished.emit(rows)
        except Exception as exc:
            logger.exception("form extract failed")
            self.failed.emit(str(exc))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _section(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
        " background: transparent; border: none;"
    )
    return lbl


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


class FormExportTool(QWidget):
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
        self._rows: list[dict] = []
        self._worker = None
        self._build_ui()
        self.setAcceptDrops(True)

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_left())
        root.addWidget(self._build_right(), 1)

    # ------------------------------------------------------------------
    # Left panel
    # ------------------------------------------------------------------

    def _build_left(self) -> QWidget:
        left = QWidget()
        left.setFixedWidth(320)
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
        icon_box.setPixmap(svg_pixmap("table", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)
        title_lbl = QLabel("Export Form Data")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 18px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        # Source file
        lay.addWidget(_section("SOURCE FILE"))
        lay.addSpacing(8)
        dz = QFrame()
        dz.setFixedHeight(52)
        dz.setStyleSheet(
            f"background: {G100}; border: 2px dashed {G200}; border-radius: 12px;"
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
        self._file_lbl.setWordWrap(True)
        self._file_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        lay.addWidget(self._file_lbl)
        lay.addSpacing(24)

        # Info
        lay.addWidget(_section("ABOUT"))
        lay.addSpacing(8)
        info = QLabel(
            "Reads every AcroForm field across all pages and collects "
            "the field name, type, and current value. Export the data "
            "as JSON (structured) or CSV (flat table)."
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        lay.addWidget(info)
        lay.addStretch()

        outer.addWidget(inner, 1)

        # Bottom bar
        bottom = QWidget()
        bottom.setStyleSheet(f"background: {WHITE}; border-top: 1px solid {G200};")
        bot = QVBoxLayout(bottom)
        bot.setContentsMargins(24, 16, 24, 20)
        bot.setSpacing(10)

        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )
        bot.addWidget(self._status_lbl)

        self._json_btn = _btn("Export as JSON", GREEN, GREEN_HOVER, h=38)
        self._json_btn.setEnabled(False)
        self._json_btn.clicked.connect(self._export_json)
        bot.addWidget(self._json_btn)

        self._csv_btn = _btn("Export as CSV", BLUE, BLUE_HOVER, h=38)
        self._csv_btn.setEnabled(False)
        self._csv_btn.clicked.connect(self._export_csv)
        bot.addWidget(self._csv_btn)

        self._xlsx_btn = _btn("Export as XLSX", BLUE, BLUE_HOVER, h=38)
        self._xlsx_btn.setEnabled(False)
        self._xlsx_btn.clicked.connect(self._export_xlsx)
        bot.addWidget(self._xlsx_btn)

        outer.addWidget(bottom)
        return left

    # ------------------------------------------------------------------
    # Right panel — field table
    # ------------------------------------------------------------------

    def _build_right(self) -> QWidget:
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
        self._field_count_lbl = QLabel("")
        self._field_count_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        tb.addWidget(self._field_count_lbl)
        v.addWidget(toolbar)

        self._table = QTreeWidget()
        self._table.setColumnCount(4)
        self._table.setHeaderLabels(["Page", "Field Name", "Type", "Value"])
        self._table.setRootIsDecorated(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setSortingEnabled(True)
        self._table.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self._table.header().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setStyleSheet(f"""
            QTreeWidget {{
                background: {WHITE}; border: none; font: 13px;
                alternate-background-color: {G100};
            }}
            QTreeWidget::item {{ padding: 4px 8px; }}
            QTreeWidget::item:selected {{ background: #DBEAFE; color: {G900}; }}
            QHeaderView::section {{
                background: {G100}; color: {G700}; font: bold 11px;
                padding: 6px 8px; border: none;
                border-bottom: 1px solid {G200};
            }}
        """)

        placeholder = QWidget()
        placeholder.setStyleSheet(f"background: {G100};")
        pl = QVBoxLayout(placeholder)
        pl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder_lbl = QLabel(
            "Load a PDF with form fields\nto preview field data here."
        )
        self._placeholder_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder_lbl.setStyleSheet(
            f"color: {G400}; font: 14px; background: transparent; border: none;"
        )
        pl.addWidget(self._placeholder_lbl)

        self._table.setVisible(False)
        v.addWidget(placeholder, 1)
        v.addWidget(self._table, 1)
        self._placeholder_widget = placeholder

        return right

    # ------------------------------------------------------------------
    # File loading
    # ------------------------------------------------------------------

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        self._pdf_path = path
        name = Path(path).name
        self._file_lbl.setText(name)
        self._toolbar_lbl.setText(name)
        self._status_lbl.setText("Extracting fields…")
        self._json_btn.setEnabled(False)
        self._csv_btn.setEnabled(False)
        self._xlsx_btn.setEnabled(False)
        self._rows = []
        self._table.clear()

        self._worker = _ExtractWorker(path)
        self._worker.finished.connect(self._on_extracted)
        self._worker.failed.connect(self._on_extract_failed)
        self._worker.start()

    def _on_extracted(self, rows: list):
        self._rows = rows
        n = len(rows)
        self._status_lbl.setText("")
        if n == 0:
            self._field_count_lbl.setText("No form fields found")
            self._status_lbl.setText("No form fields found in this PDF.")
            self._status_lbl.setStyleSheet(
                f"color: {G500}; font: 12px; border: none; background: transparent;"
            )
        else:
            self._field_count_lbl.setText(f"{n} field{'s' if n != 1 else ''}")
            self._populate_table(rows)
            self._json_btn.setEnabled(True)
            self._csv_btn.setEnabled(True)
            self._xlsx_btn.setEnabled(True)

    def _on_extract_failed(self, msg: str):
        QMessageBox.critical(self, "Error", msg)
        self._status_lbl.setText("Failed to read PDF.")

    def _populate_table(self, rows: list):
        self._table.clear()
        for row in rows:
            item = QTreeWidgetItem(
                [
                    str(row["page"]),
                    row["field_name"],
                    row["field_type"],
                    row["field_value"],
                ]
            )
            item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
            self._table.addTopLevelItem(item)
        self._table.setVisible(True)
        self._placeholder_widget.setVisible(False)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_json(self):
        if not self._rows:
            return
        stem = Path(self._pdf_path).stem
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save JSON",
            str(Path(self._pdf_path).parent / f"{stem}_fields.json"),
            "JSON Files (*.json)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._rows, f, indent=2, ensure_ascii=False)
            self._status_lbl.setText(f"Saved: {Path(path).name}")
            self._status_lbl.setStyleSheet(
                f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
            )
        except Exception as exc:
            logger.exception("json export failed")
            QMessageBox.critical(self, "Export failed", str(exc))

    def _export_csv(self):
        if not self._rows:
            return
        stem = Path(self._pdf_path).stem
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save CSV",
            str(Path(self._pdf_path).parent / f"{stem}_fields.csv"),
            "CSV Files (*.csv)",
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["page", "field_name", "field_type", "field_value"]
                )
                writer.writeheader()
                writer.writerows(self._rows)
            self._status_lbl.setText(f"Saved: {Path(path).name}")
            self._status_lbl.setStyleSheet(
                f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
            )
        except Exception as exc:
            logger.exception("csv export failed")
            QMessageBox.critical(self, "Export failed", str(exc))

    def _export_xlsx(self):
        if not self._rows:
            return
        stem = Path(self._pdf_path).stem
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Excel",
            str(Path(self._pdf_path).parent / f"{stem}_fields.xlsx"),
            "Excel Files (*.xlsx)",
        )
        if not path:
            return
        try:
            import openpyxl

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Form Fields"
            ws.append(["Page", "Field Name", "Type", "Value"])
            for row in self._rows:
                ws.append(
                    [
                        row["page"],
                        row["field_name"],
                        row["field_type"],
                        row["field_value"],
                    ]
                )
            wb.save(path)
            self._status_lbl.setText(f"Saved: {Path(path).name}")
            self._status_lbl.setStyleSheet(
                f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
            )
        except Exception as exc:
            logger.exception("xlsx export failed")
            QMessageBox.critical(self, "Export failed", str(exc))

    # ------------------------------------------------------------------
    # Drag and drop
    # ------------------------------------------------------------------

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
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait()
