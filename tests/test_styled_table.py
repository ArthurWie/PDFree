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
