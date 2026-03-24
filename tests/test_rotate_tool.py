"""Worker tests for rotate_tool._RotateWorker."""

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


def test_rotate_all_pages_90(tmp_path):
    from rotate_tool import _RotateWorker

    src = _copy("multipage.pdf", tmp_path)
    out = tmp_path / "out.pdf"

    doc = fitz.open(str(src))
    total = doc.page_count
    doc.close()

    rotations = {i: 90 for i in range(total)}
    results = {}
    worker = _RotateWorker(str(src), str(out), rotations, total)
    worker.finished.connect(lambda p, n: results.update({"done": True, "count": n}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(10000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    doc = fitz.open(str(out))
    assert doc.page_count == total
    doc.close()
    assert results.get("count") == total


def test_rotate_single_page(tmp_path):
    from rotate_tool import _RotateWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out.pdf"

    doc = fitz.open(str(src))
    total = doc.page_count
    doc.close()

    rotations = {0: 180}
    results = {}
    worker = _RotateWorker(str(src), str(out), rotations, total)
    worker.finished.connect(lambda p, n: results.update({"done": True, "count": n}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(10000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    doc = fitz.open(str(out))
    assert doc.page_count == total
    doc.close()
