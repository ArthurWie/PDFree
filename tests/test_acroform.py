"""Tests for AcroForm list box and push button widget support."""

import pytest

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")


def _make_listbox_pdf(path: str) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    w = fitz.Widget()
    w.field_type = fitz.PDF_WIDGET_TYPE_LISTBOX
    w.field_name = "MyList"
    w.choice_values = ["Option A", "Option B", "Option C"]
    w.rect = fitz.Rect(72, 72, 300, 150)
    w.field_value = "Option A"
    page.add_widget(w)
    doc.save(path)
    doc.close()


def _make_pushbutton_pdf(path: str) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    w = fitz.Widget()
    w.field_type = fitz.PDF_WIDGET_TYPE_BUTTON
    w.field_flags = fitz.PDF_BTN_FIELD_IS_PUSHBUTTON
    w.field_name = "MyButton"
    w.rect = fitz.Rect(72, 200, 200, 230)
    page.add_widget(w)
    doc.save(path)
    doc.close()


def test_listbox_pdf_has_listbox_widget(tmp_path):
    src = str(tmp_path / "listbox.pdf")
    _make_listbox_pdf(src)
    doc = fitz.open(src)
    widgets = list(doc[0].widgets())
    doc.close()
    assert any(w.field_type == fitz.PDF_WIDGET_TYPE_LISTBOX for w in widgets)


def test_listbox_choice_values(tmp_path):
    src = str(tmp_path / "listbox.pdf")
    _make_listbox_pdf(src)
    doc = fitz.open(src)
    widgets = list(doc[0].widgets())
    doc.close()
    lb = next(w for w in widgets if w.field_type == fitz.PDF_WIDGET_TYPE_LISTBOX)
    assert lb.choice_values == ["Option A", "Option B", "Option C"]


def test_pushbutton_pdf_has_button_widget(tmp_path):
    src = str(tmp_path / "pushbutton.pdf")
    _make_pushbutton_pdf(src)
    doc = fitz.open(src)
    widgets = list(doc[0].widgets())
    doc.close()
    assert any(w.field_type == fitz.PDF_WIDGET_TYPE_BUTTON for w in widgets)


def test_listbox_field_value_settable(tmp_path):
    src = str(tmp_path / "listbox.pdf")
    _make_listbox_pdf(src)
    doc = fitz.open(src)
    page = doc[0]
    for w in page.widgets():
        if w.field_type == fitz.PDF_WIDGET_TYPE_LISTBOX:
            w.field_value = "Option B"
            w.update()
    doc.close()


def test_widget_types_are_distinct():
    assert fitz.PDF_WIDGET_TYPE_LISTBOX != fitz.PDF_WIDGET_TYPE_COMBOBOX
    assert fitz.PDF_WIDGET_TYPE_LISTBOX != fitz.PDF_WIDGET_TYPE_BUTTON
    assert fitz.PDF_WIDGET_TYPE_COMBOBOX != fitz.PDF_WIDGET_TYPE_BUTTON
