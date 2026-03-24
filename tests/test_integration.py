"""Integration tests: real PDF in → tool operation → output file verification."""

import os
import sys

import pytest
from PySide6.QtWidgets import QApplication

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")

_app = QApplication.instance() or QApplication(sys.argv)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pdf(path: str, pages: int = 3, text: str = "") -> None:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        if text:
            page.insert_text(fitz.Point(72, 72), f"{text} page {i + 1}", fontsize=12)
    doc.save(path)
    doc.close()


def _page_count(path: str) -> int:
    doc = fitz.open(path)
    n = doc.page_count
    doc.close()
    return n


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


def test_merge_combines_pages(tmp_path):
    from merge_tool import _MergeWorker

    a = str(tmp_path / "a.pdf")
    b = str(tmp_path / "b.pdf")
    out = str(tmp_path / "merged.pdf")
    _make_pdf(a, pages=2)
    _make_pdf(b, pages=3)

    results = {}
    worker = _MergeWorker(
        entries=[{"path": a}, {"path": b}],
        out_path=out,
    )
    worker.finished.connect(lambda p, n: results.update({"done": True, "n": n}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(10000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert os.path.exists(out)
    assert _page_count(out) == 5


def test_merge_preserves_order(tmp_path):
    from merge_tool import _MergeWorker

    a = str(tmp_path / "a.pdf")
    b = str(tmp_path / "b.pdf")
    out = str(tmp_path / "merged.pdf")
    _make_pdf(a, pages=1, text="AAA")
    _make_pdf(b, pages=1, text="BBB")

    worker = _MergeWorker(entries=[{"path": a}, {"path": b}], out_path=out)
    worker.start()
    worker.wait(10000)

    doc = fitz.open(out)
    text_p0 = doc[0].get_text()
    text_p1 = doc[1].get_text()
    doc.close()
    assert "AAA" in text_p0
    assert "BBB" in text_p1


def test_merge_missing_file_emits_failed(tmp_path):
    from merge_tool import _MergeWorker

    out = str(tmp_path / "merged.pdf")
    results = {}
    worker = _MergeWorker(
        entries=[{"path": str(tmp_path / "nonexistent.pdf")}],
        out_path=out,
    )
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(10000)
    _app.processEvents()

    assert "error" in results


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------


def test_split_by_ranges_creates_files(tmp_path):
    from split_tool import _SplitWorker

    src = str(tmp_path / "src.pdf")
    _make_pdf(src, pages=4)

    results = {}
    worker = _SplitWorker(
        mode="ranges",
        pdf_path=src,
        ranges=[(1, 2), (3, 4)],
        page_cuts={},
        output_dir=str(tmp_path),
        filename_template="part%d",
    )
    worker.finished.connect(lambda msg: results.update({"done": msg}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(10000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert (tmp_path / "part1.pdf").exists()
    assert (tmp_path / "part2.pdf").exists()
    assert _page_count(str(tmp_path / "part1.pdf")) == 2
    assert _page_count(str(tmp_path / "part2.pdf")) == 2


def test_split_single_range_all_pages(tmp_path):
    from split_tool import _SplitWorker

    src = str(tmp_path / "src.pdf")
    _make_pdf(src, pages=3)

    results = {}
    worker = _SplitWorker(
        mode="ranges",
        pdf_path=src,
        ranges=[(1, 3)],
        page_cuts={},
        output_dir=str(tmp_path),
        filename_template="all%d",
    )
    worker.finished.connect(lambda msg: results.update({"done": msg}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(10000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert _page_count(str(tmp_path / "all1.pdf")) == 3


# ---------------------------------------------------------------------------
# Compress
# ---------------------------------------------------------------------------


def test_compress_lossless_output_valid(tmp_path):
    from compress_tool import _CompressWorker

    src = str(tmp_path / "src.pdf")
    out = str(tmp_path / "compressed.pdf")
    _make_pdf(src, pages=3)

    results = {}
    worker = _CompressWorker(
        pdf_path=src,
        out_path=out,
        preset={"dpi": None},
    )
    worker.finished.connect(lambda p: results.update({"done": p}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(10000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert os.path.exists(out)
    assert _page_count(out) == 3


def test_compress_lossless_does_not_modify_source(tmp_path):
    from compress_tool import _CompressWorker

    src = str(tmp_path / "src.pdf")
    out = str(tmp_path / "compressed.pdf")
    _make_pdf(src, pages=2)
    before = (tmp_path / "src.pdf").read_bytes()

    worker = _CompressWorker(pdf_path=src, out_path=out, preset={"dpi": None})
    worker.start()
    worker.wait(10000)

    after = (tmp_path / "src.pdf").read_bytes()
    assert before == after


def test_compress_lossy_output_valid(tmp_path):
    from compress_tool import _CompressWorker

    src = str(tmp_path / "src.pdf")
    out = str(tmp_path / "compressed.pdf")
    _make_pdf(src, pages=2)

    results = {}
    worker = _CompressWorker(
        pdf_path=src,
        out_path=out,
        preset={"dpi": 72},
    )
    worker.finished.connect(lambda p: results.update({"done": p}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert os.path.exists(out)
    assert _page_count(out) == 2


# ---------------------------------------------------------------------------
# Watermark
# ---------------------------------------------------------------------------


def test_stamp_watermark_embeds_text(tmp_path):
    from watermark_tool import _stamp_watermark

    src = str(tmp_path / "src.pdf")
    out = str(tmp_path / "watermarked.pdf")
    _make_pdf(src, pages=2)

    doc = fitz.open(src)
    for page in doc:
        _stamp_watermark(page, "CONFIDENTIAL", 36, (0.7, 0.1, 0.1), 0.5, "Center")
    doc.save(out)
    doc.close()

    assert os.path.exists(out)
    assert _page_count(out) == 2


def test_stamp_watermark_diagonal(tmp_path):
    from watermark_tool import _stamp_watermark

    src = str(tmp_path / "src.pdf")
    out = str(tmp_path / "wm.pdf")
    _make_pdf(src, pages=1)

    doc = fitz.open(src)
    _stamp_watermark(doc[0], "DRAFT", 48, (0.5, 0.5, 0.5), 0.3, "Diagonal")
    doc.save(out)
    doc.close()

    doc = fitz.open(out)
    assert doc.page_count == 1
    doc.close()


def test_stamp_watermark_positions(tmp_path):
    from watermark_tool import _stamp_watermark

    src = str(tmp_path / "src.pdf")
    _make_pdf(src, pages=1)

    for pos in ("Top", "Bottom", "Center", "Diagonal"):
        out = str(tmp_path / f"wm_{pos}.pdf")
        doc = fitz.open(src)
        _stamp_watermark(doc[0], "TEST", 24, (0.0, 0.0, 0.0), 1.0, pos)
        doc.save(out)
        doc.close()
        assert os.path.exists(out)
