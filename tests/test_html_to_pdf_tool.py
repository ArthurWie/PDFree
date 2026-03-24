"""Worker tests for html_to_pdf_tool._ConvertWorker."""

import sys

import pytest
from PySide6.QtWidgets import QApplication

pytest.importorskip("weasyprint", reason="weasyprint not installed")

_app = QApplication.instance() or QApplication(sys.argv)


def test_convert_html_string_to_pdf(tmp_path):
    from html_to_pdf_tool import _ConvertWorker

    dst = tmp_path / "out.pdf"
    html_source = "<html><body><h1>Hello PDFree</h1></body></html>"

    results = {}
    worker = _ConvertWorker("paste", html_source, str(dst))
    worker.finished.connect(lambda p: results.update({"done": p}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(30000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert dst.exists()
    assert dst.stat().st_size > 0
    assert dst.read_bytes()[:4] == b"%PDF"


def test_convert_html_file_to_pdf(tmp_path):
    from html_to_pdf_tool import _ConvertWorker

    html_file = tmp_path / "page.html"
    html_file.write_text("<html><body><p>Test page</p></body></html>", encoding="utf-8")
    dst = tmp_path / "from_file.pdf"

    results = {}
    worker = _ConvertWorker("file", str(html_file), str(dst))
    worker.finished.connect(lambda p: results.update({"done": p}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(30000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert dst.exists()
    assert dst.stat().st_size > 0
    assert dst.read_bytes()[:4] == b"%PDF"
