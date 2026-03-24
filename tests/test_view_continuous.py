import fitz
from pathlib import Path

CORPUS = Path(__file__).parent / "corpus"
PLAIN_PDF = str(CORPUS / "plain.pdf")
MULTI_PDF = str(CORPUS / "multipage.pdf")


def test_continuous_pane_page_count(qtbot):
    from view_tool import _ContinuousPane

    pane = _ContinuousPane(PLAIN_PDF)
    qtbot.addWidget(pane)
    doc = fitz.open(PLAIN_PDF)
    expected = doc.page_count
    doc.close()
    assert pane.page_count() == expected


def test_continuous_pane_scroll_to_page_does_not_raise(qtbot):
    from view_tool import _ContinuousPane

    pane = _ContinuousPane(MULTI_PDF)
    qtbot.addWidget(pane)
    pane.show()
    qtbot.waitExposed(pane)
    pane.scroll_to_page(0)
    qtbot.wait(50)  # let QTimer.singleShot(0, ...) fire


def test_continuous_pane_current_page_at_top(qtbot):
    from view_tool import _ContinuousPane

    pane = _ContinuousPane(PLAIN_PDF)
    qtbot.addWidget(pane)
    pane.show()
    qtbot.waitExposed(pane)
    assert pane.current_page() == 0


def test_continuous_pane_set_zoom(qtbot):
    from view_tool import _ContinuousPane

    pane = _ContinuousPane(PLAIN_PDF)
    qtbot.addWidget(pane)
    pane.show()
    qtbot.waitExposed(pane)
    pane.set_zoom(1.5)
    assert abs(pane.zoom() - 1.5) < 0.01
