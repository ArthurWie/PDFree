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


def test_watermark_diagonal(tmp_path):
    from watermark_tool import _WatermarkWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out_watermarked.pdf"
    results = {}

    worker = _WatermarkWorker(
        str(src),
        str(out),
        "CONFIDENTIAL",
        48.0,
        (0.5, 0.5, 0.5),
        0.3,
        "Diagonal",
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


def test_watermark_center(tmp_path):
    from watermark_tool import _WatermarkWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out_center.pdf"
    results = {}

    worker = _WatermarkWorker(
        str(src),
        str(out),
        "DRAFT",
        36.0,
        (0.8, 0.1, 0.1),
        0.5,
        "Center",
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


def test_watermark_multipage_preserves_pages(tmp_path):
    from watermark_tool import _WatermarkWorker

    src = _copy("multipage.pdf", tmp_path)
    out = tmp_path / "out_multi_watermarked.pdf"
    results = {}

    src_doc = fitz.open(str(src))
    src_pages = src_doc.page_count
    src_doc.close()

    worker = _WatermarkWorker(
        str(src),
        str(out),
        "SAMPLE",
        24.0,
        (0.0, 0.0, 0.0),
        0.2,
        "Bottom",
    )
    worker.finished.connect(lambda p: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()

    doc = fitz.open(str(out))
    assert doc.page_count == src_pages
    doc.close()


def test_watermark_top_position(tmp_path):
    from watermark_tool import _WatermarkWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out_top.pdf"
    results = {}

    worker = _WatermarkWorker(
        str(src),
        str(out),
        "TOP MARK",
        20.0,
        (0.1, 0.3, 0.85),
        0.4,
        "Top",
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
