import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QLabel,
    QPushButton,
    QMenu,
    QApplication,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from colors import (
    WHITE,
    G100,
    G200,
    G300,
    G400,
    G500,
    G600,
    G700,
    G800,
    G900,
    BLUE_DIM,
    TEAL,
)


def _fmt_size(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    if b < 1024**2:
        return f"{b / 1024:.1f} KB"
    return f"{b / 1024**2:.1f} MB"


def _fmt_mtime(path: str) -> str:
    try:
        ts = os.path.getmtime(path)
        dt = datetime.fromtimestamp(ts)
        return dt.strftime("%b ") + str(dt.day) + dt.strftime(", %Y")
    except OSError:
        return "—"


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
    open_req = Signal(str)
    toggle_sel = Signal(str, bool)
    toggle_fav = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries = []
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
            f"QTableWidget {{ border: none; background: transparent; outline: none; }}"
            f"QTableWidget::item {{ padding: 0 12px; color: {G900}; }}"
            f"QTableWidget::item:selected {{ background: {BLUE_DIM}; color: {G900}; }}"
            f"QHeaderView::section {{ background: {G100}; color: {G500};"
            f" font-size: 12px; border: none;"
            f" border-bottom: 1px solid {G200}; padding: 8px 12px; }}"
            f"QScrollBar:vertical {{ background: transparent; width: 8px; }}"
            f"QScrollBar::handle:vertical {{ background: {G200}; border-radius: 4px; }}"
        )
        self._table.viewport().setStyleSheet("background: transparent;")

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
            chk_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            chk_item.setCheckState(Qt.CheckState.Unchecked)
            chk_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(i, 0, chk_item)

            page_item = QTableWidgetItem(str(page))
            page_item.setTextAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            )
            font = page_item.font()
            font.setBold(True)
            page_item.setFont(font)
            page_item.setForeground(QColor(G800))
            self._table.setItem(i, 1, page_item)

            label_item = QTableWidgetItem(label)
            label_item.setTextAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            )
            is_roman = label and not label.isdigit() and label not in ("", "-")
            label_item.setForeground(QColor(TEAL if is_roman else G700))
            self._table.setItem(i, 2, label_item)

        self._table.itemChanged.connect(self._on_item_changed)
        self._update_footer()

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() == 0:
            self._update_footer()

    def _update_footer(self):
        checked_rows = [
            r
            for r in range(self._table.rowCount())
            if self._table.item(r, 0)
            and self._table.item(r, 0).checkState() == Qt.CheckState.Checked
        ]
        self._footer.set_count(len(checked_rows))
        self.selection_changed.emit(checked_rows)

    def populate_library(self, entries: list[dict]):
        self._entries = list(entries)

        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["", "Name", "Date Modified", "Size", ""]
        )
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 40)
        self._table.setColumnWidth(2, 160)
        self._table.setColumnWidth(3, 100)
        self._table.setColumnWidth(4, 40)

        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        try:
            self._table.cellClicked.disconnect()
        except RuntimeError:
            pass
        try:
            self._table.cellDoubleClicked.disconnect()
        except RuntimeError:
            pass
        try:
            self._table.itemChanged.disconnect(self._on_item_changed)
        except RuntimeError:
            pass

        self._table.cellClicked.connect(self._on_library_cell_clicked)
        self._table.cellDoubleClicked.connect(self._on_library_cell_double_clicked)

        self._table.setRowCount(len(entries))

        for i, entry in enumerate(entries):
            self._table.setRowHeight(i, 48)
            path = entry.get("path", "")
            name = entry.get("name", Path(path).name if path else "")
            size = entry.get("size", 0) or 0

            # Col 0: checkbox
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Unchecked)
            chk.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(i, 0, chk)

            # Col 1: name — bold
            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            )
            f = name_item.font()
            f.setBold(True)
            name_item.setFont(f)
            name_item.setForeground(QColor(G800))
            self._table.setItem(i, 1, name_item)

            # Col 2: date modified
            date_item = QTableWidgetItem(_fmt_mtime(path))
            date_item.setTextAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            )
            date_item.setForeground(QColor(G600))
            self._table.setItem(i, 2, date_item)

            # Col 3: size — right-aligned
            size_item = QTableWidgetItem(_fmt_size(size))
            size_item.setTextAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
            )
            size_item.setForeground(QColor(G600))
            self._table.setItem(i, 3, size_item)

            # Col 4: menu widget
            menu_btn = self._make_menu_btn(path)
            menu_wrap = QWidget()
            menu_wrap.setStyleSheet("background: transparent;")
            menu_lay = QHBoxLayout(menu_wrap)
            menu_lay.setContentsMargins(0, 0, 0, 0)
            menu_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            menu_lay.addWidget(menu_btn)
            self._table.setCellWidget(i, 4, menu_wrap)

        self._update_footer()

    def _make_menu_btn(self, path: str) -> QPushButton:
        btn = QPushButton("···")
        btn.setFixedSize(28, 28)
        btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none;"
            f" color: {G400}; font: bold 14px; }}"
            f"QPushButton:hover {{ background: {G100}; border-radius: 6px;"
            f" color: {G600}; }}"
        )
        btn.clicked.connect(lambda: self._show_context_menu(btn, path))
        return btn

    def _show_context_menu(self, anchor: QPushButton, path: str):
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {WHITE}; border: 1px solid {G200};"
            f" border-radius: 8px; padding: 4px; }}"
            f"QMenu::item {{ padding: 6px 20px; color: {G700};"
            f" font-size: 13px; border-radius: 4px; }}"
            f"QMenu::item:selected {{ background: {G100}; }}"
            f"QMenu::separator {{ background: {G200}; height: 1px;"
            f" margin: 4px 10px; }}"
        )
        menu.addAction("Open", lambda: self.open_req.emit(path))
        menu.addAction("Show in Explorer", lambda: self._show_in_explorer(path))
        entry = next((e for e in self._entries if e.get("path") == path), {})
        is_fav = entry.get("favorited", False)
        fav_txt = "Remove from Favorites" if is_fav else "Add to Favorites"
        menu.addAction(fav_txt, lambda: self._toggle_fav_from_menu(path, is_fav))
        menu.addSeparator()
        menu.addAction("Move to Trash", lambda: self.toggle_sel.emit(path, True))
        pos = anchor.mapToGlobal(anchor.rect().bottomLeft())
        menu.exec(pos)

    def _toggle_fav_from_menu(self, path: str, was_fav: bool):
        new_fav = not was_fav
        for e in self._entries:
            if e.get("path") == path:
                e["favorited"] = new_fav
                break
        self.toggle_fav.emit(path, new_fav)

    def _show_in_explorer(self, path: str):
        p = str(Path(path))
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", p])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", p])
        except OSError:
            pass

    def _on_library_cell_clicked(self, row: int, col: int):
        if col != 0:
            return
        item = self._table.item(row, 0)
        if item is None:
            return
        new_state = (
            Qt.CheckState.Unchecked
            if item.checkState() == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        item.setCheckState(new_state)
        path = self._entries[row].get("path", "") if row < len(self._entries) else ""
        self.toggle_sel.emit(path, new_state == Qt.CheckState.Checked)
        self._update_footer()

    def _on_library_cell_double_clicked(self, row: int, col: int):
        if col in (0, 4):
            return
        if row < len(self._entries):
            self.open_req.emit(self._entries[row].get("path", ""))


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    window = QWidget()
    window.setWindowTitle("Styled Table Demo")
    window.resize(700, 400)
    window.setStyleSheet(f"background: {G100};")

    layout = QVBoxLayout(window)
    layout.setContentsMargins(32, 32, 32, 32)

    table = StyledTable()
    table.populate(
        [
            (1, "i"),
            (2, "ii"),
            (3, "iii"),
            (4, "iv"),
            (5, "1"),
            (6, "2"),
            (7, "3"),
            (8, "A"),
            (9, "B"),
        ]
    )
    layout.addWidget(table)

    window.show()
    sys.exit(app.exec())
