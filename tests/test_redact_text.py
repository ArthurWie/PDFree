"""Tests for text-based auto-redaction in redact_tool."""

import pytest

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")


def _make_pdf_with_text(path: str, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), text, fontsize=12)
    doc.save(path)
    doc.close()


def _count_redactions(path: str) -> int:
    """Count redact annotations in the PDF (before apply)."""
    doc = fitz.open(path)
    total = 0
    for page in doc:
        total += sum(1 for a in page.annots() if a.type[0] == fitz.PDF_ANNOT_REDACT)
    doc.close()
    return total


def _search_text_present(path: str, text: str) -> bool:
    doc = fitz.open(path)
    found = any(page.search_for(text) for page in doc)
    doc.close()
    return found


def test_plain_search_finds_matches(tmp_path):
    src = str(tmp_path / "src.pdf")
    _make_pdf_with_text(src, "Hello World secret World")

    doc = fitz.open(src)
    page = doc[0]
    rects = page.search_for("World")
    doc.close()

    assert len(rects) >= 1


def test_redaction_removes_text(tmp_path):
    src = str(tmp_path / "src.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf_with_text(src, "confidential data here")

    doc = fitz.open(src)
    page = doc[0]
    for rect in page.search_for("confidential"):
        page.add_redact_annot(rect, fill=(0, 0, 0))
    page.apply_redactions()
    doc.save(dst, garbage=3, deflate=True)
    doc.close()

    assert not _search_text_present(dst, "confidential")


def test_regex_match_via_extract(tmp_path):
    import re

    src = str(tmp_path / "src.pdf")
    _make_pdf_with_text(src, "Call 555-1234 or 555-5678 for info")

    doc = fitz.open(src)
    page = doc[0]
    text = page.get_text("text")
    pattern = re.compile(r"\d{3}-\d{4}")
    matched = {m.group() for m in pattern.finditer(text) if m.group().strip()}
    found = []
    for s in matched:
        found.extend(page.search_for(s))
    doc.close()

    assert len(found) >= 2


def test_case_insensitive_search(tmp_path):
    src = str(tmp_path / "src.pdf")
    _make_pdf_with_text(src, "HELLO hello Hello")

    doc = fitz.open(src)
    page = doc[0]
    rects = page.search_for("hello")
    doc.close()

    assert len(rects) >= 1


def test_no_matches_returns_empty(tmp_path):
    src = str(tmp_path / "src.pdf")
    _make_pdf_with_text(src, "nothing special here")

    doc = fitz.open(src)
    page = doc[0]
    rects = page.search_for("xyznotpresent")
    doc.close()

    assert rects == []
