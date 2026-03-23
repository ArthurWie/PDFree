# Adaptive Open/Add PDF Button

**Date:** 2026-03-23
**Status:** Approved

## Problem

The current toolbar has two separate buttons: "Open" (replaces the active document) and "+ Add PDF" (opens in a new tab). The workflow for opening two PDFs is confusing: opening the first replaces any existing doc, and the second button is always visible even when there is nothing to "add to". Users have to open a file twice to arrive at a two-tab state.

## Goal

Replace both buttons with a single adaptive button that always opens files in tabs and changes its label/style based on whether any tab is currently open.

## Acceptance Criteria

- When no tabs are open, the button reads "Open PDF" and uses the neutral style (WHITE background, G300 border, G700 text).
- When one or more tabs are open, the button reads "+ Add PDF" and uses the green style (GREEN background, GREEN border, WHITE text).
- Clicking the button in either state opens a file dialog. Selecting a file opens it in a new tab (or switches to it if already open).
- The button updates immediately when a tab is opened or closed.
- No regression in existing tab behavior (deduplication, close, split view, etc.).

## Non-goals

- No changes to any file other than `view_tool.py`.
- No changes to drag-and-drop behavior.
- No multi-file select in the dialog (out of scope).

## Design

### Button states

| State | Label | Background | Border | Hover | Text color |
|---|---|---|---|---|---|
| No tabs | "Open PDF" | WHITE | G300 | G100 | G700 |
| 1+ tabs | "+ Add PDF" | GREEN (#16A34A) | GREEN | #15803D | WHITE |

### Handler

Remove `_pick_pdf`, `_open_file_dialog`, and `_add_pdf`. Replace with a single `_open_or_add_pdf` method:

```python
def _open_or_add_pdf(self):
    p, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
    if p:
        self.open_file(p)
```

`open_file()` already handles tab creation, deduplication, and switching.

Note: `_add_pdf` (line ~3008) has a fallback call to `_pick_pdf` on its first line that must also be removed. Remove `_add_pdf` entirely.

### State update

Add `_update_open_btn()` which reads `_tab_widget.count()` and updates the button label and stylesheet. Store a reference to the button as `self._open_btn`.

```python
def _update_open_btn(self):
    has_tabs = self._tab_widget.count() > 0
    if has_tabs:
        self._open_btn.setText("+ Add PDF")
        self._open_btn.setStyleSheet(
            f"QPushButton {{ background: {GREEN}; color: {WHITE}; "
            f"border: 1px solid {GREEN}; border-radius: 8px; "
            f"font: bold 13px 'Segoe UI'; padding: 0 16px; }}"
            f"QPushButton:hover {{ background: #15803D; }}"
        )
    else:
        self._open_btn.setText("Open PDF")
        self._open_btn.setStyleSheet(
            f"QPushButton {{ background: {WHITE}; color: {G700}; "
            f"border: 1px solid {G300}; border-radius: 8px; "
            f"font: 13px 'Segoe UI'; padding: 0 16px; }}"
            f"QPushButton:hover {{ background: {G100}; }}"
        )
```

#### When to call `_update_open_btn`

- As the **last statement inside `open_file()`**, after `_tab_widget.addTab()` and `pane.load()`.
- As the **last statement inside `_close_tab()`**, after the tab is removed. Do NOT connect to `tabCloseRequested` directly — that signal fires before the tab is removed, so the count would be wrong.
- During `__init__`, after the button is created, to set the initial state.

#### `initial_path` at construction time

When `ViewTool` is constructed with `initial_path`, the current code calls `_load_pdf()` directly, bypassing `open_file()` and the tab widget. Route this through `open_file()` instead:

```python
# in __init__, replace:
if initial_path:
    self._load_pdf()  # old

# with:
if initial_path:
    self.open_file(initial_path)  # new
```

This ensures the button reflects the correct state immediately after construction.

#### Split view

When the splitter is active, `_activate_split` and `_deactivate_split` may add/remove items from `_tab_widget` internally. The button should **not** be reconnected to any split-view signals. The button state is driven only by `open_file()` and `_close_tab()` as described above. In split mode the button will retain whatever label it had before entering split view, which is acceptable.

### Corner "+" button

The `+` button in the tab bar corner (`add_tab_btn`, currently connected to `_open_file_dialog`) must be re-connected to `_open_or_add_pdf`:

```python
add_tab_btn.clicked.connect(self._open_or_add_pdf)
```

### Files changed

| File | Change |
|---|---|
| `view_tool.py` | Remove `_pick_pdf`, `_open_file_dialog`, `_add_pdf`. Add `_open_or_add_pdf`, `_update_open_btn`. Call `_update_open_btn()` in `__init__` after button creation, at end of `open_file()`, and at end of `_close_tab()`. Route `initial_path` through `open_file()`. Re-connect corner `+` button. |

## Testing

- Open app with no PDF: button reads "Open PDF", neutral style (white bg, grey border).
- Open a PDF: button changes to "+ Add PDF", green style.
- Click "+ Add PDF": second PDF opens in a new tab.
- Close all tabs: button reverts to "Open PDF", neutral style.
- Deduplication: opening the same file twice switches to the existing tab, no duplicate.
- Corner `+` button: same behavior as clicking the toolbar button.
- `initial_path`: launch ViewTool with a path pre-set; button should read "+ Add PDF" immediately.
- Split view non-regression: activating and deactivating split view does not change the button label unexpectedly.
