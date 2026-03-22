# View Tool: Multi-Document, Clickable Links, Reading Position Memory

**Date:** 2026-03-22
**Scope:** view_tool.py
**Status:** Approved

---

## Problem Statement

Three gaps in the current viewer cause users to reach for other applications:

1. Only one PDF can be open at a time — no tabs, no side-by-side comparison.
2. Links and URLs embedded in PDFs are not clickable.
3. The viewer does not remember what page you were on when you closed a file.

---

## Approach: Approach C — Lightweight `_RenderPane` Wrapper

Extract only the per-document rendering and navigation state into a thin `_RenderPane` widget. `ViewTool` becomes a host that manages a `QTabWidget` of `_RenderPane` instances and an optional `QSplitter` for split mode. The toolbar and annotation logic remain in `ViewTool` and route actions to whichever pane is currently active.

This is preferred over a full `DocumentPane` extraction (Approach A) because it is 4–6x less work, lower regression risk, and delivers the same user-visible behavior. It is preferred over multi-instance at the app shell level (Approach B) because it avoids duplicating the toolbar in split mode and keeps document management at the right layer.

---

## Feature 1: `_RenderPane`

### Responsibility

`_RenderPane` owns everything tied to one open file:

- `fitz.Document` reference and file path
- Current page index, zoom level (including `FIT_PAGE`/`FIT_WIDTH` sentinels), rotation
- `PDFCanvas` (the rendering canvas, extracted from `ViewTool`)
- Nav bar: prev/next buttons, page number entry, total pages label
- Undo/redo stack (moves out of `ViewTool` — it is per-document state)
- Search state: current match list, current match index
- Form overlay widgets
- Thumbnail strip
- Link rect cache for the current page (see Feature 2)

### What it does not own

Annotation tool selection, active color, stroke width, toolbar. These stay in `ViewTool`.

### Public interface

| Member | Description |
|---|---|
| `load(path: str)` | Open a fitz document; restore last page from LibraryState |
| `apply_tool_action(action)` | Called by the toolbar to perform an annotation action on the active page |
| `active_page: int` | Current page index (read-only property) |
| `path: str` | Path of the open file |
| `cleanup()` | Close fitz document; release resources |
| Signal `page_changed(int)` | Emitted on every page navigation |
| Signal `modified()` | Emitted after any annotation write |

---

## Feature 2: Tab Bar + Split View

### Layout

```
ViewTool (QWidget)
├── Toolbar (annotation tools, zoom, color, stroke — unchanged)
├── QTabBar  (one tab per open file + "+" button)
└── QSplitter (horizontal)
    ├── Left _RenderPane   (always present)
    └── Right _RenderPane  (visible only in split mode)
```

### Tab behavior

- Each tab maps to one `_RenderPane` instance kept alive while the tab is open.
- Switching tabs swaps which `_RenderPane` occupies the left splitter slot.
- Tab label is the filename (truncated). A `•` prefix indicates unsaved annotation changes.
- Right-click context menu: "Open in Split View", "Close", "Close Others".
- The `+` button opens a `QFileDialog` and loads the chosen file into a new tab.

### Split behavior

- A split button in the toolbar activates split mode. The splitter shows both panes at 50/50.
- The right pane opens the same file as the left by default.
- A tab can be dragged to the right pane, or right-clicked → "Open in Split View".
- A close (×) button on the right pane collapses back to single-pane mode.
- The two panes are fully independent: each has its own page, zoom, rotation, undo stack, and search state.

### Active pane

`ViewTool.active_pane` returns the most recently focused `_RenderPane`. All toolbar actions route through it. A thin colored border (brand blue) on the active pane provides visual confirmation of focus.

---

## Feature 3: Clickable Links

### Detection

After rendering each page, `_RenderPane` calls `fitz.Page.get_links()` and caches a list of `(fitz.Rect, link_dict)` pairs. This is metadata only — no additional rendering cost.

### Hover

`PDFCanvas.mouseMoveEvent` converts the cursor position to PDF coordinates and checks against the cached link rects. On a hit: cursor changes to `Qt.PointingHandCursor`. On miss: cursor returns to the active tool's cursor. A subtle highlight is drawn over the hovered link rect.

### Click

`PDFCanvas.mousePressEvent` checks link rects before passing the event to annotation tool logic. Link detection takes priority over annotation tools regardless of which tool is active — this matches standard PDF viewer behavior.

| Link kind | Action |
|---|---|
| `LINK_URI` | `QDesktopServices.openUrl(QUrl(uri))` — opens in system browser |
| `LINK_GOTO` | `_RenderPane.goto_page(link["page"])` — navigates within the same pane |
| `LINK_GOTOR`, `LINK_LAUNCH`, `LINK_NAMED` | Ignored; log warning at DEBUG level |

---

## Feature 4: Reading Position Memory

### Data model change

`LibraryState` adds one field to the per-file entry in `library.json`:

```json
{
  "/path/to/file.pdf": {
    "name": "file.pdf",
    "last_opened": "2026-03-22T10:00:00Z",
    "favorite": false,
    "trashed": false,
    "last_page": 12
  }
}
```

### Write path

`_RenderPane` emits `page_changed(int)` on every navigation. `ViewTool` handles this signal and calls `LibraryState.set_last_page(path, page)`. The existing 1-second debounced save batches the write — no additional flush logic required.

### Read path

`_RenderPane.load(path)` calls `LibraryState.get_last_page(path)` (returns `0` if not set) after the document is open and navigates to that page before the first render.

### Edge case

If the stored page index is out of range (file has been modified and is now shorter), clamp silently to `page_count - 1`.

---

## Architecture impact

| File | Change |
|---|---|
| `view_tool.py` | Extract `_RenderPane` from `ViewTool`; add `QTabBar`, `QSplitter`, `active_pane`; route toolbar actions through `active_pane` |
| `library_page.py` | Add `set_last_page()`, `get_last_page()` to `LibraryState`; add `last_page` field to JSON schema |
| `utils.py` | No changes |
| `tests/` | Add tests for `_RenderPane` interface, tab open/close, split mode, link click routing, last-page persistence |

---

## Non-goals

- Synchronized scrolling between split panes (panes are fully independent).
- `LINK_GOTOR` / `LINK_LAUNCH` / `LINK_NAMED` link handling (deferred).
- Drag-to-reorder tabs (deferred).
- Continuous scroll mode (separate feature, not in scope here).
- Remote/cloud file opening from the tab bar.

---

## Definition of done

- [ ] `_RenderPane` extracted; all existing viewer functionality passes existing tests.
- [ ] Tab bar: open, switch, close, unsaved-changes indicator.
- [ ] Split view: activate, open file in right pane, collapse.
- [ ] Clickable links: hover cursor, LINK_URI opens browser, LINK_GOTO navigates.
- [ ] Reading position restored on file open; clamped gracefully if out of range.
- [ ] `ruff format` + `ruff check` clean.
- [ ] Full test suite passes (`pytest`).
