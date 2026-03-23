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


def test_change_metadata_produces_valid_pdf(tmp_path):
    from change_metadata_tool import _ChangeMetadataWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out_meta.pdf"
    new_meta = {
        "title": "Test Title",
        "author": "Test Author",
        "subject": "",
        "keywords": "",
        "creator": "",
        "producer": "",
        "creationDate": "",
        "modDate": "",
    }
    results = {}

    worker = _ChangeMetadataWorker(str(src), str(out), new_meta)
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


def test_change_metadata_sets_title_and_author(tmp_path):
    from change_metadata_tool import _ChangeMetadataWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out_meta_values.pdf"
    new_meta = {
        "title": "My Test Document",
        "author": "Jane Doe",
        "subject": "Testing",
        "keywords": "",
        "creator": "",
        "producer": "",
        "creationDate": "",
        "modDate": "",
    }
    results = {}

    worker = _ChangeMetadataWorker(str(src), str(out), new_meta)
    worker.finished.connect(lambda *a: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()

    doc = fitz.open(str(out))
    meta = doc.metadata
    doc.close()

    assert meta.get("title") == "My Test Document"
    assert meta.get("author") == "Jane Doe"


def test_change_metadata_clears_fields(tmp_path):
    from change_metadata_tool import _ChangeMetadataWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out_meta_clear.pdf"
    new_meta = {
        "title": "",
        "author": "",
        "subject": "",
        "keywords": "",
        "creator": "",
        "producer": "",
        "creationDate": "",
        "modDate": "",
    }
    results = {}

    worker = _ChangeMetadataWorker(str(src), str(out), new_meta)
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
