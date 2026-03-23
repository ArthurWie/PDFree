"""Worker tests for split_tool._SplitWorker."""

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


def test_split_by_ranges_produces_output(tmp_path):
    from split_tool import _SplitWorker

    src = _copy("multipage.pdf", tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    doc = fitz.open(str(src))
    total = doc.page_count
    doc.close()

    results = {}
    worker = _SplitWorker(
        "ranges",
        str(src),
        ranges=[(1, total)],
        page_cuts={},
        output_dir=str(out_dir),
        filename_template="",
    )
    worker.finished.connect(lambda msg: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    files = list(out_dir.glob("*.pdf"))
    assert len(files) >= 1
    for f in files:
        d = fitz.open(str(f))
        assert d.page_count > 0
        d.close()


def test_split_two_ranges_produces_two_files(tmp_path):
    from split_tool import _SplitWorker

    src = _copy("multipage.pdf", tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    doc = fitz.open(str(src))
    total = doc.page_count
    doc.close()

    mid = max(1, total // 2)
    results = {}
    worker = _SplitWorker(
        "ranges",
        str(src),
        ranges=[(1, mid), (mid + 1, total)],
        page_cuts={},
        output_dir=str(out_dir),
        filename_template="",
    )
    worker.finished.connect(lambda msg: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    files = sorted(out_dir.glob("*.pdf"))
    assert len(files) == 2
    for f in files:
        d = fitz.open(str(f))
        assert d.page_count >= 1
        d.close()
