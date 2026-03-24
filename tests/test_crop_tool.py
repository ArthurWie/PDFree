"""Worker tests for crop_tool._CropWorker."""

import shutil
import sys

import pytest
from PySide6.QtWidgets import QApplication

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")

_app = QApplication.instance() or QApplication(sys.argv)

CORPUS = __import__("pathlib").Path(__file__).parent / "corpus"


def _copy(name, tmp):
    p = tmp / name
    shutil.copy2(CORPUS / name, p)
    return p


def test_crop_reduces_page_rect(tmp_path):
    from crop_tool import _CropWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out.pdf"

    doc = fitz.open(str(src))
    r = doc.load_page(0).rect
    doc.close()

    margin = 10.0
    results = {}
    worker = _CropWorker(
        str(src),
        str(out),
        apply_all=True,
        current_page=0,
        page_w=r.width,
        page_h=r.height,
        x0=margin,
        y0=margin,
        x1=r.width - margin,
        y1=r.height - margin,
    )
    worker.finished.connect(lambda p: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(10000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    doc = fitz.open(str(out))
    new_rect = doc.load_page(0).rect
    doc.close()
    assert new_rect.width < r.width
    assert new_rect.height < r.height


def test_crop_single_page_only(tmp_path):
    from crop_tool import _CropWorker

    src = _copy("multipage.pdf", tmp_path)
    out = tmp_path / "out.pdf"

    doc = fitz.open(str(src))
    total = doc.page_count
    r = doc.load_page(0).rect
    doc.close()

    margin = 20.0
    results = {}
    worker = _CropWorker(
        str(src),
        str(out),
        apply_all=False,
        current_page=0,
        page_w=r.width,
        page_h=r.height,
        x0=margin,
        y0=margin,
        x1=r.width - margin,
        y1=r.height - margin,
    )
    worker.finished.connect(lambda p: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(10000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    doc = fitz.open(str(out))
    assert doc.page_count == total
    doc.close()
