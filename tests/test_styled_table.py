import pytest
from PySide6.QtWidgets import QApplication, QAbstractItemView, QHeaderView

@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    return a

def test_column_count(app):
    from styled_table import StyledTable
    t = StyledTable()
    # 3 columns: checkbox (0), Physical Page (1), Label (2)
    assert t._table.columnCount() == 3

def test_edit_triggers_disabled(app):
    from styled_table import StyledTable
    t = StyledTable()
    assert t._table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers

def test_selection_behavior_rows(app):
    from styled_table import StyledTable
    t = StyledTable()
    assert t._table.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectRows

def test_vertical_header_hidden(app):
    from styled_table import StyledTable
    t = StyledTable()
    assert t._table.verticalHeader().isHidden()

def test_column1_resize_to_contents(app):
    from styled_table import StyledTable
    t = StyledTable()
    mode = t._table.horizontalHeader().sectionResizeMode(1)
    assert mode == QHeaderView.ResizeMode.ResizeToContents

def test_column2_stretch(app):
    from styled_table import StyledTable
    t = StyledTable()
    mode = t._table.horizontalHeader().sectionResizeMode(2)
    assert mode == QHeaderView.ResizeMode.Stretch


def test_footer_default_text(app):
    from styled_table import _FooterBar
    f = _FooterBar()
    assert "No rows selected" in f._left.text()


def test_footer_one_row_selected(app):
    from styled_table import _FooterBar
    f = _FooterBar()
    f.set_count(1)
    assert "1 row selected" in f._left.text()


def test_footer_multiple_rows_selected(app):
    from styled_table import _FooterBar
    f = _FooterBar()
    f.set_count(3)
    assert "3 rows selected" in f._left.text()


def test_footer_zero_resets_to_default(app):
    from styled_table import _FooterBar
    f = _FooterBar()
    f.set_count(2)
    f.set_count(0)
    assert "No rows selected" in f._left.text()


def test_populate_sets_row_count(app):
    from styled_table import StyledTable
    t = StyledTable()
    t.populate([(1, "1"), (2, "2"), (3, "iii")])
    assert t._table.rowCount() == 3


def test_populate_col1_is_bold(app):
    from styled_table import StyledTable
    t = StyledTable()
    t.populate([(5, "v")])
    item = t._table.item(0, 1)
    assert item.font().bold()


def test_populate_roman_label_is_teal(app):
    from styled_table import StyledTable
    from colors import TEAL
    from PySide6.QtGui import QColor
    t = StyledTable()
    t.populate([(1, "i")])
    item = t._table.item(0, 2)
    assert item.foreground().color() == QColor(TEAL)


def test_populate_numeric_label_is_gray(app):
    from styled_table import StyledTable
    from colors import G700
    from PySide6.QtGui import QColor
    t = StyledTable()
    t.populate([(1, "1")])
    item = t._table.item(0, 2)
    assert item.foreground().color() == QColor(G700)


def test_checkbox_col0_is_checkable(app):
    from styled_table import StyledTable
    from PySide6.QtCore import Qt
    t = StyledTable()
    t.populate([(1, "1")])
    item = t._table.item(0, 0)
    assert item.flags() & Qt.ItemFlag.ItemIsUserCheckable


def test_footer_updates_on_check(app):
    from styled_table import StyledTable
    from PySide6.QtCore import Qt
    t = StyledTable()
    t.populate([(1, "1"), (2, "2")])
    t._table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    assert "1 row selected" in t._footer._left.text()


def test_open_req_signal_exists(app):
    from styled_table import StyledTable
    t = StyledTable()
    assert hasattr(t, "open_req")


def test_toggle_sel_signal_exists(app):
    from styled_table import StyledTable
    t = StyledTable()
    assert hasattr(t, "toggle_sel")


def test_toggle_fav_signal_exists(app):
    from styled_table import StyledTable
    t = StyledTable()
    assert hasattr(t, "toggle_fav")
