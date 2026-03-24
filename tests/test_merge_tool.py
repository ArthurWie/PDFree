"""Worker tests for merge_tool._MergeWorker."""

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


def test_merge_two_pdfs(tmp_path):
    from merge_tool import _MergeWorker

    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    shutil.copy2(CORPUS / "plain.pdf", a)
    shutil.copy2(CORPUS / "plain.pdf", b)
    out = tmp_path / "merged.pdf"

    doc_a = fitz.open(str(a))
    pages_a = doc_a.page_count
    doc_a.close()

    results = {}
    worker = _MergeWorker([{"path": str(a)}, {"path": str(b)}], str(out))
    worker.finished.connect(lambda p, n: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(10000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    merged = fitz.open(str(out))
    assert merged.page_count == pages_a * 2
    merged.close()


def test_merge_single_file(tmp_path):
    from merge_tool import _MergeWorker

    src = tmp_path / "only.pdf"
    shutil.copy2(CORPUS / "multipage.pdf", src)
    out = tmp_path / "out.pdf"

    results = {}
    worker = _MergeWorker([{"path": str(src)}], str(out))
    worker.finished.connect(lambda p, n: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(10000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    doc = fitz.open(str(out))
    assert doc.page_count >= 1
    doc.close()
