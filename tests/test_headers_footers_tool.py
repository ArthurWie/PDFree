import shutil
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")

_app = QApplication.instance() or QApplication(sys.argv)
CORPUS = Path(__file__).parent / "corpus"


def _copy(name, tmp):
    p = tmp / name
    shutil.copy2(CORPUS / name, p)
    return p


def test_headers_footers_produces_valid_pdf(tmp_path):
    from headers_footers_tool import _HeadersFootersWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out_hf.pdf"

    doc_tmp = fitz.open(str(src))
    total_pages = doc_tmp.page_count
    filename = src.name
    doc_tmp.close()

    header_inputs = {"left": "Left Header", "center": "Center Header", "right": ""}
    footer_inputs = {"left": "", "center": "{page} / {total}", "right": "Right Footer"}
    results = {}

    worker = _HeadersFootersWorker(
        str(src),
        str(out),
        total_pages,
        skip=0,
        font_size=10.0,
        margin=20,
        filename=filename,
        header_inputs=header_inputs,
        footer_inputs=footer_inputs,
    )
    worker.finished.connect(lambda *a: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    doc = fitz.open(str(out))
    assert doc.page_count == total_pages
    doc.close()


def test_headers_footers_skip_pages(tmp_path):
    from headers_footers_tool import _HeadersFootersWorker

    src = _copy("multipage.pdf", tmp_path)
    out = tmp_path / "out_hf_skip.pdf"

    doc_tmp = fitz.open(str(src))
    total_pages = doc_tmp.page_count
    filename = src.name
    doc_tmp.close()

    header_inputs = {"left": "", "center": "Page {page}", "right": ""}
    footer_inputs = {"left": "", "center": "", "right": ""}
    results = {}

    worker = _HeadersFootersWorker(
        str(src),
        str(out),
        total_pages,
        skip=1,
        font_size=11.0,
        margin=24,
        filename=filename,
        header_inputs=header_inputs,
        footer_inputs=footer_inputs,
    )
    worker.finished.connect(lambda *a: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    doc = fitz.open(str(out))
    assert doc.page_count == total_pages
    doc.close()
