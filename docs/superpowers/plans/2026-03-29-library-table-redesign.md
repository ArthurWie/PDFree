# Library Table Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `_FileTableRow` / `_build_file_table` in `library_page.py` with a redesigned `StyledTable` showing Name, Date Modified (filesystem), Size, and Favorite columns, and fix the checkbox-disappearing bug.

**Architecture:** `styled_table.py` gains three library-specific signals (`open_req`, `toggle_sel`, `toggle_fav`) and a `populate_library(entries)` method that reconfigures the table to 6 columns, uses `NoSelection` mode with manual checkbox handling via `cellClicked`, and embeds star/menu `QPushButton` cell widgets. `library_page.py` replaces `_build_file_table` with a one-liner that instantiates `StyledTable` and deletes `_FileTableRow` entirely.

**Tech Stack:** PySide6 (`QTableWidget`, `setCellWidget`, `QMenu`), `os.path.getmtime`, `datetime`, colors.py tokens (`AMBER`, `AMBER_BG`, `G300`, `G400`, `G600`).

---

## File Map

| Path | Action | Responsibility |
|---|---|---|
| `styled_table.py` | Modify | Add signals, `populate_library()`, helpers, cell widgets |
| `tests/test_styled_table.py` | Modify | Add 10 library-specific tests |
| `library_page.py` | Modify | Replace `_build_file_table`, delete `_FileTableRow` and `FileCard` |

---

### Task 1: Add library signals to StyledTable

**Files:**
- Modify: `styled_table.py`
- Modify: `tests/test_styled_table.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_styled_table.py`:

```python
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
```

- [ ] **Step 2: Run to confirm failure**

```
cd C:/Users/arthu/Desktop/PDFree && pytest tests/test_styled_table.py::test_open_req_signal_exists -v
```
Expected: FAIL — `AssertionError`

- [ ] **Step 3: Add signals to StyledTable**

In `styled_table.py`, replace the class body opening:

```python
class StyledTable(QWidget):
    selection_changed = Signal(list)
```

with:

```python
class StyledTable(QWidget):
    selection_changed = Signal(list)
    open_req = Signal(str)
    toggle_sel = Signal(str, bool)
    toggle_fav = Signal(str, bool)
```

- [ ] **Step 4: Run tests**

```
cd C:/Users/arthu/Desktop/PDFree && pytest tests/test_styled_table.py -v
```
Expected: all 19 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/arthu/Desktop/PDFree && git add styled_table.py tests/test_styled_table.py && git commit -m "feat: add open_req, toggle_sel, toggle_fav signals to StyledTable"
```

---

### Task 2: Add helpers and `populate_library()` to StyledTable

**Files:**
- Modify: `styled_table.py`
- Modify: `tests/test_styled_table.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_styled_table.py`:

```python
def _sample_entries(tmp_path):
    """Return two entries: one with a real file, one with a missing path."""
    real = tmp_path / "report.pdf"
    real.write_bytes(b"x" * 1536)
    return [
        {
            "path": str(real),
            "name": "report.pdf",
            "size": 1536,
            "favorited": False,
        },
        {
            "path": "/nonexistent/ghost.pdf",
            "name": "ghost.pdf",
            "size": 0,
            "favorited": True,
        },
    ]


def test_library_column_count(app, tmp_path):
    from styled_table import StyledTable
    t = StyledTable()
    t.populate_library(_sample_entries(tmp_path))
    assert t._table.columnCount() == 6


def test_library_row_count(app, tmp_path):
    from styled_table import StyledTable
    t = StyledTable()
    t.populate_library(_sample_entries(tmp_path))
    assert t._table.rowCount() == 2


def test_library_name_bold(app, tmp_path):
    from styled_table import StyledTable
    t = StyledTable()
    t.populate_library(_sample_entries(tmp_path))
    assert t._table.item(0, 1).font().bold()


def test_library_date_missing_file(app, tmp_path):
    from styled_table import StyledTable
    t = StyledTable()
    t.populate_library(_sample_entries(tmp_path))
    # row 1 has nonexistent path — date column must be "—"
    assert t._table.item(1, 2).text() == "—"


