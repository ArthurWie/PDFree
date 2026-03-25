import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QScrollArea,
    QFileDialog,
    QMessageBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from colors import (
    BLUE,
    BLUE_HOVER,
    GREEN,
    GREEN_HOVER,
    RED,
    EMERALD,
    G100,
    G200,
    G300,
    G400,
    G500,
    G700,
    G900,
    WHITE,
    BLUE_MED,
)
from icons import svg_pixmap

try:
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature

    _HAS_PYHANKO = True
except ImportError:
    _HAS_PYHANKO = False

logger = logging.getLogger(__name__)


def validate_signatures(path: str) -> list:
    results = []
    with open(path, "rb") as f:
        reader = PdfFileReader(f)
        for sig in reader.embedded_regular_signatures:
            try:
                status = validate_pdf_signature(sig)
                signer_name = ""
                try:
                    signer_name = sig.signer_cert.subject.human_friendly
                except Exception:
                    pass
                results.append(
                    {
                        "field": sig.field_name or "Signature",
                        "signer": signer_name,
                        "trusted": status.trusted,
                        "intact": status.bottom_line,
                        "summary": status.summary(),
                        "signing_time": (
                            str(status.signer_reported_dt)
                            if status.signer_reported_dt
                            else "Unknown"
                        ),
                        "has_timestamp": status.timestamp_validity is not None,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "field": sig.field_name or "Signature",
                        "signer": "",
                        "trusted": False,
                        "intact": False,
                        "summary": f"Validation error: {exc}",
                        "signing_time": "Unknown",
                        "has_timestamp": False,
                    }
                )
    return results


class _ValidateWorker(QThread):
    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, pdf_path, parent=None):
        super().__init__(parent)
        self._pdf_path = pdf_path

    def run(self):
        try:
            results = validate_signatures(self._pdf_path)
            self.finished.emit(results)
        except Exception as exc:
            self.failed.emit(str(exc))


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


def _section(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
        " background: transparent; border: none;"
    )
    return lbl


