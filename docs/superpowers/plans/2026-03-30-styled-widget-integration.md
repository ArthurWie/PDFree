# Styled Widget Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate `StyledTree` and `StyledTable` into `bookmarks_tool.py` and `page_labels_tool.py`, and apply consistent card styling via a new `card_wrap()` utility to `font_info_tool.py` and `form_export_tool.py`.

**Architecture:** `card_wrap(widget)` in `widgets.py` wraps any raw `QTreeWidget`/`QTableWidget` in a card container (white background, `G200` border, 8px radius) and applies standardised header QSS. `BookmarksTool` uses `StyledTree` as a card+footer wrapper while keeping its existing `QTreeWidgetItem` management logic unchanged on the underlying `_tree`. `PageLabelsTool` delegates row population entirely to `StyledTable.populate()`.

**Tech Stack:** PySide6, `styled_tree.StyledTree`, `styled_table.StyledTable`, `colors.py` tokens, `widgets.py`.

---

## File Map

| Path | Action | Responsibility |
|---|---|---|
| `widgets.py` | Modify | Add `card_wrap()` utility |
| `tests/test_widgets.py` | Modify | Tests for `card_wrap()` |
| `font_info_tool.py` | Modify | Apply `card_wrap()`, remove inline QSS, update layout/visibility |
| `form_export_tool.py` | Modify | Apply `card_wrap()`, remove inline QSS, update layout/visibility |
| `page_labels_tool.py` | Modify | Replace `QTableWidget` setup + population with `StyledTable` |
| `bookmarks_tool.py` | Modify | Replace `QTreeWidget` setup with `StyledTree`, route ops through `._tree` |

---

### Task 1: card_wrap() utility in widgets.py

**Files:**
- Modify: `widgets.py`
- Modify: `tests/test_widgets.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_widgets.py`:

```python
def test_card_wrap_returns_qwidget(qtbot):
    from PySide6.QtWidgets import QTreeWidget
    from widgets import card_wrap

    inner = QTreeWidget()
    qtbot.addWidget(inner)
    wrapper = card_wrap(inner)
    qtbot.addWidget(wrapper)
    assert isinstance(wrapper, QWidget)


def test_card_wrap_contains_inner_widget(qtbot):
    from PySide6.QtWidgets import QTreeWidget
    from widgets import card_wrap

    inner = QTreeWidget()
    qtbot.addWidget(inner)
    wrapper = card_wrap(inner)
    qtbot.addWidget(wrapper)
    assert inner.parent() == wrapper


def test_card_wrap_applies_border_stylesheet(qtbot):
    from PySide6.QtWidgets import QTreeWidget
    from widgets import card_wrap

    inner = QTreeWidget()
    qtbot.addWidget(inner)
    wrapper = card_wrap(inner)
    qtbot.addWidget(wrapper)
    assert "border-radius: 8px" in wrapper.styleSheet()
    assert "border:" in wrapper.styleSheet()
```

- [ ] **Step 2: Run to confirm failure**

```
python -m pytest tests/test_widgets.py -k "card_wrap" -v
```
Expected: `ImportError: cannot import name 'card_wrap' from 'widgets'`

- [ ] **Step 3: Implement `card_wrap` in `widgets.py`**

Update the imports block at the top of `widgets.py`:

```python
from colors import BLUE_DIM, G100, G200, G400, G700, G900, WHITE
```

Then add this function after the `PreviewCanvas` class:

```python
def card_wrap(widget, parent=None):
    """Wrap any QAbstractItemView in a card container matching the PDFree design system.

    Applies a white background card with G200 border and 8px border-radius to the
    outer container, and replaces the widget's inline stylesheet with a standardised
    QSS covering item padding, selection colour, alternate rows, and header sections.

    Args:
        widget: The QWidget (typically QTreeWidget or QTableWidget) to wrap.
        parent: Optional parent for the container widget.

    Returns:
        QWidget: The card container with widget inside.
    """
    from PySide6.QtWidgets import QVBoxLayout

    container = QWidget(parent)
    container.setObjectName("cardWrap")
    container.setStyleSheet(
        "#cardWrap { background: " + WHITE + "; border: 1px solid " + G200 + ";"
        " border-radius: 8px; }"
    )
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    widget.setStyleSheet(
        "QTreeWidget, QTableWidget { border: none; background: " + WHITE + ";"
        " alternate-background-color: " + G100 + "; font: 13px; }"
        "QTreeWidget::item, QTableWidget::item { padding: 4px 8px; color: " + G900 + "; }"
        "QTreeWidget::item:selected, QTableWidget::item:selected"
        " { background: " + BLUE_DIM + "; color: " + G900 + "; }"
        "QHeaderView::section { background: " + G100 + "; color: " + G700 + ";"
        " font: bold 11px; padding: 6px 8px; border: none;"
        " border-bottom: 1px solid " + G200 + "; }"
    )
    layout.addWidget(widget)
    return container
```

