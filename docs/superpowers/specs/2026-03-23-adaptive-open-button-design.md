# Adaptive Open/Add PDF Button

**Date:** 2026-03-23
**Status:** Approved

## Problem

The current toolbar has two separate buttons: "Open" (replaces the active document) and "+ Add PDF" (opens in a new tab). The workflow for opening two PDFs is confusing: opening the first replaces any existing doc, and the second button is always visible even when there is nothing to "add to". Users have to open a file twice to arrive at a two-tab state.

## Goal

Replace both buttons with a single adaptive button that always opens files in tabs and changes its label/style based on whether any tab is currently open.

## Acceptance Criteria

- When no tabs are open, the button reads "Open PDF" and uses the neutral style.
- When one or more tabs are open, the button reads "+ Add PDF" and uses the green style.
- Clicking the button in either state opens a file dialog. Selecting a file opens it in a new tab (or switches to it if already open).
- The button updates immediately when a tab is opened or closed.
- No regression in existing tab behavior (deduplication, close, split view, etc.).

## Non-goals

- No changes to any tool other than `view_tool.py`.
- No changes to drag-and-drop behavior.
- No multi-file select in the dialog (out of scope).

## Design

### Button states

| State | Label | Background | Text color |
|---|---|---|---|
| No tabs | "Open PDF" | neutral (G100) | G700 |
| 1+ tabs | "+ Add PDF" | GREEN (#16A34A) | WHITE |

### Handler

Remove `_pick_pdf` and `_open_file_dialog`. Replace with a single `_open_or_add_pdf` method:

```python
def _open_or_add_pdf(self):
    p, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
    if p:
        self.open_file(p)
```

`open_file()` already handles tab creation, deduplication, and switching.

### State update

Add `_update_open_btn()` which reads `_tab_widget.count()` and sets the button label and stylesheet. Store a reference to the button as `self._open_btn`.

Connect `_update_open_btn` to:
- After each `open_file()` call completes (tab added)
- `_tab_widget.tabCloseRequested` (after the tab is removed)

### Files changed

| File | Change |
|---|---|
| `view_tool.py` | Remove `_pick_pdf`, `_open_file_dialog`. Add `_open_or_add_pdf`, `_update_open_btn`. Wire button and signals. |

## Testing

- Open app with no PDF: button reads "Open PDF", neutral style.
- Open a PDF: button changes to "+ Add PDF", green style.
- Click "+ Add PDF": second PDF opens in a new tab.
- Close all tabs: button reverts to "Open PDF", neutral style.
- Deduplication: opening the same file twice switches to the existing tab, does not create a duplicate.
