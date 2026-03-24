"""Bookmarks Tool – view, add, remove, rename, and reorder PDF bookmarks.

Uses fitz.Document.get_toc / set_toc with the flat [level, title, page]
list format.  The right panel displays a tree view of the TOC; selecting
any entry populates the left panel editor for title, target page, and
nesting level.  Up/Down buttons reorder entries; Remove deletes the
selected entry and all its children.
"""

import logging
from pathlib import Path
from utils import assert_file_writable, backup_original

from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QLineEdit,
    QScrollArea,
    QHBoxLayout,
    QVBoxLayout,
    QFileDialog,
    QMessageBox,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QAbstractItemView,
    QHeaderView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from colors import (
    BLUE,
    BLUE_HOVER,
    BLUE_DIM,
    GREEN,
    GREEN_HOVER,
    G100,
    G200,
    G300,
    G400,
    G500,
    G700,
    G900,
    WHITE,
    EMERALD,
    RED,
    RED_HOVER,
    BLUE_MED,
)
from icons import svg_pixmap

try:
    import fitz
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)

_MAX_LEVEL = 6


def _btn(text, bg, hover, text_color=WHITE, border=False, h=36, w=None) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(h)
    if w:
        b.setFixedWidth(w)
    border_s = f"border: 1px solid {G300};" if border else "border: none;"
    b.setStyleSheet(
        f"""
        QPushButton {{
            background: {bg}; color: {text_color};
            {border_s} border-radius: 6px;
            font: {"bold " if bg in (BLUE, GREEN) else ""}13px;
            padding: 0 12px;
        }}
        QPushButton:hover {{ background: {hover}; }}
        QPushButton:disabled {{ color: {G300}; background: {G100}; border-color: {G200}; }}
        """
    )
    return b


# ---------------------------------------------------------------------------
# Pure helpers — operate on the flat TOC list [[level, title, page], ...]
# ---------------------------------------------------------------------------


def toc_remove(toc: list, index: int) -> list:
    """Remove the entry at *index* and all its children."""
    if not toc or index < 0 or index >= len(toc):
        return list(toc)
    level = toc[index][0]
    end = index + 1
    while end < len(toc) and toc[end][0] > level:
        end += 1
    return toc[:index] + toc[end:]


def toc_move_up(toc: list, index: int) -> tuple[list, int]:
    """Move the entry (and its children) up by one sibling position.

    Returns the new list and the new index of the moved entry.
    """
    if index <= 0:
        return list(toc), index
    level = toc[index][0]
    # Find start of the block (entry + children)
    block_end = index + 1
    while block_end < len(toc) and toc[block_end][0] > level:
        block_end += 1
    block = toc[index:block_end]

    # Find the previous sibling at the same level
    prev = index - 1
    while prev >= 0 and toc[prev][0] > level:
        prev -= 1
    if prev < 0 or toc[prev][0] < level:
        return list(toc), index  # no same-level predecessor

    # Find the start of the previous sibling's block
    prev_start = prev
    while prev_start > 0 and toc[prev_start - 1][0] > level:
        prev_start -= 1

    new_toc = toc[:prev_start] + block + toc[prev_start:index] + toc[block_end:]
    return new_toc, prev_start


def toc_move_down(toc: list, index: int) -> tuple[list, int]:
    """Move the entry (and its children) down by one sibling position.

    Returns the new list and the new index of the moved entry.
    """
    if index < 0 or index >= len(toc):
        return list(toc), index
    level = toc[index][0]
    block_end = index + 1
    while block_end < len(toc) and toc[block_end][0] > level:
        block_end += 1
    if block_end >= len(toc) or toc[block_end][0] < level:
        return list(toc), index  # no next sibling

    # Find end of next sibling's block
    next_end = block_end + 1
    while next_end < len(toc) and toc[next_end][0] > level:
        next_end += 1

    block = toc[index:block_end]
    next_block = toc[block_end:next_end]
    new_toc = toc[:index] + next_block + block + toc[next_end:]
    return new_toc, index + len(next_block)


# ---------------------------------------------------------------------------
# BookmarksTool
# ---------------------------------------------------------------------------


