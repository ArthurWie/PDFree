"""Tests for clickable link detection and routing in ViewTool."""
import sys
import pytest
from pathlib import Path


def _get_or_create_app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="module")
def qapp():
    return _get_or_create_app()


@pytest.fixture
def pdf_with_uri_link(tmp_path):
    """Create a PDF with a URI link on page 0."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    link = {
        "kind": fitz.LINK_URI,
        "from": fitz.Rect(10, 10, 100, 30),
        "uri": "https://example.com",
    }
    page.insert_link(link)
    p = tmp_path / "links.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


@pytest.fixture
def pdf_with_goto_link(tmp_path):
    """Create a 2-page PDF with a GOTO link on page 0 pointing to page 1."""
    import fitz
    doc = fitz.open()
    doc.new_page(width=200, height=200)
    doc.new_page(width=200, height=200)
    link = {
        "kind": fitz.LINK_GOTO,
        "from": fitz.Rect(10, 10, 100, 30),
        "page": 1,
    }
    doc[0].insert_link(link)
    p = tmp_path / "goto.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


def test_link_cache_populated_after_load(qapp, pdf_with_uri_link):
    """After opening a PDF, _link_cache should be populated for page 0."""
    from view_tool import ViewTool
    import fitz
    vt = ViewTool()
    vt.open_file(pdf_with_uri_link)
    pane = vt.active_pane
    pane._update_link_cache()
    assert len(pane._link_cache) >= 1
    rect, link = pane._link_cache[0]
    assert link["kind"] == fitz.LINK_URI
    vt.cleanup()


def test_uri_link_fires_open_url(qapp, pdf_with_uri_link, monkeypatch):
    """Clicking on a URI link calls QDesktopServices.openUrl."""
    from view_tool import ViewTool
    from PySide6.QtGui import QDesktopServices
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    vt = ViewTool()
    vt.open_file(pdf_with_uri_link)
    pane = vt.active_pane
    pane._update_link_cache()
    pane._fire_link(pane._link_cache[0][1])
    assert len(opened) == 1
    assert "example.com" in opened[0]
    vt.cleanup()


def test_goto_link_navigates(qapp, pdf_with_goto_link):
    """Clicking on a GOTO link navigates to the target page."""
    from view_tool import ViewTool
    import fitz
    vt = ViewTool()
    vt.open_file(pdf_with_goto_link)
    pane = vt.active_pane
    pane._update_link_cache()
    goto_link = next(
        l for _, l in pane._link_cache if l["kind"] == fitz.LINK_GOTO
    )
    pane._fire_link(goto_link)
    assert pane.active_page == 1
    vt.cleanup()


def test_unknown_link_kind_ignored(qapp, pdf_with_uri_link, monkeypatch, caplog):
    """Unknown link kinds are logged and ignored (no exception)."""
    import logging
    from view_tool import ViewTool
    from PySide6.QtGui import QDesktopServices
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: None)
    vt = ViewTool()
    vt.open_file(pdf_with_uri_link)
    pane = vt.active_pane
    with caplog.at_level(logging.DEBUG):
        pane._fire_link({"kind": 999, "uri": ""})
    assert "unhandled link" in caplog.text
    vt.cleanup()
