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


def test_add_page_numbers_produces_valid_pdf(tmp_path):
    from add_page_numbers_tool import _AddPageNumbersWorker

    src = _copy("multipage.pdf", tmp_path)
    out = tmp_path / "out_numbered.pdf"

    doc_tmp = fitz.open(str(src))
    total_pages = doc_tmp.page_count
    doc_tmp.close()

    results = {}

    worker = _AddPageNumbersWorker(
        str(src),
        str(out),
        total_pages=total_pages,
        skip=0,
        start=1,
        fmt="1",
        position="Bottom Center",
        fontsize=11.0,
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


def test_add_page_numbers_format_page_n(tmp_path):
    from add_page_numbers_tool import _AddPageNumbersWorker

    src = _copy("multipage.pdf", tmp_path)
    out = tmp_path / "out_numbered_fmt.pdf"

    doc_tmp = fitz.open(str(src))
    total_pages = doc_tmp.page_count
    doc_tmp.close()

    results = {}

    worker = _AddPageNumbersWorker(
        str(src),
        str(out),
        total_pages=total_pages,
        skip=0,
        start=1,
        fmt="Page 1 of N",
        position="Bottom Right",
        fontsize=10.0,
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


def test_add_page_numbers_skip_first_page(tmp_path):
    from add_page_numbers_tool import _AddPageNumbersWorker

    src = _copy("multipage.pdf", tmp_path)
    out = tmp_path / "out_numbered_skip.pdf"

    doc_tmp = fitz.open(str(src))
    total_pages = doc_tmp.page_count
    doc_tmp.close()

    results = {}

    worker = _AddPageNumbersWorker(
        str(src),
        str(out),
        total_pages=total_pages,
        skip=1,
        start=1,
        fmt="- 1 -",
        position="Top Center",
        fontsize=9.0,
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


def test_add_page_numbers_on_plain_pdf(tmp_path):
    from add_page_numbers_tool import _AddPageNumbersWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out_plain_numbered.pdf"

    doc_tmp = fitz.open(str(src))
    total_pages = doc_tmp.page_count
    doc_tmp.close()

    results = {}

    worker = _AddPageNumbersWorker(
        str(src),
        str(out),
        total_pages=total_pages,
        skip=0,
        start=1,
        fmt="Page 1",
        position="Bottom Left",
        fontsize=12.0,
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
