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


def test_nup_2up_reduces_page_count(tmp_path):
    from nup_tool import _NUpWorker

    src = _copy("multipage.pdf", tmp_path)
    out = tmp_path / "out.pdf"

    src_doc = fitz.open(str(src))
    total = src_doc.page_count
    src_doc.close()
    assert total > 2, "multipage.pdf must have more than 2 pages for 2-up to reduce count"

    # A4 landscape
    out_w, out_h = 841.89, 595.28
    results = {}
    worker = _NUpWorker(str(src), str(out), "2up", out_w, out_h)
    worker.finished.connect(lambda path: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    doc = fitz.open(str(out))
    assert doc.page_count < total
    doc.close()


def test_nup_4up_valid_output(tmp_path):
    from nup_tool import _NUpWorker

    src = _copy("multipage.pdf", tmp_path)
    out = tmp_path / "out4up.pdf"

    src_doc = fitz.open(str(src))
    total = src_doc.page_count
    src_doc.close()

    out_w, out_h = 841.89, 595.28
    results = {}
    worker = _NUpWorker(str(src), str(out), "4up", out_w, out_h)
    worker.finished.connect(lambda path: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    doc = fitz.open(str(out))
    assert doc.page_count > 0
    assert doc.page_count <= total
    doc.close()
