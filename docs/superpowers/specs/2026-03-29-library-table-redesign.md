# Library Table Redesign — Design Spec

## Goal

Replace `_FileTableRow` and `_build_file_table()` in `library_page.py` with a redesigned `StyledTable` (QTableWidget-based) that matches the card-style table design. Fix the checkbox-disappearing bug. Columns: Name, Date Modified (filesystem), Size, Favorite (star), Menu (···).

---

## Background

The current library table uses a custom `_FileTableRow(QFrame)` per row, assembled vertically inside a container returned by `_build_file_table()`. The new implementation uses a single `QTableWidget`-based `StyledTable` component (already created in `styled_table.py`) with per-row cell widgets for the interactive columns (star, menu).

---

## Checkbox Bug Fix

**Root cause:** `setSelectionBehavior(SelectRows)` consumes row clicks before `ItemIsUserCheckable` can toggle the checkbox, causing the checkbox to visually vanish (the item is deselected by the click event before it renders as checked).

**Fix:** Connect `cellClicked(row, col)` on the table. When `col == 0`, manually toggle the check state of the item and emit `toggle_sel`. Disconnect Qt's own selection behavior from col 0 clicks by overriding `mousePressEvent` to skip the default selection when the click lands in column 0.

---

## File Map

| Path | Action | Responsibility |
|---|---|---|
| `styled_table.py` | Modify | Add library columns, signals, star/menu cell widgets, checkbox fix |
| `library_page.py` | Modify | Replace `_FileTableRow` instantiation and `_build_file_table()` with `StyledTable` |

`_FileTableRow` class definition (lines 870–1072) is removed entirely once replaced.

---

## StyledTable Changes

### New signals

```python
open_req = Signal(str)      # path — row double-clicked
toggle_sel = Signal(str, bool)  # path, checked — checkbox toggled
toggle_fav = Signal(str, bool)  # path, new_state — star clicked
```

### New method: `populate_library(entries)`

Accepts the same entry dicts used throughout `LibraryPage`:

```python
{
    "path": str,
    "name": str,
    "size": int,          # bytes
    "favorited": bool,
    "trashed": bool,
}
```

Date modified is read at populate time via `os.path.getmtime(entry["path"])` — returns float epoch, formatted as `"Mar 28, 2026"` using `datetime.fromtimestamp()`. If the file does not exist, display `"—"`.

### Column layout

| Col | Header | Resize mode | Width | Content |
|---|---|---|---|---|
| 0 | *(empty)* | Fixed | 40 px | Checkbox item (`ItemIsUserCheckable`) |
| 1 | Name | Stretch | — | Bold text, dark (`G800`) |
| 2 | Date Modified | Fixed | 160 px | Formatted date string, `G600` |
| 3 | Size | Fixed | 100 px | Formatted size string (`_fmt_size`), right-aligned, `G600` |
| 4 | ★ | Fixed | 48 px | `setCellWidget` — star `QPushButton` |
| 5 | ··· | Fixed | 40 px | `setCellWidget` — menu `QPushButton` |

Row height: 48 px (matching existing `_FileTableRow.ROW_H`).

### Star cell widget

- Amber `★` (U+2605) when favorited, gray `☆` (U+2606) when not
- Colors: `AMBER` (#F59E0B) when favorited, `G300` (#D1D5DB) when not
- Hover: `AMBER` color, `AMBER_BG` (#FEF3C7) background, `border-radius: 6px`
- Clicking emits `toggle_fav(path, new_state)` and updates button appearance in-place
- Font size: 15px, button fixed size 28×28 px, centered in cell

### Menu cell widget (`···`)

Same actions as the current `_FileTableRow._show_menu()`:

```
Open
Show in Explorer
Add to Favorites / Remove from Favorites   ← toggles based on current state
─────────────────────────────────────────
Move to Trash
```

QMenu styled with `WHITE` background, `G200` border, `border-radius: 8px`, item padding `6px 20px`, `G700` text, `G100` selected background.

Menu popup anchored to the bottom-left of the ··· button.

### Double-click to open

Connect `cellDoubleClicked(row, col)` — emit `open_req(path)` for any column except col 0 (checkbox) and col 4/5 (star/menu — their own click handlers apply).

### Checkbox behavior

`cellClicked(row, col)`:
- If `col == 0`: toggle `CheckState` on item, emit `toggle_sel(path, checked)`
- Otherwise: no-op for checkbox logic (selection model handles row highlight)

Override `mousePressEvent` in `StyledTable` to call `super()` only when the click is not in col 0, preventing row selection from consuming the checkbox click.

---

## LibraryPage Changes

### Replace `_build_file_table(files)`

Current: creates `_FileTableRow` instances, returns a container `QFrame`.

New: returns a `StyledTable` instance after calling `populate_library(files)`.

```python
def _build_file_table(self, files: list[dict]) -> StyledTable:
    table = StyledTable()
    table.open_req.connect(self._open_file)
    table.toggle_sel.connect(self._on_toggle_sel)
    table.toggle_fav.connect(self._on_toggle_fav)
    table.populate_library(files)
    return table
```

The return value is used exactly as the container QFrame was — inserted into the page layout.

### Remove `_FileTableRow`

The entire `_FileTableRow` class (lines 870–1072) is deleted. No other file imports it.

### Signal handlers — unchanged

`_open_file`, `_on_toggle_sel`, `_on_toggle_fav` in `LibraryPage` remain byte-for-byte identical. No changes needed.

---

## Date Modified Formatting

```python
import os
from datetime import datetime

def _fmt_mtime(path: str) -> str:
    try:
        ts = os.path.getmtime(path)
        return datetime.fromtimestamp(ts).strftime("%b %-d, %Y")
    except OSError:
        return "—"
```

Windows does not support `%-d` (no leading zero). Use `"%b %#d, %Y"` on Windows or strip manually:

```python
dt = datetime.fromtimestamp(ts)
return dt.strftime("%b ") + str(dt.day) + dt.strftime(", %Y")
```

---

## Size Formatting

Reuse the existing `_fmt_size(n)` already defined at the top of `library_page.py` (or copy it into `styled_table.py` as a private helper).

---

## Testing

Existing tests: `tests/test_styled_table.py` (16 tests) — all must continue to pass.

New tests to add in `tests/test_styled_table.py`:

| Test | What it checks |
|---|---|
| `test_library_column_count` | `columnCount() == 6` after `populate_library` |
| `test_library_row_count` | row count matches entry list length |
| `test_library_name_bold` | col 1 item font is bold |
| `test_library_date_missing_file` | missing file path yields `"—"` in col 2 |
| `test_library_size_formatted` | 1536 bytes → `"1.5 KB"` in col 3 |
| `test_library_star_widget_present` | col 4 cell widget is a `QPushButton` |
| `test_library_menu_widget_present` | col 5 cell widget is a `QPushButton` |
| `test_checkbox_toggles_on_cell_click` | clicking col 0 toggles check state |
| `test_toggle_sel_signal_emitted` | `toggle_sel` signal fires with correct path and state |
| `test_toggle_fav_signal_emitted` | clicking star button emits `toggle_fav` |

---

## Non-goals

- Sorting by column (not requested)
- Drag-and-drop reordering (not requested)
- Pagination (not requested)
- Any changes to `LibraryState`, `library.json` schema, or folder logic
- Any changes to the 3-card recent strip above the table
