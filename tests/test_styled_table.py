import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView

import sys
sys.path.insert(0, ".")

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
