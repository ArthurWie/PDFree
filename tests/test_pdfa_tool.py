"""Tests for pdfa_tool pure helper."""

import pytest

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")


def _make_pdf(path: str, pages: int = 3) -> None:
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()
    doc.save(path)
    doc.close()


# ---------------------------------------------------------------------------
# convert_to_pdfa
# ---------------------------------------------------------------------------


def test_output_file_created(tmp_path):
    from pdfa_tool import convert_to_pdfa

    src = str(tmp_path / "src.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src)
    convert_to_pdfa(src, dst, part="1", conformance="B")
    assert (tmp_path / "dst.pdf").exists()


def test_xmp_contains_pdfa_declaration(tmp_path):
    from pdfa_tool import convert_to_pdfa

    src = str(tmp_path / "src.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src)
    convert_to_pdfa(src, dst, part="2", conformance="B")

    doc = fitz.open(dst)
    xmp = doc.get_xml_metadata()
    doc.close()
    assert "pdfaid:part" in xmp
    assert ">2<" in xmp
    assert ">B<" in xmp


def test_xmp_part1(tmp_path):
    from pdfa_tool import convert_to_pdfa

    src = str(tmp_path / "src.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src)
    convert_to_pdfa(src, dst, part="1", conformance="B")

    doc = fitz.open(dst)
    xmp = doc.get_xml_metadata()
    doc.close()
    assert ">1<" in xmp


def test_xmp_part3(tmp_path):
    from pdfa_tool import convert_to_pdfa

    src = str(tmp_path / "src.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src)
    convert_to_pdfa(src, dst, part="3", conformance="B")

    doc = fitz.open(dst)
    xmp = doc.get_xml_metadata()
    doc.close()
    assert ">3<" in xmp


def test_page_count_preserved(tmp_path):
    from pdfa_tool import convert_to_pdfa

    src = str(tmp_path / "src.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src, pages=5)
    convert_to_pdfa(src, dst, part="1", conformance="B")

    doc = fitz.open(dst)
    count = doc.page_count
    doc.close()
    assert count == 5


def test_src_file_not_modified(tmp_path):
    from pdfa_tool import convert_to_pdfa

    src = str(tmp_path / "src.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src)
    src_bytes_before = (tmp_path / "src.pdf").read_bytes()
    convert_to_pdfa(src, dst, part="1", conformance="B")
    src_bytes_after = (tmp_path / "src.pdf").read_bytes()
    assert src_bytes_before == src_bytes_after


def test_missing_src_raises(tmp_path):
    from pdfa_tool import convert_to_pdfa

    with pytest.raises(Exception):
        convert_to_pdfa(
            str(tmp_path / "nonexistent.pdf"),
            str(tmp_path / "dst.pdf"),
            part="1",
            conformance="B",
        )


def test_sanitise_flags_do_not_crash(tmp_path):
    from pdfa_tool import convert_to_pdfa

    src = str(tmp_path / "src.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src)
    # All sanitise flags off should still produce a valid file
    convert_to_pdfa(
        src,
        dst,
        part="2",
        conformance="B",
        remove_js=False,
        remove_embedded=False,
        remove_hidden_text=False,
        remove_thumbnails=False,
    )
    doc = fitz.open(dst)
    assert doc.page_count == 3
    doc.close()


# ---------------------------------------------------------------------------
# _run_verapdf
# ---------------------------------------------------------------------------


def test_verapdf_not_installed_returns_available_false(monkeypatch):
    import shutil
    from pdfa_tool import _run_verapdf

    monkeypatch.setattr(shutil, "which", lambda _: None)
    result = _run_verapdf("any.pdf")
    assert result["available"] is False


def test_verapdf_result_has_expected_keys(monkeypatch):
    import shutil
    from pdfa_tool import _run_verapdf

    monkeypatch.setattr(shutil, "which", lambda _: None)
    result = _run_verapdf("any.pdf")
    assert "available" in result
