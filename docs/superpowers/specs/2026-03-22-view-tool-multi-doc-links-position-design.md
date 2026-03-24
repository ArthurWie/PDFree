# View Tool: Multi-Document, Clickable Links, Reading Position Memory

**Date:** 2026-03-22
**Scope:** view_tool.py, library_page.py
**Status:** Approved

---

## Problem Statement

Three gaps in the current viewer cause users to reach for other applications:

1. Only one PDF can be open at a time — no tabs, no side-by-side comparison.
2. Links and URLs embedded in PDFs are not clickable.
3. The viewer does not remember what page you were on when you closed a file.

---

## Approach: Approach C — `_RenderPane` Wrapper

Extract the per-document rendering and navigation state into a `_RenderPane` widget. `ViewTool` becomes a host that manages a `QTabWidget` of `_RenderPane` instances and an optional `QSplitter` for split mode. The toolbar and annotation logic remain in `ViewTool` and route actions to whichever pane is currently active via `active_pane`.

This is preferred over a full `DocumentPane` extraction (Approach A) because it is 4–6x less work and lower regression risk. It is preferred over multi-instance at the app shell level (Approach B) because it avoids duplicating the full toolbar in split mode and keeps document management at the correct layer.

---

## Feature 1: `_RenderPane`

### Responsibility

`_RenderPane` owns everything tied to one open file:

- `fitz.Document` reference and file path
- `_render_worker: QThread | None` — reference to any in-flight render worker (used by `cleanup()`)
- Current page index, zoom level (including `FIT_PAGE`/`FIT_WIDTH` sentinels), rotation
- `PDFCanvas` (the rendering canvas, moved from `ViewTool`)
- Nav bar: prev/next buttons, page number entry, total pages label
- Undo/redo stack (moved from `ViewTool` — it is per-document state)
- Search state: query string, current match list, current match index
- Thumbnail strip (visible per-pane; each pane has its own strip in split mode)
- Link rect cache for the current page (see Feature 3)
- Form overlay widgets (relocated as-is from `ViewTool`; no behavioral changes in this spec)

### What it does not own

Annotation tool selection, active color, stroke width, toolbar, search panel UI. These stay in `ViewTool` and are routed to `active_pane`.

### Search panel placement

The search panel (Ctrl+F bar) remains in `ViewTool` but its state (query text, matches, current match index) is stored per-pane in `_RenderPane`. When the active pane changes, `ViewTool` reads the new pane's search state and refreshes the panel UI.

### Public interface

| Member | Type | Description |
|---|---|---|
| `load(path: str)` | method | Open a fitz document; restore last page via `LibraryState().get_last_page(path)`. On `fitz.FileDataError` or `OSError`, emits a `load_failed(str)` signal with the error message and leaves the pane in an unloaded state (no crash, no tab close). `ViewTool` handles `load_failed` by showing a `QMessageBox` and closing the tab. |
| `apply_annotation(tool: Tool, color: str, width: float, event_data: dict)` | method | Apply one annotation action. `tool` is the `Tool` enum defined in `view_tool.py` (same file, not imported from elsewhere). `event_data` carries geometry matching the existing per-tool convention in `ViewTool` (e.g. `{"rect": QRectF}` for highlight/rect/circle, `{"points": list[QPointF]}` for freehand, `{"p1": QPointF, "p2": QPointF}` for line/arrow). |
| `undo()` | method | Undo the last annotation action |
| `redo()` | method | Redo the last undone action |
| `can_undo: bool` | property | True if the undo stack is non-empty |
| `can_redo: bool` | property | True if the redo stack is non-empty |
| `active_page: int` | property (read-only) | Current zero-based page index |
| `page_count: int` | property (read-only) | Total pages in the open document |
| `path: str` | property (read-only) | Absolute path of the open file |
| `is_modified: bool` | property | True if there are unsaved annotation changes |
| `cleanup()` | method | Must be called from the main thread. If `_render_worker` is non-None, calls `_render_worker.wait(5000)` (5-second timeout). On timeout, logs a warning and proceeds. Then closes the fitz document and removes all form overlay widgets. |
| `page_changed(int)` | Signal | Emitted after every page navigation |
| `modified()` | Signal | Emitted after any annotation write |
| `load_failed(str)` | Signal | Emitted with an error message if `load()` fails to open the fitz document |

