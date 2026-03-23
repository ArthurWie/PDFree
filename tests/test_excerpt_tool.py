"""Tests for excerpt_tool core logic (inline save path, no QFileDialog)."""

import sys

import pytest
from PySide6.QtWidgets import QApplication

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")

_app = QApplication.instance() or QApplication(sys.argv)

CORPUS = __import__("pathlib").Path(__file__).parent / "corpus"


def test_append_to_output_and_save(tmp_path):
    """Build a snippet from plain.pdf and verify _out_doc can be saved."""
    from excerpt_tool import ExcerptTool, Snippet

    src = CORPUS / "plain.pdf"
    doc = fitz.open(str(src))
    page = doc[0]
    rect = page.rect
    # Use the full page as the crop rect
    crop_rect = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y1)
    doc.close()

    tool = ExcerptTool()
    snip = Snippet(
        source_path=str(src),
        page_index=0,
        crop_rect=crop_rect,
        label="test snippet",
    )

    tool._append_to_output(snip)

    assert tool._out_doc.page_count >= 1

    out = tmp_path / "excerpt.pdf"
    tool._out_doc.save(str(out))
    assert out.exists()
    assert out.stat().st_size > 0

    verify = fitz.open(str(out))
    assert verify.page_count >= 1
    verify.close()

    tool.cleanup()


def test_multiple_snippets_accumulate(tmp_path):
    """Multiple captures should add pages as needed."""
    from excerpt_tool import ExcerptTool, Snippet

    src = CORPUS / "multipage.pdf"
    doc = fitz.open(str(src))
    page_count = doc.page_count
    doc.close()

    tool = ExcerptTool()

    for pg_idx in range(min(page_count, 3)):
        d = fitz.open(str(src))
        rect = d[pg_idx].rect
        d.close()
        snip = Snippet(
            source_path=str(src),
            page_index=pg_idx,
            crop_rect=fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y1),
            label=f"page {pg_idx + 1}",
        )
        tool._append_to_output(snip)
        tool._snippets.append(snip)

    assert len(tool._snippets) >= 1
    assert tool._out_doc.page_count >= 1

    out = tmp_path / "multi_excerpt.pdf"
    tool._out_doc.save(str(out))
    assert out.exists()

    tool.cleanup()
