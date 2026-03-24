"""Worker tests for pdf_to_excel_tool._ExcelExtractionWorker."""

import shutil
import sys

import pytest
from PySide6.QtWidgets import QApplication

pytest.importorskip("fitz", reason="PyMuPDF not installed")
pytest.importorskip("pdfplumber", reason="pdfplumber not installed")
pytest.importorskip("openpyxl", reason="openpyxl not installed")

_app = QApplication.instance() or QApplication(sys.argv)

CORPUS = __import__("pathlib").Path(__file__).parent / "corpus"

_DEFAULT_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "intersection_y_tolerance": 3,
    "intersection_x_tolerance": 3,
    "snap_y_tolerance": 3,
    "snap_x_tolerance": 3,
    "edge_min_length": 3,
    "min_words_vertical": 1,
    "min_words_horizontal": 1,
    "keep_blank_chars": False,
    "text_tolerance": 3,
    "text_x_tolerance": 3,
    "text_y_tolerance": 3,
    "explicit_vertical_lines": [],
    "explicit_horizontal_lines": [],
}


def _copy(name, tmp):
    p = tmp / name
    shutil.copy2(CORPUS / name, p)
    return p


def test_excel_extraction_produces_xlsx(tmp_path):
    from pdf_to_excel_tool import _ExcelExtractionWorker

    src = _copy("plain.pdf", tmp_path)
    dst = tmp_path / "out.xlsx"

    results = {}
    worker = _ExcelExtractionWorker(
        pdf_path=str(src),
        password="",
        pages=[0],
        out_path=str(dst),
        settings=_DEFAULT_SETTINGS,
        min_rows=1,
        min_cols=1,
        skip_image=False,
        sheet_mode="Table",
        bold_header=True,
        auto_fit=True,
    )
    worker.finished.connect(lambda report, out_dir: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(30000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert dst.exists()
    assert dst.stat().st_size > 0


def test_excel_extraction_multipage(tmp_path):
    import fitz

    src = _copy("multipage.pdf", tmp_path)
    dst = tmp_path / "multi.xlsx"
    doc = fitz.open(str(src))
    page_count = doc.page_count
    doc.close()

    from pdf_to_excel_tool import _ExcelExtractionWorker

    results = {}
    worker = _ExcelExtractionWorker(
        pdf_path=str(src),
        password="",
        pages=list(range(page_count)),
        out_path=str(dst),
        settings=_DEFAULT_SETTINGS,
        min_rows=1,
        min_cols=1,
        skip_image=False,
        sheet_mode="Page",
        bold_header=False,
        auto_fit=False,
    )
    worker.finished.connect(lambda report, out_dir: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(30000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert dst.exists()
    assert dst.stat().st_size > 0
