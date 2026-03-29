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


from PySide6.QtCore import Qt


def test_populate_adds_top_level_items(app):
    from styled_tree import StyledTree, _NodeData

    t = StyledTree()
    t.populate(
        [
            _NodeData(label="Root", is_folder=True, children=[]),
        ]
    )
    assert t._tree.topLevelItemCount() == 1


def test_folder_has_children(app):
    from styled_tree import StyledTree, _NodeData

    t = StyledTree()
    t.populate(
        [
            _NodeData(
                label="Root",
                is_folder=True,
                children=[
                    _NodeData(
                        label="child.txt", is_folder=False, page=1, raw_label="1"
                    ),
                ],
            ),
        ]
    )
    root_item = t._tree.topLevelItem(0)
    assert root_item.childCount() == 1


def test_leaf_node_has_checkbox(app):
    from styled_tree import StyledTree, _NodeData

    t = StyledTree()
    t.populate(
        [
            _NodeData(
                label="Root",
                is_folder=True,
                children=[
                    _NodeData(label="file.txt", is_folder=False, page=5, raw_label="v"),
                ],
            ),
        ]
    )
    leaf = t._tree.topLevelItem(0).child(0)
    assert leaf.flags() & Qt.ItemFlag.ItemIsUserCheckable


def test_folder_node_has_no_checkbox(app):
    from styled_tree import StyledTree, _NodeData

    t = StyledTree()
    t.populate(
        [
            _NodeData(label="Root", is_folder=True, children=[]),
        ]
    )
    folder_item = t._tree.topLevelItem(0)
    assert not (folder_item.flags() & Qt.ItemFlag.ItemIsUserCheckable)


def test_leaf_col1_shows_page_number(app):
    from styled_tree import StyledTree, _NodeData

    t = StyledTree()
    t.populate(
        [
            _NodeData(
                label="Root",
                is_folder=True,
                children=[
                    _NodeData(label="file.txt", is_folder=False, page=7, raw_label="7"),
                ],
            ),
        ]
    )
    leaf = t._tree.topLevelItem(0).child(0)
    assert "7" in leaf.text(1)
