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


def test_flatten_produces_valid_pdf(tmp_path):
    from flatten_tool import _FlattenWorker

    src = _copy("annotated.pdf", tmp_path)
    out = tmp_path / "out_flat.pdf"
    results = {}

    worker = _FlattenWorker(str(src), str(out), annots=True, js=True, links=False)
    worker.finished.connect(lambda *a: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    doc = fitz.open(str(out))
    assert doc.page_count > 0
    doc.close()


def test_flatten_removes_annotations(tmp_path):
    from flatten_tool import _FlattenWorker

    src = _copy("annotated.pdf", tmp_path)

    before_doc = fitz.open(str(src))
    before_count = sum(len(list(before_doc[i].annots())) for i in range(before_doc.page_count))
    before_doc.close()

    out = tmp_path / "out_flat_annots.pdf"
    results = {}

    worker = _FlattenWorker(str(src), str(out), annots=True, js=True, links=False)
    worker.finished.connect(lambda *a: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()

    after_doc = fitz.open(str(out))
    after_count = sum(len(list(after_doc[i].annots())) for i in range(after_doc.page_count))
    after_doc.close()

    assert after_count < before_count or before_count == 0


def test_flatten_no_annots_flag(tmp_path):
    from flatten_tool import _FlattenWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out_flat_noop.pdf"
    results = {}

    worker = _FlattenWorker(str(src), str(out), annots=False, js=False, links=False)
    worker.finished.connect(lambda *a: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    doc = fitz.open(str(out))
    assert doc.page_count > 0
    doc.close()
