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


def _count_annots(path):
    doc = fitz.open(str(path))
    total = sum(len(list(doc[i].annots())) for i in range(doc.page_count))
    doc.close()
    return total


def test_remove_annotations_produces_valid_pdf(tmp_path):
    from remove_annotations_tool import _RemoveAnnotationsWorker

    src = _copy("annotated.pdf", tmp_path)
    out = tmp_path / "out_clean.pdf"
    results = {}

    worker = _RemoveAnnotationsWorker(str(src), str(out))
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


def test_remove_annotations_clears_all_annots(tmp_path):
    from remove_annotations_tool import _RemoveAnnotationsWorker

    src = _copy("annotated.pdf", tmp_path)
    out = tmp_path / "out_clean_annots.pdf"
    results = {}

    worker = _RemoveAnnotationsWorker(str(src), str(out))
    worker.finished.connect(lambda *a: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    assert _count_annots(out) == 0


def test_remove_annotations_on_plain_pdf(tmp_path):
    from remove_annotations_tool import _RemoveAnnotationsWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out_plain_clean.pdf"
    results = {}

    worker = _RemoveAnnotationsWorker(str(src), str(out))
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
