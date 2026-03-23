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


def _discover_images(pdf_path):
    doc = fitz.open(str(pdf_path))
    images = []
    for page_idx in range(doc.page_count):
        for img_info in doc.get_page_images(page_idx, full=True):
            xref = img_info[0]
            images.append((page_idx, xref, img_info[2], img_info[3]))
    seen = set()
    unique = []
    for item in images:
        if item[1] not in seen:
            seen.add(item[1])
            unique.append(item)
    doc.close()
    return unique


def test_extract_images_empty_completes_without_error(tmp_path):
    from extract_images_tool import _ExtractImagesWorker

    src = _copy("plain.pdf", tmp_path)
    out_dir = tmp_path / "images"
    images = _discover_images(src)

    results = {}
    worker = _ExtractImagesWorker(str(src), out_dir, images, "png", "png")
    worker.finished.connect(lambda d, n: results.update({"done": True, "count": n}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out_dir.exists()


def test_extract_images_output_dir_created(tmp_path):
    from extract_images_tool import _ExtractImagesWorker

    src = _copy("multipage.pdf", tmp_path)
    out_dir = tmp_path / "extracted"
    images = _discover_images(src)

    results = {}
    worker = _ExtractImagesWorker(str(src), out_dir, images, "png", "png")
    worker.finished.connect(lambda d, n: results.update({"done": True, "count": n}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out_dir.exists()
    assert results.get("count", 0) == len(images)
