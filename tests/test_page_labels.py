"""Tests for page_labels_tool pure helpers."""

import pytest

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")


def _make_pdf(path: str, pages: int = 5) -> None:
    doc = fitz.open()
    for i in range(pages):
        doc.new_page()
    doc.save(path)
    doc.close()


# ---------------------------------------------------------------------------
# _format_num
# ---------------------------------------------------------------------------


def test_format_arabic():
    from page_labels_tool import _format_num

    assert _format_num(1, "D") == "1"
    assert _format_num(42, "D") == "42"


def test_format_roman_lower():
    from page_labels_tool import _format_num

    assert _format_num(1, "r") == "i"
    assert _format_num(4, "r") == "iv"
    assert _format_num(9, "r") == "ix"
    assert _format_num(14, "r") == "xiv"


def test_format_roman_upper():
    from page_labels_tool import _format_num

    assert _format_num(1, "R") == "I"
    assert _format_num(10, "R") == "X"
    assert _format_num(40, "R") == "XL"


def test_format_alpha_lower():
    from page_labels_tool import _format_num

    assert _format_num(1, "a") == "a"
    assert _format_num(26, "a") == "z"
    assert _format_num(27, "a") == "aa"


def test_format_alpha_upper():
    from page_labels_tool import _format_num

    assert _format_num(1, "A") == "A"
    assert _format_num(26, "A") == "Z"
    assert _format_num(27, "A") == "AA"


def test_format_none_style():
    from page_labels_tool import _format_num

    assert _format_num(5, "") == ""


# ---------------------------------------------------------------------------
# compute_labels
# ---------------------------------------------------------------------------


def test_compute_labels_empty_ranges():
    from page_labels_tool import compute_labels

    # No ranges → default sequential numbers
    result = compute_labels([], 4)
    assert result == ["1", "2", "3", "4"]


def test_compute_labels_single_arabic():
    from page_labels_tool import compute_labels

    ranges = [{"startpage": 0, "style": "D", "prefix": "", "firstpagenum": 1}]
    result = compute_labels(ranges, 3)
    assert result == ["1", "2", "3"]


def test_compute_labels_roman_then_arabic():
    from page_labels_tool import compute_labels

    ranges = [
        {"startpage": 0, "style": "r", "prefix": "", "firstpagenum": 1},
        {"startpage": 2, "style": "D", "prefix": "", "firstpagenum": 1},
    ]
    result = compute_labels(ranges, 5)
    assert result == ["i", "ii", "1", "2", "3"]


def test_compute_labels_with_prefix():
    from page_labels_tool import compute_labels

    ranges = [{"startpage": 0, "style": "D", "prefix": "A-", "firstpagenum": 1}]
    result = compute_labels(ranges, 3)
    assert result == ["A-1", "A-2", "A-3"]


def test_compute_labels_custom_start():
    from page_labels_tool import compute_labels

    ranges = [{"startpage": 0, "style": "D", "prefix": "", "firstpagenum": 5}]
    result = compute_labels(ranges, 3)
    assert result == ["5", "6", "7"]


def test_compute_labels_unsorted_ranges():
    from page_labels_tool import compute_labels

    # Ranges given out of order should still work
    ranges = [
        {"startpage": 3, "style": "D", "prefix": "", "firstpagenum": 1},
        {"startpage": 0, "style": "r", "prefix": "", "firstpagenum": 1},
    ]
    result = compute_labels(ranges, 5)
    assert result == ["i", "ii", "iii", "1", "2"]


def test_compute_labels_no_label_style():
    from page_labels_tool import compute_labels

    ranges = [{"startpage": 0, "style": "", "prefix": "", "firstpagenum": 1}]
    result = compute_labels(ranges, 3)
    assert result == ["", "", ""]


# ---------------------------------------------------------------------------
# Round-trip via fitz
# ---------------------------------------------------------------------------


def test_roundtrip_set_and_get_labels(tmp_path):
    from page_labels_tool import compute_labels

    src = str(tmp_path / "src.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src, pages=5)

    ranges = [
        {"startpage": 0, "style": "r", "prefix": "", "firstpagenum": 1},
        {"startpage": 3, "style": "D", "prefix": "", "firstpagenum": 1},
    ]

    doc = fitz.open(src)
    doc.set_page_labels(ranges)
    doc.save(dst, garbage=3, deflate=True)
    doc.close()

    # Verify via fitz
    doc2 = fitz.open(dst)
    actual = [doc2[i].get_label() for i in range(5)]
    doc2.close()

    assert actual == ["i", "ii", "iii", "1", "2"]

    # Also verify our compute_labels matches
    assert compute_labels(ranges, 5) == ["i", "ii", "iii", "1", "2"]