def test_library_size_formatted(app, tmp_path):
    from styled_table import StyledTable
    t = StyledTable()
    t.populate_library(_sample_entries(tmp_path))
    # 1536 bytes = 1.5 KB
    assert t._table.item(0, 3).text() == "1.5 KB"


def test_library_star_widget_present(app, tmp_path):
    from styled_table import StyledTable
    from PySide6.QtWidgets import QPushButton
    t = StyledTable()
    t.populate_library(_sample_entries(tmp_path))
    w = t._table.cellWidget(0, 4)
    # cell widget is a wrapper QWidget containing a QPushButton
    assert w is not None
    btn = w.findChild(QPushButton)
    assert btn is not None


def test_library_menu_widget_present(app, tmp_path):
    from styled_table import StyledTable
    from PySide6.QtWidgets import QPushButton
    t = StyledTable()
    t.populate_library(_sample_entries(tmp_path))
    w = t._table.cellWidget(0, 5)
    assert w is not None
    btn = w.findChild(QPushButton)
    assert btn is not None


def test_checkbox_toggles_on_cell_click(app, tmp_path):
    from styled_table import StyledTable
    from PySide6.QtCore import Qt
    t = StyledTable()
    t.populate_library(_sample_entries(tmp_path))
    # simulate cellClicked on col 0
    t._on_library_cell_clicked(0, 0)
    assert t._table.item(0, 0).checkState() == Qt.CheckState.Checked


def test_toggle_sel_signal_emitted(app, tmp_path):
    from styled_table import StyledTable
    received = []
    t = StyledTable()
    t.populate_library(_sample_entries(tmp_path))
    t.toggle_sel.connect(lambda path, checked: received.append((path, checked)))
    t._on_library_cell_clicked(0, 0)
    assert len(received) == 1
    assert received[0][1] is True


def test_toggle_fav_signal_emitted(app, tmp_path):
    from styled_table import StyledTable
    from PySide6.QtWidgets import QPushButton
    received = []
    t = StyledTable()
    t.populate_library(_sample_entries(tmp_path))
    t.toggle_fav.connect(lambda path, fav: received.append((path, fav)))
    # get the star button from col 4 wrapper
    w = t._table.cellWidget(0, 4)
    btn = w.findChild(QPushButton)
    btn.click()
    assert len(received) == 1
    assert received[0][1] is True  # was False, now True
