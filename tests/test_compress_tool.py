"""Worker tests for compress_tool._CompressWorker."""

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


def test_compress_lossless_produces_valid_pdf(tmp_path):
    from compress_tool import _CompressWorker, PRESETS

    src = _copy("multipage.pdf", tmp_path)
    dst = tmp_path / "out.pdf"
    lossless_preset = next(p for p in PRESETS if p["dpi"] is None)

    results = {}
    worker = _CompressWorker(str(src), str(dst), lossless_preset)
    worker.finished.connect(lambda p: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert dst.exists()
    doc = fitz.open(str(dst))
    assert doc.page_count >= 1
    doc.close()


def test_compress_screen_preset_produces_valid_pdf(tmp_path):
    from compress_tool import _CompressWorker, PRESETS

    src = _copy("plain.pdf", tmp_path)
    dst = tmp_path / "out.pdf"
    screen_preset = next(p for p in PRESETS if p.get("dpi") == 72)

    results = {}
    worker = _CompressWorker(str(src), str(dst), screen_preset)
    worker.finished.connect(lambda p: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert dst.exists()
    doc = fitz.open(str(dst))
    assert doc.page_count >= 1
    doc.close()
