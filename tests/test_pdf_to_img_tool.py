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


def test_export_png_all_pages(tmp_path):
    from pdf_to_img_tool import _ExportImagesWorker

    src = _copy("plain.pdf", tmp_path)
    out_dir = tmp_path / "images"
    results = {}

    doc = fitz.open(str(src))
    page_count = doc.page_count
    doc.close()
    pages = list(range(page_count))

    worker = _ExportImagesWorker(
        str(src),
        str(out_dir),
        pages,
        dpi=72,
        fmt="png",
        quality=85,
        stem="plain",
    )
    worker.finished.connect(lambda d, n: results.update({"done": True, "count": n}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    png_files = list(out_dir.glob("*.png"))
    assert len(png_files) >= 1


def test_export_jpeg_single_page(tmp_path):
    from pdf_to_img_tool import _ExportImagesWorker

    src = _copy("plain.pdf", tmp_path)
    out_dir = tmp_path / "jpeg_out"
    results = {}

    worker = _ExportImagesWorker(
        str(src),
        str(out_dir),
        [0],
        dpi=96,
        fmt="jpeg",
        quality=80,
        stem="plain",
    )
    worker.finished.connect(lambda d, n: results.update({"done": True, "count": n}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    jpg_files = list(out_dir.glob("*.jpg"))
    assert len(jpg_files) == 1


def test_export_multipage_correct_count(tmp_path):
    from pdf_to_img_tool import _ExportImagesWorker

    src = _copy("multipage.pdf", tmp_path)
    out_dir = tmp_path / "multi_out"
    results = {}

    doc = fitz.open(str(src))
    page_count = doc.page_count
    doc.close()
    pages = list(range(page_count))

    worker = _ExportImagesWorker(
        str(src),
        str(out_dir),
        pages,
        dpi=72,
        fmt="png",
        quality=85,
        stem="multipage",
    )
    worker.finished.connect(lambda d, n: results.update({"done": True, "count": n}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert results.get("count") == page_count
    png_files = list(out_dir.glob("*.png"))
    assert len(png_files) == page_count


def test_export_subset_of_pages(tmp_path):
    from pdf_to_img_tool import _ExportImagesWorker

    src = _copy("multipage.pdf", tmp_path)
    out_dir = tmp_path / "subset_out"
    results = {}

    worker = _ExportImagesWorker(
        str(src),
        str(out_dir),
        [0],
        dpi=72,
        fmt="png",
        quality=85,
        stem="multipage",
    )
    worker.finished.connect(lambda d, n: results.update({"done": True, "count": n}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert results.get("count") == 1
    png_files = list(out_dir.glob("*.png"))
    assert len(png_files) == 1