- [ ] **Step 4: Run tests**

```
python -m pytest tests/test_widgets.py -v
```
Expected: all tests PASS (existing PreviewCanvas tests + 3 new card_wrap tests)

- [ ] **Step 5: Run ruff**

```
ruff format widgets.py tests/test_widgets.py
ruff check widgets.py tests/test_widgets.py
```
Expected: exit 0

- [ ] **Step 6: Commit**

```bash
git add widgets.py tests/test_widgets.py
git commit -m "feat: add card_wrap() utility to widgets.py"
```

---

### Task 2: FontInfoTool — apply card_wrap

**Files:**
- Modify: `font_info_tool.py:295-343`

- [ ] **Step 1: Run existing font info tests to establish baseline**

```
python -m pytest tests/test_font_info.py -v
```
Expected: all pass. Note the count.

- [ ] **Step 2: Add import for card_wrap in font_info_tool.py**

At the top of `font_info_tool.py`, find the line that imports from `widgets` (or add one). Add `card_wrap` to the import:

```python
from widgets import card_wrap
```

If `widgets` is not yet imported in this file, add the line after the other local imports.

- [ ] **Step 3: Remove the inline setStyleSheet and replace with card_wrap**

In `font_info_tool.py`, find the block starting at `self._table.setStyleSheet(f"""` (around line 316) and ending with the closing `""")` (around line 328). Delete the entire `setStyleSheet` call.

Then find:
```python
        self._table.setVisible(False)
        v.addWidget(placeholder, 1)
        v.addWidget(self._table, 1)
        self._placeholder_widget = placeholder
```

Replace with:
```python
        self._table_card = card_wrap(self._table)
        self._table_card.setVisible(False)
        v.addWidget(placeholder, 1)
        v.addWidget(self._table_card, 1)
        self._placeholder_widget = placeholder
```

- [ ] **Step 4: Update visibility call in _populate_table**

In `font_info_tool.py`, find `_populate_table`. It contains:
```python
        self._table.setVisible(True)
        self._placeholder_widget.setVisible(False)
```

Replace `self._table.setVisible(True)` with `self._table_card.setVisible(True)`:
```python
        self._table_card.setVisible(True)
        self._placeholder_widget.setVisible(False)
```

All other references to `self._table` (`.clear()`, `.addTopLevelItem()`, `.setVisible(False)` in `_load_file`) stay unchanged — they operate on the inner widget, not the card.

- [ ] **Step 5: Check for any remaining self._table.setVisible calls**

Search the file for `self._table.setVisible` and confirm none remain (the one at construction was replaced with `self._table_card.setVisible(False)` and the one in `_populate_table` with `self._table_card.setVisible(True)`).

- [ ] **Step 6: Run tests**

```
python -m pytest tests/test_font_info.py -v
```
Expected: same count as baseline, all pass.

- [ ] **Step 7: Run ruff**

```
ruff format font_info_tool.py
ruff check font_info_tool.py
```
Expected: exit 0

- [ ] **Step 8: Commit**

```bash
git add font_info_tool.py
git commit -m "feat: apply card_wrap styling to FontInfoTool table"
```

---

### Task 3: FormExportTool — apply card_wrap

**Files:**
- Modify: `form_export_tool.py:309-354`

- [ ] **Step 1: Run existing form export tests to establish baseline**

```
python -m pytest tests/test_form_export.py -v
```
Expected: note count and which pass (the xlsx test may fail due to missing openpyxl — that is pre-existing).

- [ ] **Step 2: Add import for card_wrap in form_export_tool.py**

At the top of `form_export_tool.py`, add:
```python
from widgets import card_wrap
```

- [ ] **Step 3: Remove inline setStyleSheet and replace with card_wrap**

Find the block starting at `self._table.setStyleSheet(f"""` (around line 324) and ending with the closing `""")` (around line 336). Delete the entire `setStyleSheet` call.

Then find:
```python
        self._table.setVisible(False)
        v.addWidget(placeholder, 1)
        v.addWidget(self._table, 1)
        self._placeholder_widget = placeholder
```

Replace with:
```python
        self._table_card = card_wrap(self._table)
        self._table_card.setVisible(False)
        v.addWidget(placeholder, 1)
        v.addWidget(self._table_card, 1)
        self._placeholder_widget = placeholder
```

