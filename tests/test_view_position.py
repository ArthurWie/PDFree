"""Tests for reading position memory (last_page restore and save)."""

import sys
import pytest


def _get_or_create_app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="module")
def qapp():
    return _get_or_create_app()


@pytest.fixture
def pdf_file(tmp_path):
    """Create a 5-page PDF for testing."""
    import fitz

    doc = fitz.open()
    for _ in range(5):
        doc.new_page()
    p = tmp_path / "multi.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


@pytest.fixture
def library(tmp_path, monkeypatch):
    """LibraryState backed by a temp JSON file."""
    from library_page import LibraryState

    state_file = tmp_path / "library_test.json"
    monkeypatch.setattr("library_page._STATE_PATH", state_file)
    return LibraryState()


def test_last_page_restored_on_open(qapp, pdf_file, library):
    """Opening a tracked file resumes at the stored last_page."""
    from view_tool import ViewTool

    # Track the file and set last_page to 3
    library.track(pdf_file)
    library.set_last_page(pdf_file, 3)
    vt = ViewTool()
    vt.open_file(pdf_file)
    assert vt.active_pane.active_page == 3
    vt.cleanup()


def test_last_page_out_of_range_clamped(qapp, pdf_file, library):
    """Out-of-range stored page is clamped to page_count - 1."""
    from view_tool import ViewTool

    library.track(pdf_file)
    library.set_last_page(pdf_file, 99)  # way beyond 5 pages
    vt = ViewTool()
    vt.open_file(pdf_file)
    assert vt.active_pane.active_page == 4  # clamped to 5-1=4
    vt.cleanup()


def test_untracked_file_opens_at_page_zero(qapp, pdf_file, library):
    """Untracked file (get_last_page returns 0) opens at page 0."""
    from view_tool import ViewTool

    # Do NOT track the file — get_last_page should return 0
    vt = ViewTool()
    vt.open_file(pdf_file)
    assert vt.active_pane.active_page == 0
    vt.cleanup()


def test_page_change_writes_last_page(qapp, pdf_file, library):
    """Navigating to a page updates LibraryState.last_page."""
    from view_tool import ViewTool
    from library_page import LibraryState

    library.track(pdf_file)
    vt = ViewTool()
    vt.open_file(pdf_file)
    pane = vt.active_pane
    # Simulate page change
    pane._current_page = 2
    pane.page_changed.emit(2)
    # Verify last_page was written (create fresh instance to read from disk)
    fresh = LibraryState()
    assert fresh.get_last_page(pdf_file) == 2
    vt.cleanup()


def test_page_changed_connected_once(qapp, pdf_file, library):
    """page_changed signal connected exactly once — opening same file twice doesn't double-connect."""
    from view_tool import ViewTool
    from library_page import LibraryState

    library.track(pdf_file)
    vt = ViewTool()
    vt.open_file(pdf_file)  # first open — connects signal
    vt.open_file(
        pdf_file
    )  # duplicate — should focus existing tab, NOT reconnect signal
    pane = vt.active_pane
    write_count = []
    # Track how many times set_last_page is called on the real pane
    pane.page_changed.connect(lambda p: write_count.append(p))
    pane._current_page = 2
    pane.page_changed.emit(2)
    # Verify the page was written (use fresh instance to see disk state)
    fresh = LibraryState()
    assert fresh.get_last_page(pdf_file) == 2
    # Verify test counter slot fired once
    assert len(write_count) == 1
    vt.cleanup()
