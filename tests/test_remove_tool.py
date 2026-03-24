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


def test_remove_keeps_specified_pages(tmp_path):
    from remove_tool import _RemovePagesWorker

    src = _copy("multipage.pdf", tmp_path)
    out = tmp_path / "out.pdf"

    src_doc = fitz.open(str(src))
    total = src_doc.page_count
    src_doc.close()
    assert total > 1, "multipage.pdf must have more than 1 page"

    pages_to_keep = [0]
    results = {}
    worker = _RemovePagesWorker(str(src), str(out), pages_to_keep)
    worker.finished.connect(
        lambda path, removed, kept: results.update({"done": True, "kept": kept})
    )
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    doc = fitz.open(str(out))
    assert doc.page_count == 1
    assert doc.page_count < total
    doc.close()


def test_remove_multiple_keeps_correct_count(tmp_path):
    from remove_tool import _RemovePagesWorker

    src = _copy("multipage.pdf", tmp_path)
    out = tmp_path / "out.pdf"

    src_doc = fitz.open(str(src))
    total = src_doc.page_count
    src_doc.close()
    assert total >= 3, "multipage.pdf must have at least 3 pages for this test"

    pages_to_keep = [0, 2]
    results = {}
    worker = _RemovePagesWorker(str(src), str(out), pages_to_keep)
    worker.finished.connect(lambda path, removed, kept: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    doc = fitz.open(str(out))
    assert doc.page_count == 2
    doc.close()
