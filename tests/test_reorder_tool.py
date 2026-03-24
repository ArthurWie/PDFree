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


def test_reorder_preserves_page_count(tmp_path):
    from reorder_tool import _ReorderWorker

    src = _copy("multipage.pdf", tmp_path)
    out = tmp_path / "out.pdf"

    src_doc = fitz.open(str(src))
    total = src_doc.page_count
    src_doc.close()
    assert total > 1, "multipage.pdf must have more than 1 page"

    order = list(range(total - 1, -1, -1))
    results = {}
    worker = _ReorderWorker(str(src), str(out), order)
    worker.finished.connect(lambda path: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    doc = fitz.open(str(out))
    assert doc.page_count == total
    doc.close()


def test_reorder_identity_order(tmp_path):
    from reorder_tool import _ReorderWorker

    src = _copy("multipage.pdf", tmp_path)
    out = tmp_path / "out.pdf"

    src_doc = fitz.open(str(src))
    total = src_doc.page_count
    src_doc.close()

    order = list(range(total))
    results = {}
    worker = _ReorderWorker(str(src), str(out), order)
    worker.finished.connect(lambda path: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    doc = fitz.open(str(out))
    assert doc.page_count == total
    doc.close()
