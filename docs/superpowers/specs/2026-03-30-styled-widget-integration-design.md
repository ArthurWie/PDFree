# Styled Widget Integration Design

**Date:** 2026-03-30

## Goal

Integrate `StyledTree` and `StyledTable` into the four tools that currently use raw `QTreeWidget` or `QTableWidget`, and apply consistent card styling to the two tools whose column structures don't fit the existing components.

---

## Scope

| Tool | File | Change | Component |
|---|---|---|---|
| Bookmarks | `bookmarks_tool.py` | Full swap | `StyledTree` replaces `QTreeWidget` |
| Page Labels | `page_labels_tool.py` | Full swap | `StyledTable` replaces `QTableWidget` |
| Font Info | `font_info_tool.py` | Card wrap | `card_wrap()` wraps existing `QTreeWidget` |
| Form Export | `form_export_tool.py` | Card wrap | `card_wrap()` wraps existing `QTreeWidget` |

---

## Architecture

### card_wrap() utility — `widgets.py`

A new module-level function added to `widgets.py`:

```python
def card_wrap(widget: QWidget, parent=None) -> QWidget:
```

- Returns a `QWidget` with a `QVBoxLayout` (zero margins, zero spacing) containing `widget`
- Card styling applied to the outer wrapper: `background: #FFFFFF`, `border: 1px solid G200`, `border-radius: 8px`
- Header QSS applied directly to `widget` via `setStyleSheet`:
  - `QHeaderView::section`: `G100` background, `G700` text, `G200` bottom border, no other borders, 8px padding — matches `StyledTable` header appearance
- The inner widget's own border is set to `none` so the card border is the only visible border

### BookmarksTool → StyledTree

**What changes:**
- `self._tree: QTreeWidget` → `self._styled_tree: StyledTree`; the underlying `QTreeWidget` is accessed via `self._styled_tree._tree`
- `_refresh_tree` converts the flat `[level, title, page]` TOC into a nested `_NodeData` tree using the same stack-based algorithm, then calls `self._styled_tree.populate(roots)`
- Bookmark entries that have children use `is_folder=True` (folder icon, expand/collapse, col 1 left empty)
- Bookmark entries with no children use `is_folder=False` (document icon, page number shown in col 1, `raw_label` set to the page number string)
- `page` is stored as `_NodeData.page: int` on all entries so `selection_changed` emits it and the edit panel can read it
- `currentItemChanged` is connected on `self._styled_tree._tree` (the underlying `QTreeWidget`) — the edit panel reads `_NodeData.page` from `item.data(0, Qt.ItemDataRole.UserRole)`
- Up/Down/Remove buttons still call `self._styled_tree._tree.currentItem()`
- The existing custom `setStyleSheet` on the old `QTreeWidget` is removed — `StyledTree` handles styling

**What does not change:**
- Column count stays 2 (label col 2 = title, col 1 = page number)
- TOC data source, `_FontInfoWorker`, edit panel, save logic — untouched
- Signal names and handler method signatures

### PageLabelsTool → StyledTable

**What changes:**
- `self._table: QTableWidget` → `self._styled_table: StyledTable`
- `_refresh_preview` calls `self._styled_table.populate(list(zip(range(1, n+1), labels)))` — the `compute_labels()` output maps directly to the `(int, str)` tuple format `StyledTable.populate()` already accepts
- The existing `setStyleSheet` and row-by-row population loop are removed
- `StyledTable.selection_changed` signal is not connected — checkbox selection is a visual bonus with no action in this tool

**What does not change:**
- `compute_labels()`, range spin boxes, style combos, prefix entry, Apply Labels button — untouched

### FontInfoTool — card_wrap()

**What changes:**
- `self._tree` construction and all columns/signals stay identical
- The existing `setStyleSheet` call on `self._tree` is removed
- `card_wrap(self._tree)` is passed to the layout instead of `self._tree` directly

**What does not change:**
- Column definitions, sort behavior, population logic, export buttons — untouched

### FormExportTool — card_wrap()

Same pattern as FontInfoTool:
- Existing `setStyleSheet` removed
- `card_wrap(self._tree)` added to layout
- Everything else untouched

---

## Testing Strategy

- Existing tests for all four tools must continue to pass with no modifications
- New unit tests cover `card_wrap()`: verifies the returned widget has the correct stylesheet and contains the passed widget as a child
- New integration smoke tests for `BookmarksTool` and `PageLabelsTool`: populate with sample data and verify the underlying tree/table row counts and item data match expectations
- No tests are skipped or modified to pass

---

## Non-Goals

- Making `StyledTable` generic (arbitrary column counts) — deferred
- Wiring `StyledTable.selection_changed` in `PageLabelsTool` to any action — deferred
- Adding checkboxes to `FontInfoTool` or `FormExportTool` — deferred
- Any changes to export logic, worker threads, or PDF parsing — out of scope