- [ ] **Step 4: Update visibility call in _populate_table**

In `form_export_tool.py`, find `_populate_table`. It contains:
```python
        self._table.setVisible(True)
        self._placeholder_widget.setVisible(False)
```

Replace with:
```python
        self._table_card.setVisible(True)
        self._placeholder_widget.setVisible(False)
```

- [ ] **Step 5: Run tests**

```
python -m pytest tests/test_form_export.py -v
```
Expected: same results as baseline.

- [ ] **Step 6: Run ruff**

```
ruff format form_export_tool.py
ruff check form_export_tool.py
```
Expected: exit 0

- [ ] **Step 7: Commit**

```bash
git add form_export_tool.py
git commit -m "feat: apply card_wrap styling to FormExportTool table"
```

---

### Task 4: PageLabelsTool → StyledTable

**Files:**
- Modify: `page_labels_tool.py:529-549` (setup), `page_labels_tool.py:633-645` (`_refresh_preview`)

- [ ] **Step 1: Run existing page labels tests to establish baseline**

```
python -m pytest tests/test_page_labels.py -v
```
Expected: all pass. Note the count.

- [ ] **Step 2: Add imports in page_labels_tool.py**

At the top of `page_labels_tool.py`, find the existing import block and add:
```python
from styled_table import StyledTable
```

Remove `QTableWidget` and `QTableWidgetItem` from the PySide6 imports if they are no longer used after the swap (check the file — these are used only in the table setup and `_refresh_preview`).

- [ ] **Step 3: Replace QTableWidget setup with StyledTable**

Find the block starting at `# Table` (around line 529) and ending with `v.addWidget(self._table, 1)` (around line 549). Replace the entire block:

```python
        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Physical Page", "Label"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().hide()
        self._table.setStyleSheet(
            f"QTableWidget {{ border: none; background: {WHITE}; gridline-color: {G100}; }}"
            f"QTableWidget::item {{ padding: 0 8px; color: {G900}; }}"
            f"QHeaderView::section {{ background: {G100}; color: {G700}; font: bold 12px;"
            f" border: none; border-bottom: 1px solid {G200}; padding: 6px 8px; }}"
        )
        v.addWidget(self._table, 1)
```

With:

```python
        # Table
        self._table = StyledTable()
        v.addWidget(self._table, 1)
```

- [ ] **Step 4: Replace _refresh_preview population loop with StyledTable.populate()**

Find `_refresh_preview` (around line 633). Replace:

```python
    def _refresh_preview(self) -> None:
        if not self._page_count:
            return
        ranges = self._get_ranges()
        labels = compute_labels(ranges, self._page_count)

        self._table.setRowCount(self._page_count)
        for i, label in enumerate(labels):
            phys_item = QTableWidgetItem(str(i + 1))
            phys_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            label_item = QTableWidgetItem(label)
            self._table.setItem(i, 0, phys_item)
            self._table.setItem(i, 1, label_item)
```

With:

```python
    def _refresh_preview(self) -> None:
        if not self._page_count:
            return
        ranges = self._get_ranges()
        labels = compute_labels(ranges, self._page_count)
        self._table.populate(list(enumerate(labels, 1)))
```

- [ ] **Step 5: Remove now-unused imports**

Check which of `QTableWidget`, `QTableWidgetItem`, `QHeaderView`, `QAbstractItemView` are still needed in `page_labels_tool.py` (they may be used by other parts of the file). Remove only the ones that are now unused. Run ruff to confirm:

```
ruff check page_labels_tool.py
```

Fix any `F401` (unused import) errors reported.

- [ ] **Step 6: Run tests**

```
python -m pytest tests/test_page_labels.py -v
```
Expected: same count as baseline, all pass.

- [ ] **Step 7: Run ruff format**

```
ruff format page_labels_tool.py
ruff check page_labels_tool.py
```
Expected: exit 0

- [ ] **Step 8: Commit**

```bash
git add page_labels_tool.py
git commit -m "feat: replace QTableWidget with StyledTable in PageLabelsTool"
```

---

### Task 5: BookmarksTool → StyledTree

**Files:**
- Modify: `bookmarks_tool.py:454-473` (setup), `bookmarks_tool.py:520-560` (`_refresh_tree`)

The strategy is to use `StyledTree` as the card+footer wrapper only — all `QTreeWidgetItem` management continues to operate on the underlying `self._styled_tree._tree`. This preserves the existing `UserRole`-stored flat index without any `_NodeData` changes.

