"""Styled tree component — VS Code-style folder hierarchy matching PDFree design system.

Wraps QTreeWidget with the same column attributes as styled_table.py (checkbox col 0,
Physical Page col 1, Label col 2, NoEditTriggers, SelectRows, MultiSelection, hidden
header) inside a card-style container.

Run standalone:  python styled_tree.py
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from colors import (
    BLUE_DIM,
    G50,
    G100,
    G200,
    G700,
    G800,
    G900,
    TEAL,
    WHITE,
)

_ORANGE_RUST = "#C2410C"
_INDENT = 20  # px per depth level
_ROW_H = 36


@dataclass
class _NodeData:
    label: str
    is_folder: bool
    page: int | None = None
    raw_label: str = ""
    checked: bool = False
    children: list["_NodeData"] = field(default_factory=list)


class _FooterBar(QWidget):
    """Bottom bar showing selection count (identical to styled_table._FooterBar)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setStyleSheet(
            f"background: {WHITE}; border-top: 1px solid {G200};"
            f" border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        self._left = QLabel("No rows selected")
        self._left.setStyleSheet(f"color: {G700}; font-size: 13px; border: none;")
        layout.addWidget(self._left)
        layout.addStretch()

    def set_count(self, n: int):
        if n == 0:
            self._left.setText("No rows selected")
        elif n == 1:
            self._left.setText("1 row selected")
        else:
            self._left.setText(f"{n} rows selected")


class StyledTree(QWidget):
    """Card-style tree with checkbox column, folder/file hierarchy, and footer bar."""

    selection_changed = Signal(list)  # emits list of checked leaf page numbers

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        self._item_changed_connected = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card = QWidget()
        card.setObjectName("treeCard")
        card.setStyleSheet(
            f"#treeCard {{ background: {WHITE}; border: 1px solid {G200};"
            f" border-radius: 8px; }}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(3)
        self._tree.header().hide()
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tree.setColumnWidth(0, 40)
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self._tree.setRootIsDecorated(False)
        self._tree.setIndentation(0)
        self._tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._apply_stylesheet()

        self._footer = _FooterBar()

        card_layout.addWidget(self._tree)
        card_layout.addWidget(self._footer)
        root.addWidget(card)

    def _apply_stylesheet(self):
        self._tree.setStyleSheet(
            f"QTreeWidget {{ border: none; background: {WHITE}; outline: none; }}"
            f"QTreeWidget::item {{ height: {_ROW_H}px; border-bottom: 1px solid {G200};"
            f" padding: 0 8px; }}"
            f"QTreeWidget::item:selected {{ background: {BLUE_DIM}; color: {G900}; }}"
            f"QTreeWidget::item:hover:!selected {{ background: {G50}; }}"
            f"QScrollBar:vertical {{ background: {WHITE}; width: 8px; }}"
            f"QScrollBar::handle:vertical {{ background: {G200}; border-radius: 4px; }}"
        )

    def populate(self, nodes: list[_NodeData]):
        """Populate tree from a list of root-level _NodeData (children nested inside)."""
        if self._item_changed_connected:
            self._tree.itemChanged.disconnect(self._on_item_changed)
        self._tree.clear()
        for node in nodes:
            self._add_node(node, parent=None, depth=0)
        self._tree.expandAll()
        self._tree.itemChanged.connect(self._on_item_changed)
        self._item_changed_connected = True
        self._update_footer()

    def _add_node(self, data: _NodeData, parent, depth: int):
        item = QTreeWidgetItem()
        item.setData(0, Qt.ItemDataRole.UserRole, data)

        if data.is_folder:
            item.setText(0, "")
            item.setText(1, "")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        else:
            chk = Qt.CheckState.Checked if data.checked else Qt.CheckState.Unchecked
            item.setCheckState(0, chk)
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
            )
            item.setText(1, str(data.page) if data.page is not None else "")

        self._style_item(item, data, depth)

        if parent is None:
            self._tree.addTopLevelItem(item)
        else:
            parent.addChild(item)

        for child in data.children:
            self._add_node(child, parent=item, depth=depth + 1)

    def _style_item(self, item: QTreeWidgetItem, data: _NodeData, depth: int):
        pad = " " * (depth * 3)
        if data.is_folder:
            folder_color = G800 if depth == 0 else G700 if depth == 1 else _ORANGE_RUST
            item.setForeground(2, QColor(folder_color))
            bold_font = QFont("Segoe UI", 13)
            bold_font.setBold(True)
            item.setFont(2, bold_font)
            item.setText(2, f"{pad}\u25be  \U0001f4c1  {data.label}")
        else:
            item.setForeground(1, QColor(G900))
            font1 = item.font(1)
            font1.setBold(True)
            item.setFont(1, font1)
            is_roman = (
                data.raw_label
                and not data.raw_label.isdigit()
                and data.raw_label not in ("", "-")
            )
            item.setForeground(2, QColor(TEAL if is_roman else G700))
            item.setText(2, f"{pad}\U0001f4c4  {data.raw_label or data.label}")

    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        if column == 0:
            self._update_footer()

    def _update_footer(self):
        checked_pages = []
        for i in range(self._tree.topLevelItemCount()):
            self._collect_checked(self._tree.topLevelItem(i), checked_pages)
        self._footer.set_count(len(checked_pages))
        self.selection_changed.emit(checked_pages)

    def _collect_checked(self, item: QTreeWidgetItem, result: list):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and not data.is_folder:
            if item.checkState(0) == Qt.CheckState.Checked:
                result.append(data.page)
        for i in range(item.childCount()):
            self._collect_checked(item.child(i), result)


if __name__ == "__main__":
    import sys

    _app = QApplication(sys.argv)

    win = QWidget()
    win.setWindowTitle("Styled Tree Demo")
    win.resize(640, 480)
    win.setStyleSheet(f"background: {G100};")

    layout = QVBoxLayout(win)
    layout.setContentsMargins(32, 32, 32, 32)

    tree = StyledTree()
    tree.populate(
        [
            _NodeData(
                label="Project",
                is_folder=True,
                children=[
                    _NodeData(
                        label="src",
                        is_folder=True,
                        children=[
                            _NodeData(
                                label="components",
                                is_folder=True,
                                children=[
                                    _NodeData(
                                        label="ui",
                                        is_folder=True,
                                        children=[
                                            _NodeData(
                                                label="button.tsx",
                                                is_folder=False,
                                                page=1,
                                                raw_label="i",
                                            ),
                                            _NodeData(
                                                label="tree.tsx",
                                                is_folder=False,
                                                page=2,
                                                raw_label="2",
                                            ),
                                        ],
                                    )
                                ],
                            )
                        ],
                    )
                ],
            )
        ]
    )
    layout.addWidget(tree)

    win.show()
    sys.exit(_app.exec())
