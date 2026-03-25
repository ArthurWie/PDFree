"""Tests for bookmarks_tool pure helpers."""

import pytest

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")


def _make_pdf(path: str, pages: int = 5) -> None:
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()
    doc.save(path)
    doc.close()


# ---------------------------------------------------------------------------
# toc_remove
# ---------------------------------------------------------------------------


def test_remove_single_entry():
    from bookmarks_tool import toc_remove

    toc = [[1, "A", 1], [1, "B", 2], [1, "C", 3]]
    result = toc_remove(toc, 1)
    assert result == [[1, "A", 1], [1, "C", 3]]


def test_remove_entry_and_children():
    from bookmarks_tool import toc_remove

    toc = [
        [1, "A", 1],
        [2, "A.1", 2],
        [2, "A.2", 3],
        [1, "B", 4],
    ]
    result = toc_remove(toc, 0)
    assert result == [[1, "B", 4]]


def test_remove_only_removes_children_not_siblings():
    from bookmarks_tool import toc_remove

    toc = [
        [1, "A", 1],
        [2, "A.1", 2],
        [1, "B", 3],
        [2, "B.1", 4],
    ]
    result = toc_remove(toc, 0)
    assert result == [[1, "B", 3], [2, "B.1", 4]]


def test_remove_out_of_bounds_returns_unchanged():
    from bookmarks_tool import toc_remove

    toc = [[1, "A", 1]]
    assert toc_remove(toc, 5) == [[1, "A", 1]]
    assert toc_remove(toc, -1) == [[1, "A", 1]]


def test_remove_last_entry():
    from bookmarks_tool import toc_remove

    toc = [[1, "A", 1], [1, "B", 2]]
    assert toc_remove(toc, 1) == [[1, "A", 1]]


def test_remove_from_empty():
    from bookmarks_tool import toc_remove

    assert toc_remove([], 0) == []


# ---------------------------------------------------------------------------
# toc_move_up
# ---------------------------------------------------------------------------


def test_move_up_first_entry_unchanged():
    from bookmarks_tool import toc_move_up

    toc = [[1, "A", 1], [1, "B", 2]]
    new_toc, new_idx = toc_move_up(toc, 0)
    assert new_toc == toc
    assert new_idx == 0


def test_move_up_second_entry():
    from bookmarks_tool import toc_move_up

    toc = [[1, "A", 1], [1, "B", 2], [1, "C", 3]]
    new_toc, new_idx = toc_move_up(toc, 1)
    assert new_toc == [[1, "B", 2], [1, "A", 1], [1, "C", 3]]
    assert new_idx == 0


def test_move_up_with_children():
    from bookmarks_tool import toc_move_up

    toc = [
        [1, "A", 1],
        [1, "B", 2],
        [2, "B.1", 3],
    ]
    new_toc, new_idx = toc_move_up(toc, 1)
    assert new_toc == [[1, "B", 2], [2, "B.1", 3], [1, "A", 1]]
    assert new_idx == 0


def test_move_up_nested_no_predecessor():
    from bookmarks_tool import toc_move_up

    toc = [[1, "A", 1], [2, "A.1", 2]]
    new_toc, new_idx = toc_move_up(toc, 1)
    # A.1 has no same-level predecessor — stays put
    assert new_toc == toc
    assert new_idx == 1


# ---------------------------------------------------------------------------
# toc_move_down
# ---------------------------------------------------------------------------


def test_move_down_last_entry_unchanged():
    from bookmarks_tool import toc_move_down

    toc = [[1, "A", 1], [1, "B", 2]]
    new_toc, new_idx = toc_move_down(toc, 1)
    assert new_toc == toc
    assert new_idx == 1


def test_move_down_first_entry():
    from bookmarks_tool import toc_move_down

    toc = [[1, "A", 1], [1, "B", 2], [1, "C", 3]]
    new_toc, new_idx = toc_move_down(toc, 0)
    assert new_toc == [[1, "B", 2], [1, "A", 1], [1, "C", 3]]
    assert new_idx == 1


def test_move_down_with_children():
    from bookmarks_tool import toc_move_down

    toc = [
        [1, "A", 1],
        [2, "A.1", 2],
        [1, "B", 3],
    ]
    new_toc, new_idx = toc_move_down(toc, 0)
    assert new_toc == [[1, "B", 3], [1, "A", 1], [2, "A.1", 2]]
    assert new_idx == 1


def test_move_up_then_down_roundtrip():
    from bookmarks_tool import toc_move_up, toc_move_down

    toc = [[1, "A", 1], [1, "B", 2], [1, "C", 3]]
    moved, idx = toc_move_down(toc, 0)
    restored, idx2 = toc_move_up(moved, idx)
    assert restored == toc
    assert idx2 == 0


# ---------------------------------------------------------------------------
# Round-trip via fitz
# ---------------------------------------------------------------------------


def test_roundtrip_set_toc(tmp_path):
    src = str(tmp_path / "src.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src, pages=5)

    toc_in = [
        [1, "Chapter 1", 1],
        [2, "Section 1.1", 2],
        [1, "Chapter 2", 3],
    ]
    doc = fitz.open(src)
    doc.set_toc(toc_in)
    doc.save(dst, garbage=3, deflate=True)
    doc.close()

    doc2 = fitz.open(dst)
    toc_out = doc2.get_toc()
    doc2.close()

    assert toc_out == toc_in


def test_clear_toc(tmp_path):
    src = str(tmp_path / "src.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src, pages=3)

    doc = fitz.open(src)
    doc.set_toc([[1, "Only entry", 1]])
    doc.save(dst)
    doc.close()

    # Now clear it
    doc2 = fitz.open(dst)
    doc2.set_toc([])
    doc2.save(str(tmp_path / "cleared.pdf"), garbage=3)
    doc2.close()

    doc3 = fitz.open(str(tmp_path / "cleared.pdf"))
    assert doc3.get_toc() == []
    doc3.close()