---

## Feature 2: Tab Bar + Split View

### Layout

```
ViewTool (QWidget)
├── Toolbar (annotation tools, zoom, color, stroke — unchanged)
├── QTabWidget  (tab bar + stacked _RenderPane widgets; single-pane mode)
│   ├── Tab 0 → _RenderPane
│   ├── Tab 1 → _RenderPane
│   └── ...  (+ button is the last tab)
└── [split mode only] QSplitter replaces QTabWidget in the layout:
    ├── Left slot  → active tab's _RenderPane (reparented from QTabWidget)
    └── Right slot → auxiliary _RenderPane (not in the tab list)
```

The toolbar always remains as a fixed child of `ViewTool` above the `QTabWidget`/`QSplitter` slot. Only the inner content slot (below the toolbar) is swapped between `QTabWidget` and `QSplitter` when entering/exiting split mode.

**Split mode reparenting:** When split mode activates, the active `_RenderPane` is removed from `QTabWidget` via `QTabWidget.removeTab()` and added to the left slot of the `QSplitter`. The `QTabWidget` is hidden. When split mode collapses, the left pane is re-inserted into `QTabWidget` at its original index via `QTabWidget.insertTab()`, the `QSplitter` is removed from the layout, and `QTabWidget` is shown again.

### Empty state

When no tabs are open, the `QTabWidget` is hidden and an empty-state widget (the existing "drop a file" zone, reused from the current `ViewTool` initial state) is shown in its place. The `+` tab button remains accessible via the toolbar or a dedicated "Open" button on the empty-state widget.

### Tab behavior

- Each tab maps to one `_RenderPane` instance kept alive while the tab is open.
- Switching tabs makes the selected `_RenderPane` the `active_pane` and refreshes the toolbar and search panel state.
- Tab label: filename without extension, truncated to 20 characters with an ellipsis. A `•` prefix indicates `is_modified == True`. Full path shown in a tooltip on hover.
- The `+` button opens a `QFileDialog` filtered to `*.pdf`. If the user cancels, nothing happens.
- If the user opens a file already open in another tab, that tab is focused instead of opening a duplicate.
- Keyboard shortcuts: `Ctrl+Tab` / `Ctrl+Shift+Tab` cycle tabs; `Ctrl+W` closes the active tab.
- Right-click context menu on a tab: "Open in Split View", "Close", "Close Others".

### Tab close flow

When a tab with `is_modified == True` is closed (via the × button, `Ctrl+W`, or context menu):

1. A `QMessageBox` prompts: "Save changes to [filename] before closing?" — Save / Discard / Cancel.
2. **Save** → save the document, then close the tab.
3. **Discard** → close the tab without saving.
4. **Cancel** → abort; the tab remains open.

When `is_modified == False`, the tab closes immediately with no prompt.

### Application quit with multiple unsaved panes

When the application receives a `QCloseEvent` (user closes the main window) and one or more panes have `is_modified == True`, `ViewTool` intercepts the event and shows a single aggregate dialog: "You have unsaved changes in [N] open document(s). Save all, discard all, or cancel?" — Save All / Discard All / Cancel. Save All saves each modified pane in sequence; any save failure aborts the quit and shows an error. Discard All closes without saving. Cancel leaves the application open.

### Maximum open tabs

No hard limit. Each open `_RenderPane` holds a `fitz.Document` (file handle + page cache). Users manage their own tabs; no automatic eviction is in scope.

### Split behavior

- A split button in the toolbar toggles split mode.
- On activation: `QTabWidget` is hidden, the active pane is reparented into the left slot of a new `QSplitter` at 50%, and a new auxiliary `_RenderPane` opens the same file in the right slot.
- The right pane is fully independent (own page, zoom, rotation, undo stack, search state).
- The right pane is not in the tab bar. Any tab can subsequently be loaded into the right pane via right-click → "Open in Split View", which replaces the right pane's document (calling `cleanup()` on the old right pane first).
- A `×` button on the right pane header collapses split mode: `cleanup()` is called on the right pane, the `QSplitter` is removed, the left pane is re-inserted into `QTabWidget`, and the `QTabWidget` is shown.
- If the user closes the tab currently in the left pane while split mode is active: the next tab (or previous if no next) becomes the left pane. If no tabs remain, split mode collapses automatically — `cleanup()` is called on the right pane, the `QSplitter` is removed, and the empty-state widget is shown.
- The right pane opens at page 0 (not `last_page`) since the user is opening it for side-by-side reference, not to resume reading. Duplicate file path deduplication uses `str(Path(path).resolve())` (canonical path) to handle case-insensitive filesystems.

