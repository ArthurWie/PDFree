"""Worker tests for ocr_tool._OCRWorker."""

import shutil
import sys

import pytest
from PySide6.QtWidgets import QApplication

pytestmark = pytest.mark.skipif(
    shutil.which("ocrmypdf") is None or shutil.which("tesseract") is None,
    reason="ocrmypdf or tesseract not installed",
)

_app = QApplication.instance() or QApplication(sys.argv)

CORPUS = __import__("pathlib").Path(__file__).parent / "corpus"


def _copy(name, tmp):
    p = tmp / name
    shutil.copy2(CORPUS / name, p)
    return p


def test_ocr_produces_output_pdf(tmp_path):
    from ocr_tool import _OCRWorker

    src = _copy("plain.pdf", tmp_path)
    dst = tmp_path / "out_ocr.pdf"

    results = {}
    worker = _OCRWorker(
        pdf_path=str(src),
        out_path=str(dst),
        lang="eng",
        deskew=False,
        force_ocr=False,
        skip_text=True,
    )
    worker.finished.connect(lambda p: results.update({"done": p}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(120000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert dst.exists()
    assert dst.stat().st_size > 0
    assert dst.read_bytes()[:4] == b"%PDF"
