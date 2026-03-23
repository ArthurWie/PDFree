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


def test_sanitize_all_options(tmp_path):
    from sanitize_tool import _SanitizeWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out_sanitized.pdf"
    results = {}

    worker = _SanitizeWorker(
        str(src),
        str(out),
        js=True,
        attach=True,
        meta=True,
        thumbs=True,
        xml=True,
        repair=True,
    )
    worker.finished.connect(lambda p: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()

    doc = fitz.open(str(out))
    assert doc.page_count > 0
    doc.close()


def test_sanitize_no_repair(tmp_path):
    from sanitize_tool import _SanitizeWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out_sanitized_norepair.pdf"
    results = {}

    worker = _SanitizeWorker(
        str(src),
        str(out),
        js=True,
        attach=True,
        meta=False,
        thumbs=False,
        xml=False,
        repair=False,
    )
    worker.finished.connect(lambda p: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()

    doc = fitz.open(str(out))
    assert doc.page_count > 0
    doc.close()


def test_sanitize_multipage(tmp_path):
    from sanitize_tool import _SanitizeWorker

    src = _copy("multipage.pdf", tmp_path)
    out = tmp_path / "out_sanitized_multi.pdf"
    results = {}

    worker = _SanitizeWorker(
        str(src),
        str(out),
        js=True,
        attach=True,
        meta=True,
        thumbs=True,
        xml=True,
        repair=True,
    )
    worker.finished.connect(lambda p: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()

    src_doc = fitz.open(str(src))
    src_pages = src_doc.page_count
    src_doc.close()

    doc = fitz.open(str(out))
    assert doc.page_count == src_pages
    doc.close()