### Active pane and `_modified` aggregate

`ViewTool.active_pane` returns the most recently focused `_RenderPane`. Clicking inside a pane sets it as active. A 2px border using `colors.BLUE` is drawn around the active pane when split mode is on; the border is not shown in single-pane mode.

`ViewTool._modified` (read by `main.py` via `getattr(tool, "_modified", False)`) returns `True` if **any** open `_RenderPane` (including the right split pane) has `is_modified == True`.

### ViewTool.cleanup()

`ViewTool.cleanup()` iterates over all `_RenderPane` instances (tab panes + the right split pane if present) and calls `cleanup()` on each before returning. This satisfies the existing contract with `main.py`.

---

## Feature 3: Clickable Links

### Detection

After rendering each page, `_RenderPane` calls `fitz.Page.get_links()` and caches a list of `(fitz.Rect, link_dict)` pairs for that page. The cache is rebuilt on every page change. No rendering cost. Both the left pane and the right split pane maintain their own link caches independently.

### Hover

`PDFCanvas.mouseMoveEvent` converts the cursor position to PDF coordinates and checks against the cached link rects:

- **Hit:** cursor changes to `Qt.PointingHandCursor`. A semi-transparent fill using `colors.BLUE` at 20% opacity is drawn over the link rect as a `QPainter` overlay — consistent with existing selection-highlight rendering. See `docs/DESIGN_STANDARDS.md` for color token usage rules.
- **Miss:** cursor returns to the current tool's cursor.

### Click priority

Link detection runs first in `PDFCanvas.mousePressEvent`, before any annotation tool handler. A link fires if and only if:

- The press position (in logical widget pixels) hits a link rect, **and**
- The mouse release position is within 4 logical pixels of the press position (i.e. a click, not a drag).

If the user presses on a link rect and then moves more than 4 logical pixels before release, the event is treated as a normal annotation drag and no link fires. This allows freehand and selection tools to function over link areas.

| Link kind | Action |
|---|---|
| `LINK_URI` | `QDesktopServices.openUrl(QUrl(uri))` — opens in the system browser |
| `LINK_GOTO` | `_RenderPane.goto_page(link["page"])` — navigates within the same pane |
| `LINK_GOTOR`, `LINK_LAUNCH`, `LINK_NAMED` | Ignored; `logging.debug("unhandled link: %s", link)` |

---

## Feature 4: Reading Position Memory

### Actual `library.json` schema

`files` is a list of dicts (not a dict keyed by path). The existing entry shape is:

```json
{
  "files": [
    {
      "path": "/path/to/file.pdf",
      "name": "file.pdf",
      "last_opened": "2026-03-22T10:00:00Z",
      "favorited": false,
      "trashed": false
    }
  ]
}
```

This spec adds `last_page` as an optional integer field to each entry. Files tracked before this change will not have the field; `get_last_page` returns `0` for absent entries.

### New LibraryState methods

| Method | Signature | Behavior |
|---|---|---|
| `set_last_page` | `(path: str, page: int) -> None` | Finds the entry with matching `path` and sets `last_page`. No-op if path is not in the library. Does not implicitly call `track()`. |
| `get_last_page` | `(path: str) -> int` | Returns `last_page` for the matching entry, or `0` if not found or field is absent. |

### Accessing LibraryState from _RenderPane

`LibraryState` is instantiated on demand throughout the codebase (`LibraryState()` reads from the shared JSON file at `_STATE_PATH`). `_RenderPane` follows the same pattern: call `LibraryState().get_last_page(path)` inside `load()` and call `LibraryState().set_last_page(path, page)` inside the `page_changed` handler in `ViewTool`. No reference needs to be injected.