```

- [ ] **Step 2: Run to confirm failure**

```
cd C:/Users/arthu/Desktop/PDFree && pytest tests/test_styled_table.py::test_library_column_count -v
```
Expected: FAIL — `AttributeError: 'StyledTable' object has no attribute 'populate_library'`

- [ ] **Step 3: Add imports to `styled_table.py`**

Replace the current import block at the top of `styled_table.py`:

```python
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
    G400,
    G500,
    G600,
    G700,
    G800,
    G900,
    BLUE_DIM,
    TEAL,
    AMBER,
    AMBER_BG,
    G300,
)
```

- [ ] **Step 4: Add module-level helpers before `_FooterBar`**

Insert these two functions before the `class _FooterBar` line:

```python
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
```

- [ ] **Step 5: Add `populate_library` and helpers to `StyledTable`**

Append these methods inside the `StyledTable` class, after `_update_footer`:

```python
    def populate_library(self, entries: list[dict]):
        self._entries = list(entries)

        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["", "Name", "Date Modified", "Size", "★", ""]
        )
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 40)
        self._table.setColumnWidth(2, 160)
        self._table.setColumnWidth(3, 100)
        self._table.setColumnWidth(4, 48)
        self._table.setColumnWidth(5, 40)

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
            fav = entry.get("favorited", False)

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

            # Col 4: star widget
            star_btn = self._make_star_btn(path, fav)
            star_wrap = QWidget()
            star_wrap.setStyleSheet("background: transparent;")
            star_lay = QHBoxLayout(star_wrap)
            star_lay.setContentsMargins(0, 0, 0, 0)
            star_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            star_lay.addWidget(star_btn)
            self._table.setCellWidget(i, 4, star_wrap)

            # Col 5: menu widget
            menu_btn = self._make_menu_btn(path, star_btn)
            menu_wrap = QWidget()
            menu_wrap.setStyleSheet("background: transparent;")
            menu_lay = QHBoxLayout(menu_wrap)
            menu_lay.setContentsMargins(0, 0, 0, 0)
            menu_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            menu_lay.addWidget(menu_btn)
            self._table.setCellWidget(i, 5, menu_wrap)

        self._update_footer()

    def _make_star_btn(self, path: str, fav: bool) -> QPushButton:
        btn = QPushButton("★" if fav else "☆")
        btn.setFixedSize(28, 28)
        self._apply_star_style(btn, fav)
        btn.clicked.connect(lambda: self._on_star_clicked(btn, path))
        return btn

    def _apply_star_style(self, btn: QPushButton, fav: bool):
        btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none;"
            f" color: {AMBER if fav else G300}; font: 15px; }}"
            f"QPushButton:hover {{ color: {AMBER}; background: {AMBER_BG};"
            f" border-radius: 6px; }}"
        )

    def _on_star_clicked(self, btn: QPushButton, path: str):
        new_fav = btn.text() != "★"
        btn.setText("★" if new_fav else "☆")
        self._apply_star_style(btn, new_fav)
        self.toggle_fav.emit(path, new_fav)

    def _make_menu_btn(self, path: str, star_btn: QPushButton) -> QPushButton:
        btn = QPushButton("···")
        btn.setFixedSize(28, 28)
        btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none;"
            f" color: {G400}; font: bold 14px; }}"
            f"QPushButton:hover {{ background: {G100}; border-radius: 6px;"
            f" color: {G600}; }}"
        )
        btn.clicked.connect(lambda: self._show_context_menu(btn, path, star_btn))
        return btn

    def _show_context_menu(
        self, anchor: QPushButton, path: str, star_btn: QPushButton
    ):
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
        is_fav = star_btn.text() == "★"
        fav_txt = "Remove from Favorites" if is_fav else "Add to Favorites"
        menu.addAction(fav_txt, lambda: self._on_star_clicked(star_btn, path))
        menu.addSeparator()
        menu.addAction("Move to Trash", lambda: self.toggle_sel.emit(path, True))
        pos = anchor.mapToGlobal(anchor.rect().bottomLeft())
        menu.exec(pos)

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
        if col in (0, 4, 5):
            return
        if row < len(self._entries):
            self.open_req.emit(self._entries[row].get("path", ""))
```

- [ ] **Step 6: Run all tests**

```
cd C:/Users/arthu/Desktop/PDFree && pytest tests/test_styled_table.py -v
```
Expected: all 29 tests PASS. If any fail, fix the implementation — do NOT modify tests.

- [ ] **Step 7: Run ruff**

```
cd C:/Users/arthu/Desktop/PDFree && ruff format styled_table.py && ruff check styled_table.py
```
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
cd C:/Users/arthu/Desktop/PDFree && git add styled_table.py tests/test_styled_table.py && git commit -m "feat: add populate_library with 6 columns, star/menu widgets, checkbox fix"
```

---

### Task 3: Replace `_build_file_table` and delete `_FileTableRow` in library_page.py

**Files:**
- Modify: `library_page.py`

No new tests — existing test suite covers regressions.

- [ ] **Step 1: Add StyledTable import to library_page.py**

Find the block of local imports near the top of `library_page.py` (after the `from colors import` block) and add:

```python
from styled_table import StyledTable
```

- [ ] **Step 2: Replace `_build_file_table`**

Find `_build_file_table` (lines 1587–1643) and replace the entire method with:

```python
    def _build_file_table(self, files: list[dict]) -> StyledTable:
        table = StyledTable()
        table.open_req.connect(self._open_file)
        table.toggle_sel.connect(self._on_toggle_sel)
        table.toggle_fav.connect(self._on_toggle_fav)
        table.populate_library(files)
        return table
```

- [ ] **Step 3: Delete `_FileTableRow` and `FileCard`**

