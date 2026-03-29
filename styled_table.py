from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QLabel,
    QApplication,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from colors import (
    WHITE, G100, G200, G500, G700, G800, G900,
    BLUE_DIM, TEAL,
)


class _FooterBar(QWidget):

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


class StyledTable(QWidget):

    selection_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card = QWidget()
        card.setObjectName("tableCard")
        card.setStyleSheet(
            f"#tableCard {{ background: {WHITE}; border: 1px solid {G200};"
            f" border-radius: 8px; }}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["", "Physical Page", "Label"])

        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 40)

        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().hide()
        self._table.setShowGrid(False)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._table.setStyleSheet(
            f"QTableWidget {{ border: none; background: {WHITE}; outline: none; }}"
            f"QTableWidget::item {{ padding: 0 12px; color: {G900};"
            f" border-bottom: 1px solid {G200}; }}"
            f"QTableWidget::item:selected {{ background: {BLUE_DIM}; color: {G900}; }}"
            f"QHeaderView::section {{ background: {WHITE}; color: {G500};"
            f" font-size: 12px; border: none;"
            f" border-bottom: 1px solid {G200}; padding: 8px 12px; }}"
            f"QScrollBar:vertical {{ background: {WHITE}; width: 8px; }}"
            f"QScrollBar::handle:vertical {{ background: {G200}; border-radius: 4px; }}"
        )

        self._footer = _FooterBar()

        card_layout.addWidget(self._table)
        card_layout.addWidget(self._footer)
        root.addWidget(card)

    def populate(self, rows: list[tuple[int, str]]):
        try:
            self._table.itemChanged.disconnect(self._on_item_changed)
        except RuntimeError:
            pass

        self._table.setRowCount(len(rows))

        for i, (page, label) in enumerate(rows):
            self._table.setRowHeight(i, 48)

            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk_item.setCheckState(Qt.CheckState.Unchecked)
            chk_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(i, 0, chk_item)

            page_item = QTableWidgetItem(str(page))
            page_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            font = page_item.font()
            font.setBold(True)
            page_item.setFont(font)
            page_item.setForeground(QColor(G800))
            self._table.setItem(i, 1, page_item)

            label_item = QTableWidgetItem(label)
            label_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            is_roman = label and not label.isdigit() and label not in ("", "-")
            label_item.setForeground(QColor(TEAL if is_roman else G700))
            self._table.setItem(i, 2, label_item)

        self._table.itemChanged.connect(self._on_item_changed)
        self._update_footer()

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() == 0:
            self._update_footer()

    def _update_footer(self):
        checked = sum(
            1 for r in range(self._table.rowCount())
            if self._table.item(r, 0)
            and self._table.item(r, 0).checkState() == Qt.CheckState.Checked
        )
        self._footer.set_count(checked)
        self.selection_changed.emit(
            [
                r for r in range(self._table.rowCount())
                if self._table.item(r, 0)
                and self._table.item(r, 0).checkState() == Qt.CheckState.Checked
            ]
        )
