"""Worker tests for pdf_to_word_tool._ConvertWorker."""

import shutil
import sys

import pytest
from PySide6.QtWidgets import QApplication

pytest.importorskip("pdf2docx", reason="pdf2docx not installed")

_app = QApplication.instance() or QApplication(sys.argv)

CORPUS = __import__("pathlib").Path(__file__).parent / "corpus"


def _copy(name, tmp):
    p = tmp / name
    shutil.copy2(CORPUS / name, p)
    return p


def test_convert_produces_docx(tmp_path):
    from pdf_to_word_tool import _ConvertWorker

    src = _copy("plain.pdf", tmp_path)
    dst = tmp_path / "out.docx"

    results = {}
    worker = _ConvertWorker(str(src), str(dst), 0, None)
    worker.finished.connect(lambda p: results.update({"done": p}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(30000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert dst.exists()
    assert dst.stat().st_size > 0


def test_convert_page_range(tmp_path):
    from pdf_to_word_tool import _ConvertWorker

    src = _copy("plain.pdf", tmp_path)
    dst = tmp_path / "range.docx"

    results = {}
    worker = _ConvertWorker(str(src), str(dst), 0, 1)
    worker.finished.connect(lambda p: results.update({"done": p}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(30000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert dst.exists()
    assert dst.stat().st_size > 0
