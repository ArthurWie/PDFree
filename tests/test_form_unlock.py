"""Tests for form_unlock_tool.unlock_form_fields."""

import os

import pytest

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")
pytest.importorskip("pypdf", reason="pypdf not installed")


def _make_pdf_with_readonly_field(path: str) -> None:
    """Create a single-page PDF with one read-only text field."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    widget = fitz.Widget()
    widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    widget.field_name = "Name"
    widget.rect = fitz.Rect(72, 72, 300, 100)
    widget.field_value = "locked"
    # Set the ReadOnly flag (bit 0 = value 1)
    widget.field_flags = 1
    page.add_widget(widget)
    doc.save(path)
    doc.close()


def _make_plain_pdf(path: str) -> None:
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(path)
    doc.close()


def test_unlock_removes_readonly_flag(tmp_path):
    from form_unlock_tool import unlock_form_fields

    src = str(tmp_path / "locked.pdf")
    dst = str(tmp_path / "unlocked.pdf")
    _make_pdf_with_readonly_field(src)

    n = unlock_form_fields(src, dst)
    assert n >= 1
    assert os.path.exists(dst)


def test_unlock_output_is_valid_pdf(tmp_path):
    from form_unlock_tool import unlock_form_fields

    src = str(tmp_path / "locked.pdf")
    dst = str(tmp_path / "unlocked.pdf")
    _make_pdf_with_readonly_field(src)
    unlock_form_fields(src, dst)

    doc = fitz.open(dst)
    assert doc.page_count == 1
    doc.close()


def test_unlock_pdf_with_no_fields_returns_zero(tmp_path):
    from form_unlock_tool import unlock_form_fields

    src = str(tmp_path / "plain.pdf")
    dst = str(tmp_path / "out.pdf")
    _make_plain_pdf(src)

    n = unlock_form_fields(src, dst)
    assert n == 0
    assert os.path.exists(dst)


def test_unlock_does_not_modify_source(tmp_path):
    from form_unlock_tool import unlock_form_fields

    src = str(tmp_path / "locked.pdf")
    dst = str(tmp_path / "unlocked.pdf")
    _make_pdf_with_readonly_field(src)
    before = (tmp_path / "locked.pdf").read_bytes()

    unlock_form_fields(src, dst)

    after = (tmp_path / "locked.pdf").read_bytes()
    assert before == after


def test_unlock_missing_src_raises(tmp_path):
    from form_unlock_tool import unlock_form_fields

    with pytest.raises(Exception):
        unlock_form_fields(
            str(tmp_path / "nonexistent.pdf"),
            str(tmp_path / "out.pdf"),
        )
