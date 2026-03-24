"""Worker tests for office_to_pdf_tool._ConvertWorker."""

import shutil
import sys

import pytest
from PySide6.QtWidgets import QApplication

pytestmark = pytest.mark.skipif(
    shutil.which("soffice") is None and shutil.which("libreoffice") is None,
    reason="LibreOffice not installed",
)

_app = QApplication.instance() or QApplication(sys.argv)


def _make_docx(path):
    import docx

    doc = docx.Document()
    doc.add_paragraph("PDFree office_to_pdf test document.")
    doc.save(str(path))


def test_convert_docx_to_pdf(tmp_path):
    from office_to_pdf_tool import _ConvertWorker, _find_soffice

    soffice = _find_soffice()
    assert soffice is not None

    src = tmp_path / "test.docx"
    _make_docx(src)
    dst = tmp_path / "out.pdf"

    results = {}
    worker = _ConvertWorker(soffice, str(src), str(dst))
    worker.finished.connect(lambda p: results.update({"done": p}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(120000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert dst.exists()
    assert dst.stat().st_size > 0
    assert dst.read_bytes()[:4] == b"%PDF"
