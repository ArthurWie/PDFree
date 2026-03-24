import sys

import pytest
from PySide6.QtWidgets import QApplication

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")
PIL = pytest.importorskip("PIL", reason="Pillow not installed")
from PIL import Image

_app = QApplication.instance() or QApplication(sys.argv)


def _make_png(tmp_path, name="test.png", size=(100, 100), color=(0, 128, 255)):
    img = Image.new("RGB", size, color=color)
    p = tmp_path / name
    img.save(str(p))
    return p


def test_img_to_pdf_single_image(tmp_path):
    from img_to_pdf_tool import _ImgToPdfWorker

    img_path = _make_png(tmp_path)
    out = tmp_path / "out.pdf"
    results = {}

    entries = [{"path": str(img_path)}]
    worker = _ImgToPdfWorker(entries, str(out), (595, 842), 18)
    worker.finished.connect(lambda p: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()

    doc = fitz.open(str(out))
    assert doc.page_count == 1
    doc.close()


def test_img_to_pdf_multiple_images(tmp_path):
    from img_to_pdf_tool import _ImgToPdfWorker

    img1 = _make_png(tmp_path, "img1.png", color=(255, 0, 0))
    img2 = _make_png(tmp_path, "img2.png", color=(0, 255, 0))
    img3 = _make_png(tmp_path, "img3.png", color=(0, 0, 255))
    out = tmp_path / "out_multi.pdf"
    results = {}

    entries = [{"path": str(img1)}, {"path": str(img2)}, {"path": str(img3)}]
    worker = _ImgToPdfWorker(entries, str(out), (595, 842), 0)
    worker.finished.connect(lambda p: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()

    doc = fitz.open(str(out))
    assert doc.page_count == 3
    doc.close()


def test_img_to_pdf_fit_to_image(tmp_path):
    from img_to_pdf_tool import _ImgToPdfWorker

    img_path = _make_png(tmp_path, "fit.png", size=(200, 300))
    out = tmp_path / "out_fit.pdf"
    results = {}

    entries = [{"path": str(img_path)}]
    # page_size=None triggers "Fit to Image" mode
    worker = _ImgToPdfWorker(entries, str(out), None, 0)
    worker.finished.connect(lambda p: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()

    doc = fitz.open(str(out))
    assert doc.page_count == 1
    doc.close()