class BookmarksTool(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._modified = False
        self._pdf_path = ""
        self._page_count = 0
        self._toc: list = []  # flat [[level, title, page], ...]
        self._sel_index: int = -1  # index in _toc of selected entry

        if fitz is None:
            lay = QVBoxLayout(self)
            lbl = QLabel("Missing dependency.\n\nInstall with:\n  pip install pymupdf")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {G500}; font: 16px;")
            lay.addWidget(lbl)
            return

        self._build_ui()
        self.setAcceptDrops(True)

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_left_panel())
        root.addWidget(self._build_right_panel(), 1)

    def _build_left_panel(self) -> QWidget:
        left = QWidget()
        left.setFixedWidth(360)
        left.setStyleSheet(f"background: {WHITE}; border-right: 1px solid {G200};")
        outer = QVBoxLayout(left)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("border: none; background: transparent;")

        inner = QWidget()
        inner.setStyleSheet(f"background: {WHITE};")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(24, 24, 24, 12)
        lay.setSpacing(0)

        # Title
        title_row = QHBoxLayout()
        title_row.setSpacing(12)
        title_row.setContentsMargins(0, 0, 0, 0)
        icon_box = QLabel()
        icon_box.setFixedSize(40, 40)
        icon_box.setPixmap(svg_pixmap("list", BLUE, 20))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {BLUE_MED}; border-radius: 8px;")
        title_row.addWidget(icon_box)
        title_lbl = QLabel("Bookmarks")
        title_lbl.setStyleSheet(
            f"color: {G900}; font: bold 20px; background: transparent; border: none;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)
        lay.addSpacing(28)

        # File section
        sec_file = QLabel("SOURCE FILE")
        sec_file.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_file)
        lay.addSpacing(8)

        drop_zone = QFrame()
        drop_zone.setFixedHeight(56)
        drop_zone.setStyleSheet(
            f"background: {G100}; border: 2px dashed {G200}; border-radius: 12px;"
        )
        dz_lay = QHBoxLayout(drop_zone)
        dz_lay.setContentsMargins(10, 0, 10, 0)
        dz_lay.setSpacing(8)
        dz_icon = QLabel()
        dz_icon.setPixmap(svg_pixmap("file-text", G400, 20))
        dz_icon.setStyleSheet("border: none; background: transparent;")
        dz_lay.addWidget(dz_icon)
        dz_lbl = QLabel("Drop PDF here or")
        dz_lbl.setStyleSheet(
            f"color: {G500}; font: 13px; border: none; background: transparent;"
        )
        dz_lay.addWidget(dz_lbl)
        browse_btn = _btn("Browse", BLUE, BLUE_HOVER, h=32, w=80)
        browse_btn.clicked.connect(self._browse_file)
        dz_lay.addWidget(browse_btn)
        dz_lay.addStretch()
        lay.addWidget(drop_zone)
        lay.addSpacing(24)

        # Edit section (shown when a bookmark is selected)
        sec_edit = QLabel("EDIT SELECTED")
        sec_edit.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_edit)
        lay.addSpacing(8)

        self._edit_panel = QFrame()
        self._edit_panel.setStyleSheet(
            f"background: {G100}; border: 1px solid {G200}; border-radius: 8px;"
        )
        ep_lay = QVBoxLayout(self._edit_panel)
        ep_lay.setContentsMargins(16, 14, 16, 14)
        ep_lay.setSpacing(10)

        # Title field
        title_row2 = QHBoxLayout()
        title_row2.setContentsMargins(0, 0, 0, 0)
        title_row2.setSpacing(8)
        title_fl = QLabel("Title")
        title_fl.setFixedWidth(36)
        title_fl.setStyleSheet(
            f"color: {G700}; font: 12px; background: transparent; border: none;"
        )
        title_row2.addWidget(title_fl)
        self._title_entry = QLineEdit()
        self._title_entry.setPlaceholderText("Bookmark title")
        self._title_entry.setFixedHeight(32)
        self._title_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 4px; padding: 0 8px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        title_row2.addWidget(self._title_entry, 1)
        ep_lay.addLayout(title_row2)

        # Page + level row
        pl_row = QHBoxLayout()
        pl_row.setContentsMargins(0, 0, 0, 0)
        pl_row.setSpacing(8)

        page_fl = QLabel("Page")
        page_fl.setFixedWidth(36)
        page_fl.setStyleSheet(
            f"color: {G700}; font: 12px; background: transparent; border: none;"
        )
        pl_row.addWidget(page_fl)

        self._page_spin = QSpinBox()
        self._page_spin.setRange(1, 9999)
        self._page_spin.setFixedHeight(32)
        self._page_spin.setFixedWidth(64)
        self._page_spin.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 4px; padding: 0 4px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        pl_row.addWidget(self._page_spin)

        pl_row.addSpacing(12)

        level_fl = QLabel("Level")
        level_fl.setFixedWidth(36)
        level_fl.setStyleSheet(
            f"color: {G700}; font: 12px; background: transparent; border: none;"
        )
        pl_row.addWidget(level_fl)

        self._level_spin = QSpinBox()
        self._level_spin.setRange(1, _MAX_LEVEL)
        self._level_spin.setFixedHeight(32)
        self._level_spin.setFixedWidth(52)
        self._level_spin.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 4px; padding: 0 4px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        pl_row.addWidget(self._level_spin)
        pl_row.addStretch()
        ep_lay.addLayout(pl_row)

        apply_edit_btn = _btn("Apply Changes", BLUE, BLUE_HOVER, h=32)
        apply_edit_btn.clicked.connect(self._apply_edit)
        ep_lay.addWidget(apply_edit_btn)

        self._edit_panel.setEnabled(False)
        lay.addWidget(self._edit_panel)
        lay.addSpacing(20)

        # Action buttons
        sec_actions = QLabel("ACTIONS")
        sec_actions.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(sec_actions)
        lay.addSpacing(8)

        add_btn = _btn("+ Add Bookmark", G100, G200, text_color=G700, border=True, h=34)
        add_btn.clicked.connect(self._add_bookmark)
        add_btn.setEnabled(False)
        self._add_btn = add_btn
        lay.addWidget(add_btn)
        lay.addSpacing(6)

        # Up / Down / Remove row
        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(0, 0, 0, 0)
        nav_row.setSpacing(6)

        self._up_btn = _btn("▲ Up", G100, G200, text_color=G700, border=True, h=34)
        self._up_btn.clicked.connect(self._move_up)
        self._up_btn.setEnabled(False)
        nav_row.addWidget(self._up_btn)

        self._down_btn = _btn("▼ Down", G100, G200, text_color=G700, border=True, h=34)
        self._down_btn.clicked.connect(self._move_down)
        self._down_btn.setEnabled(False)
        nav_row.addWidget(self._down_btn)

        self._remove_btn = _btn("Remove", RED, RED_HOVER, h=34)
        self._remove_btn.clicked.connect(self._remove_bookmark)
        self._remove_btn.setEnabled(False)
        nav_row.addWidget(self._remove_btn)

        lay.addLayout(nav_row)

        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # Bottom action area
        bottom = QWidget()
        bottom.setStyleSheet(f"background: {WHITE}; border-top: 1px solid {G200};")
        bot_lay = QVBoxLayout(bottom)
        bot_lay.setContentsMargins(24, 16, 24, 20)
        bot_lay.setSpacing(10)

        out_lbl = QLabel("OUTPUT FILE")
        out_lbl.setStyleSheet(
            f"color: {G500}; font: bold 11px; letter-spacing: 1.2px;"
            " background: transparent; border: none;"
        )
        bot_lay.addWidget(out_lbl)

        self._out_entry = QLineEdit()
        self._out_entry.setPlaceholderText("output_bookmarks.pdf")
        self._out_entry.setFixedHeight(36)
        self._out_entry.setStyleSheet(
            f"border: 1px solid {G200}; border-radius: 6px; padding: 0 10px;"
            f" font: 13px; color: {G900}; background: {WHITE};"
        )
        bot_lay.addWidget(self._out_entry)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color: {G500}; font: 12px; border: none; background: transparent;"
        )
        bot_lay.addWidget(self._status_lbl)

        self._save_btn = _btn("Save PDF", GREEN, GREEN_HOVER, h=42)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save)
        bot_lay.addWidget(self._save_btn)

        outer.addWidget(bottom)
        return left

    def _build_right_panel(self) -> QWidget:
        right = QWidget()
        right.setStyleSheet(f"background: {G100};")
        v = QVBoxLayout(right)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setFixedHeight(48)
        toolbar.setStyleSheet(f"background: {WHITE}; border-bottom: 1px solid {G200};")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(16, 0, 16, 0)
        tb.setSpacing(0)
        self._toolbar_lbl = QLabel("Bookmark tree")
        self._toolbar_lbl.setStyleSheet(
            f"color: {G700}; font: 13px; background: transparent; border: none;"
        )
        tb.addWidget(self._toolbar_lbl)
        tb.addStretch()
        v.addWidget(toolbar)

        # Tree widget
        self._tree = QTreeWidget()
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["Title", "Page"])
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.setAlternatingRowColors(True)
        self._tree.setIndentation(20)
        self._tree.setStyleSheet(
            f"QTreeWidget {{ border: none; background: {WHITE}; }}"
            f"QTreeWidget::item {{ padding: 4px 4px; color: {G900}; }}"
            f"QTreeWidget::item:selected {{ background: {BLUE_DIM}; color: {G900}; }}"
            f"QHeaderView::section {{ background: {G100}; color: {G700}; font: bold 12px;"
            f" border: none; border-bottom: 1px solid {G200}; padding: 6px 8px; }}"
        )
        self._tree.currentItemChanged.connect(self._on_selection_changed)
        v.addWidget(self._tree, 1)

        self._empty_lbl = QLabel("Load a PDF to view and edit its bookmarks.")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color: {G400}; font: 15px; border: none; background: {WHITE};"
        )
        v.addWidget(self._empty_lbl)

        return right

    # -----------------------------------------------------------------------
    # File loading
    # -----------------------------------------------------------------------

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if path:
            self._load_file(path)

    def _load_file(self, path: str) -> None:
        try:
            doc = fitz.open(path)
            page_count = doc.page_count
            toc = doc.get_toc()
            doc.close()
        except Exception as exc:
            logger.exception("could not open pdf for bookmarks")
            QMessageBox.warning(self, "Error", f"Could not open PDF:\n{exc}")
            return

        self._pdf_path = path
        self._page_count = page_count
        self._toc = [list(entry) for entry in toc]
        self._page_spin.setMaximum(page_count)
        stem = Path(path).stem
        self._out_entry.setText(f"{stem}_bookmarks.pdf")
        self._toolbar_lbl.setText(Path(path).name)
        self._save_btn.setEnabled(True)
        self._add_btn.setEnabled(True)
        self._sel_index = -1
        self._refresh_tree()

    # -----------------------------------------------------------------------
    # Tree management
    # -----------------------------------------------------------------------

    def _refresh_tree(self) -> None:
        self._tree.blockSignals(True)
        self._tree.clear()

        n = len(self._toc)
        self._empty_lbl.setVisible(n == 0 and not self._pdf_path)

        # Build tree structure from flat TOC list
        # stack[i] = the last QTreeWidgetItem at depth i (1-based level)
        stack: list[QTreeWidgetItem | None] = [None] * (_MAX_LEVEL + 1)

        for i, entry in enumerate(self._toc):
            level, title, page = entry[0], entry[1], entry[2]
            level = max(1, min(level, _MAX_LEVEL))

            item = QTreeWidgetItem([title, str(page)])
            item.setData(0, Qt.ItemDataRole.UserRole, i)  # store flat index

            parent = None
            for lv in range(level - 1, 0, -1):
                if stack[lv] is not None:
                    parent = stack[lv]
                    break

            if parent:
                parent.addChild(item)
            else:
                self._tree.addTopLevelItem(item)

            stack[level] = item
            # Clear deeper levels
            for lv in range(level + 1, _MAX_LEVEL + 1):
                stack[lv] = None

        self._tree.expandAll()

        # Re-select previously selected index
        if self._sel_index >= 0:
            self._select_by_index(self._sel_index)

        self._tree.blockSignals(False)

    def _select_by_index(self, index: int) -> None:
        """Find and select the tree item whose UserRole data equals index."""
        it = self._tree.invisibleRootItem()
        self._find_and_select(it, index)

    def _find_and_select(self, parent: QTreeWidgetItem, index: int) -> bool:
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) == index:
                self._tree.setCurrentItem(child)
                return True
            if self._find_and_select(child, index):
                return True
        return False

    def _on_selection_changed(
        self, current: QTreeWidgetItem, _previous: QTreeWidgetItem
    ) -> None:
        if current is None:
            self._sel_index = -1
            self._edit_panel.setEnabled(False)
            self._up_btn.setEnabled(False)
            self._down_btn.setEnabled(False)
            self._remove_btn.setEnabled(False)
            return

        idx = current.data(0, Qt.ItemDataRole.UserRole)
        if idx is None or idx >= len(self._toc):
            return
        self._sel_index = idx
        entry = self._toc[idx]
        level, title, page = entry[0], entry[1], entry[2]

        self._title_entry.setText(title)
        self._page_spin.setValue(page)
        self._level_spin.setValue(level)

        self._edit_panel.setEnabled(True)
        self._up_btn.setEnabled(True)
        self._down_btn.setEnabled(True)
        self._remove_btn.setEnabled(True)

    # -----------------------------------------------------------------------
    # Edit / Add / Remove / Move
    # -----------------------------------------------------------------------

    def _apply_edit(self) -> None:
        if self._sel_index < 0 or self._sel_index >= len(self._toc):
            return
        self._toc[self._sel_index] = [
            self._level_spin.value(),
            self._title_entry.text(),
            self._page_spin.value(),
        ]
        self._modified = True
        self._refresh_tree()

    def _add_bookmark(self) -> None:
        if self._sel_index >= 0:
            # Insert after the selected entry (and its children)
            level = self._toc[self._sel_index][0]
            end = self._sel_index + 1
            while end < len(self._toc) and self._toc[end][0] > level:
                end += 1
            self._toc.insert(end, [1, "New Bookmark", 1])
            self._sel_index = end
        else:
            self._toc.append([1, "New Bookmark", 1])
            self._sel_index = len(self._toc) - 1

        self._modified = True
        self._refresh_tree()
        # Populate edit panel with the new entry
        self._title_entry.setText("New Bookmark")
        self._page_spin.setValue(1)
        self._level_spin.setValue(1)
        self._edit_panel.setEnabled(True)

    def _remove_bookmark(self) -> None:
        if self._sel_index < 0:
            return
        self._toc = toc_remove(self._toc, self._sel_index)
        self._sel_index = min(self._sel_index, len(self._toc) - 1)
        self._modified = True
        self._refresh_tree()
        if self._sel_index < 0:
            self._edit_panel.setEnabled(False)
            self._up_btn.setEnabled(False)
            self._down_btn.setEnabled(False)
            self._remove_btn.setEnabled(False)

    def _move_up(self) -> None:
        if self._sel_index < 0:
            return
        new_toc, new_idx = toc_move_up(self._toc, self._sel_index)
        self._toc = new_toc
        self._sel_index = new_idx
        self._modified = True
        self._refresh_tree()

    def _move_down(self) -> None:
        if self._sel_index < 0:
            return
        new_toc, new_idx = toc_move_down(self._toc, self._sel_index)
        self._toc = new_toc
        self._sel_index = new_idx
        self._modified = True
        self._refresh_tree()

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------

    def _save(self) -> None:
        if not self._pdf_path:
            return
        out_name = self._out_entry.text().strip() or "bookmarks.pdf"
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"
        default_dir = str(Path(self._pdf_path).parent)
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF",
            str(Path(default_dir) / out_name),
            "PDF Files (*.pdf)",
        )
        if not out_path:
            return
        try:
            assert_file_writable(Path(out_path))
            backup_original(Path(self._pdf_path))
            doc = fitz.open(self._pdf_path)
            doc.set_toc(self._toc)
            doc.save(out_path, garbage=3, deflate=True)
            doc.close()
        except PermissionError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        except Exception as exc:
            logger.exception("could not save bookmarks pdf")
            QMessageBox.critical(self, "Save failed", str(exc))
            return

        self._status_lbl.setText("Saved successfully.")
        self._status_lbl.setStyleSheet(
            f"color: {EMERALD}; font: 12px; border: none; background: transparent;"
        )
        self._modified = False

    # -----------------------------------------------------------------------
    # Drag and drop
    # -----------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pdf"):
                self._load_file(path)
                break

    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------

    def cleanup(self) -> None:
        pass