Delete the entire `_FileTableRow` class (lines 870–1071) and the alias on line 1072:

```python
FileCard = _FileTableRow
```

Both must be removed. Verify no other file imports `_FileTableRow` or `FileCard` before deleting:

```
cd C:/Users/arthu/Desktop/PDFree && grep -r "FileCard\|_FileTableRow" --include="*.py" .
```

Expected: only matches inside `library_page.py` itself (the lines you're about to delete). If other files import it, do NOT delete yet — report the finding instead.

- [ ] **Step 4: Run ruff**

```
cd C:/Users/arthu/Desktop/PDFree && ruff format library_page.py && ruff check library_page.py
```
Fix any unused imports left behind by deleting `_FileTableRow` (e.g., `QCursor`, `QSizePolicy` if they were only used there). Remove only the ones that are genuinely unused after the deletion.

- [ ] **Step 5: Run full test suite**

```
cd C:/Users/arthu/Desktop/PDFree && pytest -v
```
Expected: same pass/fail ratio as before (the 2 pre-existing failures from missing `openpyxl`/`pyhanko` are acceptable — no new failures).

- [ ] **Step 6: Commit**

```bash
cd C:/Users/arthu/Desktop/PDFree && git add library_page.py && git commit -m "feat: replace _FileTableRow with StyledTable in library_page"
```

---

### Task 4: Smoke-test the running app

**Files:** None modified.

- [ ] **Step 1: Run the library demo / full app**

```
cd C:/Users/arthu/Desktop/PDFree && python main.py
```

Open the Library page. Verify:
- Table shows Name, Date Modified, Size, ★, ··· columns
- Checkboxes stay checked when clicked (not disappear)
- Star button toggles between ★ (amber) and ☆ (gray)
- ··· menu opens with Open / Show in Explorer / Add-Remove Favorites / Move to Trash
- Double-clicking a row opens the PDF

If the app does not start or the library page crashes, check the traceback and fix before committing.

- [ ] **Step 2: Run full test suite one final time**

```
cd C:/Users/arthu/Desktop/PDFree && pytest -v
```
Expected: no new failures vs. pre-task baseline.

---

## Self-Review

**Spec coverage:**

| Requirement | Task |
|---|---|
| Checkbox fix (disappearing bug) | Task 2 — `NoSelection` mode + `_on_library_cell_clicked` |
| 6 columns: checkbox, name, date modified, size, star, menu | Task 2 — `populate_library` |
| Date Modified = `os.path.getmtime`, formatted cross-platform | Task 2 — `_fmt_mtime` |
| Missing file → "—" | Task 2 — `_fmt_mtime` OSError catch |
| Size formatted | Task 2 — `_fmt_size` |
| Star button: AMBER filled / G300 hollow, AMBER_BG hover | Task 2 — `_make_star_btn` / `_apply_star_style` |
| Menu: Open, Show in Explorer, Add/Remove Favorites, Move to Trash | Task 2 — `_show_context_menu` |
| `open_req`, `toggle_sel`, `toggle_fav` signals | Task 1 + Task 2 |
| Double-click row → `open_req` | Task 2 — `_on_library_cell_double_clicked` |
| Replace `_build_file_table` | Task 3 |
| Delete `_FileTableRow` | Task 3 |
| Existing signal handlers (`_open_file`, `_on_toggle_sel`, `_on_toggle_fav`) unchanged | Task 3 — confirmed by inspection |

**Placeholder scan:** None found.

**Type consistency:**
- `_make_star_btn(path, fav) -> QPushButton` — called in `populate_library`, referenced in `_show_context_menu` and `_on_star_clicked` — consistent.
- `_on_star_clicked(btn, path)` — called from star btn's `clicked` and from menu action — consistent.
- `_entries` list — set in `populate_library`, indexed in `_on_library_cell_clicked` and `_on_library_cell_double_clicked` — consistent.
- `toggle_sel(str, bool)` — emitted in `_on_library_cell_clicked` and `_show_context_menu` (Move to Trash) — consistent with `LibraryPage._on_toggle_sel(path, selected)` signature.