**Important:** `set_last_page` is a no-op if the path is not yet tracked. Since `LibraryState().track(path)` is already called by `main.py` whenever a file is opened (`main.py:2170`), `last_page` will be set correctly in the normal flow. If the viewer is opened directly without going through `main.py`'s `_on_quick_start`, `set_last_page` will silently skip — acceptable behavior.

### Write path

`ViewTool` connects each `_RenderPane.page_changed(int)` signal **once at tab creation** (not on every active-pane switch) and calls `LibraryState().set_last_page(pane.path, page)`. The existing 1-second debounced save in `LibraryState` batches the write.

`set_last_page` updates `last_page` only for entries where `"trashed": false`. Trashed entries are not updated (they are effectively removed from the active library).

### Read path

`_RenderPane.load(path)` calls `LibraryState().get_last_page(path)` after the fitz document is open. If the returned index is `>= page_count`, clamp to `page_count - 1`. Navigate to the clamped page before the first render.

---

## Architecture impact

| File | Change |
|---|---|
| `view_tool.py` | Extract `_RenderPane`; add `QTabWidget`, `QSplitter`, `active_pane`, aggregate `_modified`; route toolbar and search through `active_pane`; update `cleanup()` to iterate all panes |
| `library_page.py` | Add `set_last_page()` and `get_last_page()` to `LibraryState`; `last_page` is optional (absent = 0) |
| `utils.py` | No changes |
| `docs/project-state/ARCHITECTURE.md` | Update module map and annotation system section to reflect `_RenderPane` and moved undo stack |
| `tests/` | New tests per Definition of Done |

---

## Non-goals

- Synchronized scrolling between split panes (fully independent).
- `LINK_GOTOR` / `LINK_LAUNCH` / `LINK_NAMED` link handling (deferred).
- Drag-to-reorder tabs (deferred).
- Continuous scroll mode (separate feature).
- Remote/cloud file opening from the tab bar.
- Maximum tab limit or automatic tab eviction.
- Behavioral changes to form overlay widgets (relocated as-is).

---

## Definition of done

- [ ] `_RenderPane` extracted; no regressions in the existing test suite (`pytest` passes with no new failures).
- [ ] Tab bar: open new tab via `+`, switch tabs, close tab with unsaved-changes prompt, `Ctrl+W` closes active tab, duplicate file open (by resolved canonical path) focuses existing tab, empty state shown when no tabs are open.
- [ ] `ViewTool._modified` is `True` if any open pane has `is_modified == True` (test: two panes, only one modified); `False` when all panes are unmodified.
- [ ] App quit with unsaved panes shows aggregate Save All / Discard All / Cancel dialog.
- [ ] `ViewTool.cleanup()` calls `cleanup()` on all panes including the right split pane; verified via `assert pane._doc.is_closed` after `ViewTool.cleanup()`.
- [ ] Split view: activate via toolbar button, right pane opens same file at page 0, both panes render independently (navigate to different pages, verify each pane's `active_page` is independent), closing right pane restores single-pane layout, left-pane tab close in split mode promotes next tab and calls `cleanup()` on the right pane if no tabs remain.
- [ ] Clickable links: `LINK_URI` calls `QDesktopServices.openUrl` (mock via `unittest.mock.patch("view_tool.QDesktopServices.openUrl")`); `LINK_GOTO` navigates to correct page; mouse drag starting on a link rect does not fire the link. Hover cursor (`Qt.PointingHandCursor`) verified via `PDFCanvas.cursor()` after synthetic `QMouseMoveEvent` over a link rect (manual check acceptable if headless environment prevents cursor inspection).
- [ ] Reading position: page is restored on reopen; out-of-range stored page clamps to `page_count - 1`; `get_last_page` on unknown path returns `0`; `set_last_page` on unknown path is a no-op (no exception, no new entry created); `set_last_page` on a trashed entry is a no-op.
- [ ] `page_changed` signal connected once per pane at creation; verified no double-fire when switching active pane.
- [ ] `docs/project-state/ARCHITECTURE.md` updated to reflect `_RenderPane` and moved undo stack.
- [ ] `ruff format` + `ruff check` clean.
- [ ] Full test suite passes (`pytest`).
