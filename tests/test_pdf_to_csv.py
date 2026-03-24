"""Tests for pure-logic methods in pdf_to_csv_tool (no Qt required)."""

import pytest

# These are all @staticmethod or @classmethod — importable without a Qt app.
from pdf_to_csv_tool import PDFtoCSVTool


# ---------------------------------------------------------------------------
# _parse_page_range
# ---------------------------------------------------------------------------


def test_parse_all(self=None):
    assert PDFtoCSVTool._parse_page_range("all", 5) == [0, 1, 2, 3, 4]


def test_parse_empty_string():
    assert PDFtoCSVTool._parse_page_range("", 3) == [0, 1, 2]


def test_parse_single_page():
    assert PDFtoCSVTool._parse_page_range("1", 5) == [0]
    assert PDFtoCSVTool._parse_page_range("3", 5) == [2]
    assert PDFtoCSVTool._parse_page_range("5", 5) == [4]


def test_parse_range():
    assert PDFtoCSVTool._parse_page_range("2-4", 5) == [1, 2, 3]


def test_parse_comma_separated():
    assert PDFtoCSVTool._parse_page_range("1,3,5", 5) == [0, 2, 4]


def test_parse_mixed():
    result = PDFtoCSVTool._parse_page_range("1,3-5", 10)
    assert result == [0, 2, 3, 4]


def test_parse_out_of_bounds_page():
    with pytest.raises(ValueError):
        PDFtoCSVTool._parse_page_range("6", 5)


def test_parse_out_of_bounds_range():
    with pytest.raises(ValueError):
        PDFtoCSVTool._parse_page_range("3-8", 5)


def test_parse_inverted_range():
    with pytest.raises(ValueError):
        PDFtoCSVTool._parse_page_range("5-2", 10)


def test_parse_deduplicates():
    result = PDFtoCSVTool._parse_page_range("1-3,2-4", 10)
    assert result == sorted(set(result))
    assert len(result) == len(set(result))


# ---------------------------------------------------------------------------
# _check_column_consistency
# ---------------------------------------------------------------------------


def test_column_consistency_uniform():
    rows = [["a", "b"], ["c", "d"], ["e", "f"]]
    assert PDFtoCSVTool._check_column_consistency(rows) is None


def test_column_consistency_inconsistent():
    rows = [["a", "b"], ["c", "d", "e"]]
    result = PDFtoCSVTool._check_column_consistency(rows)
    assert result is not None
    assert "2" in result
    assert "3" in result


def test_column_consistency_empty():
    assert PDFtoCSVTool._check_column_consistency([]) is None


def test_column_consistency_single_row():
    assert PDFtoCSVTool._check_column_consistency([["a", "b", "c"]]) is None


# ---------------------------------------------------------------------------
# _try_parse_date
# ---------------------------------------------------------------------------


def test_parse_date_iso():
    assert PDFtoCSVTool._try_parse_date("2024-03-15") == "2024-03-15"


def test_parse_date_dmy_slash():
    assert PDFtoCSVTool._try_parse_date("15/03/2024") == "2024-03-15"


def test_parse_date_not_a_date():
    assert PDFtoCSVTool._try_parse_date("hello") is None
    assert PDFtoCSVTool._try_parse_date("") is None
    assert PDFtoCSVTool._try_parse_date("123") is None


def test_parse_date_numeric_string():
    # Numbers that happen to parse as dates should return ISO
    result = PDFtoCSVTool._try_parse_date("01/01/2000")
    assert result == "2000-01-01"


# ---------------------------------------------------------------------------
# _convert_cell_type
# ---------------------------------------------------------------------------


def test_convert_empty_passthrough():
    assert PDFtoCSVTool._convert_cell_type("", True, True) == ""
    assert PDFtoCSVTool._convert_cell_type("  ", True, True) == "  "


def test_convert_integer():
    assert PDFtoCSVTool._convert_cell_type("42", True, False) == "42"


def test_convert_float():
    result = PDFtoCSVTool._convert_cell_type("3.14", True, False)
    assert result == "3.14"


def test_convert_text_passthrough():
    assert PDFtoCSVTool._convert_cell_type("hello", True, True) == "hello"


def test_convert_date_iso():
    result = PDFtoCSVTool._convert_cell_type("2024-03-15", False, True)
    assert result == "2024-03-15"


def test_convert_numbers_disabled():
    assert PDFtoCSVTool._convert_cell_type("42", False, False) == "42"
