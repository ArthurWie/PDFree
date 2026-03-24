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


def test_export_diff_identical_pdfs(tmp_path):
    from compare_tool import _ExportDiffWorker

    src_a = _copy("plain.pdf", tmp_path)
    src_b = tmp_path / "plain_b.pdf"
    shutil.copy2(src_a, src_b)
    out = tmp_path / "diff.pdf"

    results = {}
    worker = _ExportDiffWorker(str(src_a), str(src_b), str(out))
    worker.finished.connect(lambda path: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()


def test_export_diff_multipage(tmp_path):
    from compare_tool import _ExportDiffWorker

    src_a = _copy("multipage.pdf", tmp_path)
    src_b = tmp_path / "multipage_b.pdf"
    shutil.copy2(src_a, src_b)
    out = tmp_path / "diff_multi.pdf"

    results = {}
    worker = _ExportDiffWorker(str(src_a), str(src_b), str(out))
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
