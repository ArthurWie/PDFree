"""Tests for i18n helpers."""

import pytest


def test_tr_returns_string(qapp):
    from i18n import tr

    result = tr("Hello")
    assert isinstance(result, str)


def test_tr_passthrough_without_translation(qapp):
    from i18n import tr

    # No .qm file loaded, so translate() returns the source string unchanged.
    assert tr("View PDF") == "View PDF"


def test_tr_empty_string(qapp):
    from i18n import tr

    assert tr("") == ""


def test_qt_translate_noop_is_identity():
    from i18n import QT_TRANSLATE_NOOP

    assert QT_TRANSLATE_NOOP("PDFree", "Rotate") == "Rotate"
    assert QT_TRANSLATE_NOOP("PDFree", "") == ""
    assert QT_TRANSLATE_NOOP("other", "X") == "X"


def test_qt_translate_noop_does_not_require_qapp():
    # Must be callable at module level before QApplication is created.
    from i18n import QT_TRANSLATE_NOOP

    result = QT_TRANSLATE_NOOP("PDFree", "Merge")
    assert result == "Merge"


def test_categories_titles_are_strings():
    # Verify QT_TRANSLATE_NOOP wrapping in CATEGORIES does not break the values.
    import main

    for cat in main.CATEGORIES:
        assert isinstance(cat["title"], str)
        assert len(cat["title"]) > 0


def test_tool_descriptions_are_strings():
    import main

    for key, val in main.TOOL_DESCRIPTIONS.items():
        assert isinstance(val, str), f"TOOL_DESCRIPTIONS[{key!r}] is not a str"


def test_tab_categories_keys_are_strings():
    import main

    for key in main.TAB_CATEGORIES:
        assert isinstance(key, str)


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication.instance() or QApplication(sys.argv)
    yield app
