import sys
import fitz
from pathlib import Path
import pytest

CORPUS = Path(__file__).parent / "corpus"
PLAIN_PDF = str(CORPUS / "plain.pdf")
MULTI_PDF = str(CORPUS / "multipage.pdf")


def _get_or_create_app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="module")
def qapp():
    return _get_or_create_app()


def test_continuous_pane_page_count(qapp):
    from view_tool import _ContinuousPane

    pane = _ContinuousPane(PLAIN_PDF)
    doc = fitz.open(PLAIN_PDF)
    expected = doc.page_count
    doc.close()
    assert pane.page_count() == expected
    pane.close()


def test_continuous_pane_scroll_to_page_does_not_raise(qapp):
    from view_tool import _ContinuousPane

    pane = _ContinuousPane(MULTI_PDF)
    pane.show()
    pane.scroll_to_page(0)
    pane.close()


def test_continuous_pane_current_page_at_top(qapp):
    from view_tool import _ContinuousPane

    pane = _ContinuousPane(PLAIN_PDF)
    pane.show()
    assert pane.current_page() == 0
    pane.close()


def test_continuous_pane_set_zoom(qapp):
    from view_tool import _ContinuousPane

    pane = _ContinuousPane(PLAIN_PDF)
    pane.show()
    pane.set_zoom(1.5)
    assert abs(pane.zoom() - 1.5) < 0.01
    pane.close()
