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


def test_scale_to_a4_produces_valid_pdf(tmp_path):
    from scale_pages_tool import _ScalePagesWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out.pdf"

    # A4 portrait in points
    target_w, target_h = 595.28, 841.89
    results = {}
    worker = _ScalePagesWorker(str(src), str(out), target_w, target_h, True, True)
    worker.finished.connect(lambda path: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    doc = fitz.open(str(out))
    assert doc.page_count > 0
    doc.close()


def test_scale_without_aspect_preserve(tmp_path):
    from scale_pages_tool import _ScalePagesWorker

    src = _copy("multipage.pdf", tmp_path)
    out = tmp_path / "out.pdf"

    src_doc = fitz.open(str(src))
    total = src_doc.page_count
    src_doc.close()

    target_w, target_h = 612.0, 792.0
    results = {}
    worker = _ScalePagesWorker(str(src), str(out), target_w, target_h, True, False)
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
