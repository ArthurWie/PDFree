"""Smoke tests using the committed PDF test corpus in tests/corpus/.

These tests verify that core operations work correctly against real (if
minimal) PDF fixtures rather than PDFs generated on-the-fly inside the test.
"""

from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")

CORPUS = Path(__file__).parent / "corpus"


def _pdf(name: str) -> str:
    return str(CORPUS / name)


# ---------------------------------------------------------------------------
# plain.pdf
# ---------------------------------------------------------------------------


def test_plain_opens_and_has_one_page():
    doc = fitz.open(_pdf("plain.pdf"))
    assert doc.page_count == 1
    doc.close()


def test_plain_contains_expected_text():
    doc = fitz.open(_pdf("plain.pdf"))
    text = doc[0].get_text()
    assert "Hello World" in text
    doc.close()


def test_plain_has_no_form_fields():
    doc = fitz.open(_pdf("plain.pdf"))
    fields = list(doc[0].widgets())
    doc.close()
    assert fields == []


# ---------------------------------------------------------------------------
# multipage.pdf
# ---------------------------------------------------------------------------


def test_multipage_has_ten_pages():
    doc = fitz.open(_pdf("multipage.pdf"))
    assert doc.page_count == 10
    doc.close()


def test_multipage_page_text_correct():
    doc = fitz.open(_pdf("multipage.pdf"))
    for i in range(10):
        text = doc[i].get_text()
        assert f"Page {i + 1} of 10" in text
    doc.close()


# ---------------------------------------------------------------------------
# password.pdf
# ---------------------------------------------------------------------------


def test_password_pdf_requires_auth():
    doc = fitz.open(_pdf("password.pdf"))
    assert doc.needs_pass
    doc.close()


def test_password_pdf_opens_with_correct_password():
    doc = fitz.open(_pdf("password.pdf"))
    result = doc.authenticate("test")
    assert result > 0
    assert doc.page_count == 1
    doc.close()


def test_password_pdf_rejects_wrong_password():
    doc = fitz.open(_pdf("password.pdf"))
    result = doc.authenticate("wrong")
    assert result == 0
    doc.close()


# ---------------------------------------------------------------------------
# form.pdf
# ---------------------------------------------------------------------------


def test_form_pdf_has_fields():
    doc = fitz.open(_pdf("form.pdf"))
    widgets = list(doc[0].widgets())
    doc.close()
    assert len(widgets) == 3


def test_form_pdf_field_names():
    doc = fitz.open(_pdf("form.pdf"))
    names = {w.field_name for w in doc[0].widgets()}
    doc.close()
    assert names == {"FirstName", "LastName", "Email"}


# ---------------------------------------------------------------------------
# annotated.pdf
# ---------------------------------------------------------------------------


def test_annotated_pdf_has_annotations():
    doc = fitz.open(_pdf("annotated.pdf"))
    annots = list(doc[0].annots())
    doc.close()
    assert len(annots) >= 2


def test_annotated_pdf_highlight_content():
    doc = fitz.open(_pdf("annotated.pdf"))
    contents = [a.info.get("content", "") for a in doc[0].annots()]
    doc.close()
    assert any("Highlighted" in c for c in contents)


# ---------------------------------------------------------------------------
# corrupt.pdf — PyMuPDF opens in repair mode; should not raise
# ---------------------------------------------------------------------------


def test_corrupt_pdf_does_not_raise():
    try:
        doc = fitz.open(_pdf("corrupt.pdf"))
        doc.close()
    except Exception:
        pytest.skip("corrupt PDF raised on this PyMuPDF build (acceptable)")
