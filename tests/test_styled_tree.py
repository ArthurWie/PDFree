import sys
import pytest

sys.path.insert(0, ".")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
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


def test_footer_default_text(app):
    from styled_tree import StyledTree

    t = StyledTree()
    assert "No rows selected" in t._footer._left.text()


def test_footer_updates_on_leaf_check(app):
    from styled_tree import StyledTree, _NodeData

    t = StyledTree()
    t.populate(
        [
            _NodeData(
                label="Root",
                is_folder=True,
                children=[
                    _NodeData(label="file.txt", is_folder=False, page=1, raw_label="1"),
                ],
            ),
        ]
    )
    leaf = t._tree.topLevelItem(0).child(0)
    leaf.setCheckState(0, Qt.CheckState.Checked)
    assert "1 row selected" in t._footer._left.text()


def test_footer_multi_count(app):
    from styled_tree import StyledTree, _NodeData

    t = StyledTree()
    t.populate(
        [
            _NodeData(
                label="Root",
                is_folder=True,
                children=[
                    _NodeData(label="a.txt", is_folder=False, page=1, raw_label="1"),
                    _NodeData(label="b.txt", is_folder=False, page=2, raw_label="2"),
                ],
            ),
        ]
    )
    t._tree.topLevelItem(0).child(0).setCheckState(0, Qt.CheckState.Checked)
    t._tree.topLevelItem(0).child(1).setCheckState(0, Qt.CheckState.Checked)
    assert "2 rows selected" in t._footer._left.text()


def test_footer_unchecking_decrements(app):
    from styled_tree import StyledTree, _NodeData

    t = StyledTree()
    t.populate(
        [
            _NodeData(
                label="Root",
                is_folder=True,
                children=[
                    _NodeData(label="a.txt", is_folder=False, page=1, raw_label="1"),
                ],
            ),
        ]
    )
    leaf = t._tree.topLevelItem(0).child(0)
    leaf.setCheckState(0, Qt.CheckState.Checked)
    assert "1 row selected" in t._footer._left.text()  # verify increment happened first
    leaf.setCheckState(0, Qt.CheckState.Unchecked)
    assert "No rows selected" in t._footer._left.text()


def test_depth0_folder_color_is_g800(app):
    from styled_tree import StyledTree, _NodeData
    from colors import G800

    t = StyledTree()
    t.populate([_NodeData(label="Root", is_folder=True, children=[])])
    item = t._tree.topLevelItem(0)
    assert item.foreground(2).color() == QColor(G800)


def test_depth2_folder_color_is_orange_rust(app):
    from styled_tree import StyledTree, _NodeData

    t = StyledTree()
    t.populate(
        [
            _NodeData(
                label="Root",
                is_folder=True,
                children=[
                    _NodeData(
                        label="Child",
                        is_folder=True,
                        children=[
                            _NodeData(label="Deep", is_folder=True, children=[]),
                        ],
                    ),
                ],
            )
        ]
    )
    deep = t._tree.topLevelItem(0).child(0).child(0)
    assert deep.foreground(2).color() == QColor("#C2410C")


def test_roman_leaf_label_is_teal(app):
    from styled_tree import StyledTree, _NodeData
    from colors import TEAL

    t = StyledTree()
    t.populate(
        [
            _NodeData(
                label="Root",
                is_folder=True,
                children=[
                    _NodeData(label="file", is_folder=False, page=1, raw_label="iv"),
                ],
            )
        ]
    )
    leaf = t._tree.topLevelItem(0).child(0)
    assert leaf.foreground(2).color() == QColor(TEAL)


def test_numeric_leaf_label_is_g700(app):
    from styled_tree import StyledTree, _NodeData
    from colors import G700

    t = StyledTree()
    t.populate(
        [
            _NodeData(
                label="Root",
                is_folder=True,
                children=[
                    _NodeData(label="file", is_folder=False, page=1, raw_label="5"),
                ],
            )
        ]
    )
    leaf = t._tree.topLevelItem(0).child(0)
    assert leaf.foreground(2).color() == QColor(G700)


def test_folder_name_is_bold(app):
    from styled_tree import StyledTree, _NodeData

    t = StyledTree()
    t.populate([_NodeData(label="Root", is_folder=True, children=[])])
    item = t._tree.topLevelItem(0)
    assert item.font(2).bold()


def test_selection_changed_emits_page_numbers(app):
    from styled_tree import StyledTree, _NodeData

    emitted = []
    t = StyledTree()
    t.selection_changed.connect(emitted.append)
    t.populate(
        [
            _NodeData(
                label="Root",
                is_folder=True,
                children=[
                    _NodeData(label="file.txt", is_folder=False, page=3, raw_label="3"),
                ],
            ),
        ]
    )
    t._tree.topLevelItem(0).child(0).setCheckState(0, Qt.CheckState.Checked)
    assert emitted and emitted[-1] == [3]
