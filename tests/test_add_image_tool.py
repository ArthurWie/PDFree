import shutil
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")
PIL = pytest.importorskip("PIL", reason="Pillow not installed")
from PIL import Image

_app = QApplication.instance() or QApplication(sys.argv)
CORPUS = Path(__file__).parent / "corpus"


def _copy(name, tmp):
    p = tmp / name
    shutil.copy2(CORPUS / name, p)
    return p


def _make_test_image(tmp_path, filename="test.png", size=(50, 50), color=(255, 0, 0)):
    img_path = tmp_path / filename
    img = Image.new("RGB", size, color=color)
    img.save(str(img_path))
    return img_path


def test_add_image_produces_valid_pdf(tmp_path):
    from add_image_tool import _AddImageWorker

    src = _copy("plain.pdf", tmp_path)
    img_path = _make_test_image(tmp_path)
    out = tmp_path / "out_img.pdf"

    doc_tmp = fitz.open(str(src))
    page = doc_tmp[0]
    rect = fitz.Rect(0, 0, page.rect.width, page.rect.height)
    doc_tmp.close()

    results = {}

    worker = _AddImageWorker(
        str(src), str(img_path), page_idx=0, rect=rect, keep_aspect=True, out_path=str(out)
    )
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


def test_add_image_top_left_position(tmp_path):
    from add_image_tool import _AddImageWorker

    src = _copy("plain.pdf", tmp_path)
    img_path = _make_test_image(tmp_path, filename="top_left.png", color=(0, 255, 0))
    out = tmp_path / "out_img_topleft.pdf"

    doc_tmp = fitz.open(str(src))
    page = doc_tmp[0]
    w, h = page.rect.width, page.rect.height
    rect = fitz.Rect(0, 0, w * 0.4, h * 0.3)
    doc_tmp.close()

    results = {}

    worker = _AddImageWorker(
        str(src), str(img_path), page_idx=0, rect=rect, keep_aspect=False, out_path=str(out)
    )
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


def test_add_image_multipage_second_page(tmp_path):
    from add_image_tool import _AddImageWorker

    src = _copy("multipage.pdf", tmp_path)
    img_path = _make_test_image(tmp_path, filename="page2.png", color=(0, 0, 255))
    out = tmp_path / "out_img_page2.pdf"

    doc_tmp = fitz.open(str(src))
    page_count = doc_tmp.page_count
    page = doc_tmp[1] if page_count > 1 else doc_tmp[0]
    w, h = page.rect.width, page.rect.height
    rect = fitz.Rect(w * 0.25, h * 0.35, w * 0.75, h * 0.65)
    page_idx = 1 if page_count > 1 else 0
    doc_tmp.close()

    results = {}

    worker = _AddImageWorker(
        str(src), str(img_path), page_idx=page_idx, rect=rect, keep_aspect=True, out_path=str(out)
    )
    worker.finished.connect(lambda *a: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()
    doc = fitz.open(str(out))
    assert doc.page_count == page_count
    doc.close()