- [ ] **Step 1: Run existing bookmark tests to establish baseline**

```
python -m pytest tests/test_bookmarks.py -v
```
Expected: all pass. Note the count.

- [ ] **Step 2: Add imports in bookmarks_tool.py**

At the top of `bookmarks_tool.py`, add:
```python
from styled_tree import StyledTree
```

Remove `QTreeWidget` from PySide6 imports if it becomes unused (check the rest of the file first — it may still be referenced in type annotations or other places). Run `ruff check` after to confirm.

- [ ] **Step 3: Replace QTreeWidget setup with StyledTree**

Find the block:
```python
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
```

Replace with:

```python
        # Tree widget
        self._styled_tree = StyledTree()
        self._tree = self._styled_tree._tree
        self._tree.setColumnCount(2)
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setAlternatingRowColors(True)
        self._tree.setIndentation(20)
        self._tree.currentItemChanged.connect(self._on_selection_changed)
        v.addWidget(self._styled_tree, 1)
```

Note: `self._tree` is now an alias for `self._styled_tree._tree`. All existing code that uses `self._tree` (in `_refresh_tree`, `_select_by_index`, `_find_and_select`, `_on_selection_changed`, `_add_bookmark`, `_move_up`, `_move_down`, `_remove_selected`) continues to work unchanged because `self._tree` still refers to the underlying `QTreeWidget`.

- [ ] **Step 4: Verify _refresh_tree needs no changes**

Open `bookmarks_tool.py` and read `_refresh_tree`. Confirm it only uses `self._tree` (not `self._styled_tree`). Since `self._tree = self._styled_tree._tree`, all calls (`self._tree.blockSignals`, `self._tree.clear`, `self._tree.addTopLevelItem`, `self._tree.expandAll`) are unchanged.

If any call in `_refresh_tree` references `self._tree` directly — no change needed.

- [ ] **Step 5: Run tests**

```
python -m pytest tests/test_bookmarks.py -v
```
Expected: same count as baseline, all pass.

- [ ] **Step 6: Run full suite to check for regressions**

```
python -m pytest -v --tb=short -q
```
Expected: same pass count as before this task (363 passed, 2 pre-existing failures).

- [ ] **Step 7: Run ruff**

```
ruff format bookmarks_tool.py
ruff check bookmarks_tool.py
```
Expected: exit 0

- [ ] **Step 8: Commit**

```bash
git add bookmarks_tool.py
git commit -m "feat: replace QTreeWidget with StyledTree in BookmarksTool"
```

---

### Task 6: Full regression check

**Files:** None modified.

- [ ] **Step 1: Run full test suite**

```
python -m pytest -v --tb=short
```
Expected: 363 passed, 2 pre-existing failures (`test_xlsx_export_roundtrip`, `test_sign_worker_full_round_trip`), 8 skipped. No new failures.

- [ ] **Step 2: Run ruff on all modified files**

```
ruff format widgets.py font_info_tool.py form_export_tool.py page_labels_tool.py bookmarks_tool.py
ruff check widgets.py font_info_tool.py form_export_tool.py page_labels_tool.py bookmarks_tool.py
```
Expected: exit 0 on all.

- [ ] **Step 3: If any new failure appears**, trace to the specific file changed in Tasks 1–5 that caused it. Fix the root cause in that file — do not skip or modify the failing test.

---

## Self-Review

**Spec coverage:**
- `card_wrap()` in `widgets.py` — Task 1 ✓
- `FontInfoTool` card_wrap + visibility update — Task 2 ✓
- `FormExportTool` card_wrap + visibility update — Task 3 ✓
- `PageLabelsTool` StyledTable swap + `_refresh_preview` → `populate()` — Task 4 ✓
- `BookmarksTool` StyledTree wrapper + `self._tree` alias — Task 5 ✓
- Full regression — Task 6 ✓

**Placeholder scan:** None found. All steps contain complete code.

**Type consistency:**
- `card_wrap(widget, parent=None) → QWidget` — defined Task 1, used Tasks 2 and 3 as `card_wrap(self._table)` — consistent.
- `StyledTable.populate(rows: list[tuple[int, str]])` — existing API, called as `self._table.populate(list(enumerate(labels, 1)))` in Task 4 — `enumerate(labels, 1)` produces `(int, str)` tuples — consistent.
- `self._tree = self._styled_tree._tree` alias in Task 5 — all downstream uses of `self._tree` in the existing code remain valid `QTreeWidget` calls — consistent.
- `self._table_card.setVisible(True/False)` — set in Tasks 2 and 3, used in the same files — consistent.
