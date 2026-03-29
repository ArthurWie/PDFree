import sys
import pytest

sys.path.insert(0, ".")

from PySide6.QtWidgets import QApplication, QAbstractItemView, QHeaderView


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    return a


def test_column_count(app):
    from styled_tree import StyledTree

    t = StyledTree()
    assert t._tree.columnCount() == 3


def test_edit_triggers_disabled(app):
    from styled_tree import StyledTree

    t = StyledTree()
    assert t._tree.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers


def test_selection_behavior_rows(app):
    from styled_tree import StyledTree

    t = StyledTree()
    assert t._tree.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectRows


def test_selection_mode_multi(app):
    from styled_tree import StyledTree

    t = StyledTree()
    assert t._tree.selectionMode() == QAbstractItemView.SelectionMode.MultiSelection


def test_header_hidden(app):
    from styled_tree import StyledTree

    t = StyledTree()
    assert t._tree.header().isHidden()


def test_col1_resize_to_contents(app):
    from styled_tree import StyledTree

    t = StyledTree()
    mode = t._tree.header().sectionResizeMode(1)
    assert mode == QHeaderView.ResizeMode.ResizeToContents


def test_col2_stretch(app):
    from styled_tree import StyledTree

    t = StyledTree()
    mode = t._tree.header().sectionResizeMode(2)
    assert mode == QHeaderView.ResizeMode.Stretch