class ValidateSignatureTool(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        if not _HAS_PYHANKO:
            lay = QVBoxLayout(self)
            lbl = QLabel("Missing dependency.\n\nInstall with:\n  pip install pyhanko")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {G500}; font: 16px;")
            lay.addWidget(lbl)
            return

        self._pdf_path = ""
        self._worker = None
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

        title_row = QHBoxLayout()
        title_row.setSpacing(12)
        title_row.setContentsMargins(0, 0, 0, 0)
        icon_box = QLabel()
        icon_box.setFixedSize(40, 40)
        icon_box.setPixmap(svg_pixmap("shield-check", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)
        title_lbl = QLabel("Validate Signatures")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 20px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        lay.addWidget(_section("SOURCE FILE"))
        lay.addSpacing(8)
        lay.addWidget(self._drop_zone())
        lay.addSpacing(8)
        self._file_lbl = QLabel("No file loaded")
        self._file_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        self._file_lbl.setWordWrap(True)
        lay.addWidget(self._file_lbl)
        lay.addSpacing(20)

        lay.addWidget(_section("ABOUT"))
        lay.addSpacing(8)
        about_items = [
            (
                "Integrity",
                "Verifies that the document has not been altered since signing.",
            ),
            (
                "Trust",
                "Checks whether the signing certificate chains to a trusted root.",
            ),
            (
                "Timestamp",
                "Detects embedded RFC 3161 timestamps proving when the signature was applied.",
            ),
        ]
        for term, desc in about_items:
            row = QHBoxLayout()
            row.setContentsMargins(0, 2, 0, 2)
            row.setSpacing(8)
            dot = QLabel("•")
            dot.setFixedWidth(10)
            dot.setStyleSheet(
                f"color: {BLUE}; font: bold 13px; background: transparent; border: none;"
            )
            row.addWidget(dot)
            txt = QLabel(f"<b>{term}</b> — {desc}")
            txt.setWordWrap(True)
            txt.setStyleSheet(
                f"color: {G700}; font: 12px; background: transparent; border: none;"
            )
            row.addWidget(txt, 1)
            lay.addLayout(row)

        lay.addStretch()
        outer.addWidget(inner, 1)

        bottom = QWidget()
        bottom.setStyleSheet(f"background: {WHITE}; border-top: 1px solid {G200};")
        bot = QVBoxLayout(bottom)
        bot.setContentsMargins(24, 16, 24, 20)
        bot.setSpacing(10)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )
        bot.addWidget(self._status_lbl)

        self._validate_btn = _btn("Validate", GREEN, GREEN_HOVER, h=42)
        self._validate_btn.setEnabled(False)
        self._validate_btn.clicked.connect(self._validate)
        bot.addWidget(self._validate_btn)

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
        self._toolbar_file_lbl = QLabel("No file loaded")
        self._toolbar_file_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._toolbar_file_lbl)
        tb.addStretch()
        self._toolbar_count_lbl = QLabel("")
        self._toolbar_count_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; background: transparent; border: none;"
        )
        tb.addWidget(self._toolbar_count_lbl)
        v.addWidget(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._results_container = QWidget()
        self._results_container.setStyleSheet(f"background: {G100};")
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setContentsMargins(24, 24, 24, 24)
        self._results_layout.setSpacing(12)

        self._placeholder_lbl = QLabel("No digital signatures found in this PDF.")
        self._placeholder_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder_lbl.setStyleSheet(
            f"color: {G400}; font: 14px; background: transparent; border: none;"
        )
        self._placeholder_lbl.setVisible(False)
        self._results_layout.addWidget(self._placeholder_lbl)
        self._results_layout.addStretch()

        scroll.setWidget(self._results_container)
        v.addWidget(scroll, 1)
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

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        self._pdf_path = path
        name = Path(path).name
        self._file_lbl.setText(name)
        self._toolbar_file_lbl.setText(name)
        self._toolbar_count_lbl.setText("")
        self._validate_btn.setEnabled(True)
        self._status_lbl.setText("")
        self._clear_results()

    def _clear_results(self):
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._placeholder_lbl = QLabel("No digital signatures found in this PDF.")
        self._placeholder_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder_lbl.setStyleSheet(
            f"color: {G400}; font: 14px; background: transparent; border: none;"
        )
        self._placeholder_lbl.setVisible(False)
        self._results_layout.addWidget(self._placeholder_lbl)
        self._results_layout.addStretch()

    def _validate(self):
        if not self._pdf_path:
            return
        self._validate_btn.setEnabled(False)
        self._status_lbl.setText("Validating\u2026")
        self._worker = _ValidateWorker(self._pdf_path)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_finished(self, results: list):
        self._status_lbl.setText("")
        self._validate_btn.setEnabled(True)
        self._clear_results()

        if not results:
            self._placeholder_lbl.setVisible(True)
            self._toolbar_count_lbl.setText("0 signatures")
            return

        n = len(results)
        self._toolbar_count_lbl.setText(f"{n} signature{'s' if n != 1 else ''}")

        stretch_item = self._results_layout.takeAt(self._results_layout.count() - 1)

        for r in results:
            card = self._make_result_card(r)
            self._results_layout.addWidget(card)

        if stretch_item:
            self._results_layout.addStretch()

    def _on_failed(self, msg: str):
        self._status_lbl.setText("Failed.")
        self._validate_btn.setEnabled(True)
        QMessageBox.critical(self, "Validation Failed", msg)

    def _make_result_card(self, r: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: {WHITE}; border: 1px solid {G200}; border-radius: 10px; }}"
        )
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(6)

        header_row = QHBoxLayout()
        header_row.setSpacing(10)
        field_lbl = QLabel(r.get("field", "Signature"))
        field_lbl.setStyleSheet(
            f"color: {G900}; font: bold 14px; background: transparent; border: none;"
        )
        header_row.addWidget(field_lbl, 1)

        trusted = r.get("trusted", False)
        badge = QLabel("Trusted \u2713" if trusted else "Not trusted")
        badge_bg = EMERALD if trusted else RED
        badge.setStyleSheet(
            f"color: {WHITE}; background: {badge_bg}; border-radius: 4px;"
            f" font: bold 11px; padding: 2px 8px; border: none;"
        )
        badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        header_row.addWidget(badge)
        lay.addLayout(header_row)

        signer = r.get("signer", "")
        if signer:
            signer_lbl = QLabel(f"Signer: {signer}")
            signer_lbl.setWordWrap(True)
            signer_lbl.setStyleSheet(
                f"color: {G700}; font: 12px; background: transparent; border: none;"
            )
            lay.addWidget(signer_lbl)

        intact = r.get("intact", False)
        intact_text = "Document intact" if intact else "Document modified or invalid"
        intact_color = EMERALD if intact else RED
        intact_lbl = QLabel(intact_text)
        intact_lbl.setStyleSheet(
            f"color: {intact_color}; font: 12px; background: transparent; border: none;"
        )
        lay.addWidget(intact_lbl)

        summary = r.get("summary", "")
        if summary:
            summary_lbl = QLabel(summary)
            summary_lbl.setWordWrap(True)
            summary_lbl.setStyleSheet(
                f"color: {G500}; font: 12px; background: transparent; border: none;"
            )
            lay.addWidget(summary_lbl)

        details_row = QHBoxLayout()
        details_row.setSpacing(16)
        signing_time = r.get("signing_time", "Unknown")
        time_lbl = QLabel(f"Signed: {signing_time}")
        time_lbl.setStyleSheet(
            f"color: {G500}; font: 11px; background: transparent; border: none;"
        )
        details_row.addWidget(time_lbl)

        has_ts = r.get("has_timestamp", False)
        ts_lbl = QLabel("Timestamp: yes" if has_ts else "Timestamp: no")
        ts_lbl.setStyleSheet(
            f"color: {G500}; font: 11px; background: transparent; border: none;"
        )
        details_row.addWidget(ts_lbl)
        details_row.addStretch()
        lay.addLayout(details_row)

        return card

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
            self._worker.wait(3000)
