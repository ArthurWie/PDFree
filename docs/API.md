# Internal Module API

PDFree is a desktop application with no HTTP API. This document describes the public-facing interface of each module — the classes and functions that other modules call. Internal/private methods (prefixed `_`) are not listed here; see the source file directly for those.

---

## colors.py

Pure constant module. Import individual tokens by name.

```python
from colors import BLUE, RED, G200, BRAND, ...
```

All tokens are hex color strings. See `docs/DESIGN_STANDARDS.md` for the semantic usage of each token. See the module itself for the full list.

---

## icons.py

```python
from icons import svg_pixmap, svg_icon, is_svg_icon
```

### `is_svg_icon(name: str) → bool`
Returns `True` if `name` is a known Lucide icon in the internal registry.

```python
is_svg_icon("scissors")  # True
is_svg_icon("garbage")   # False
```

### `svg_pixmap(name: str, color: str = "#374151", size: int = 20) → QPixmap`
Renders a Lucide icon to a `QPixmap` of `size × size` pixels.
- `name`: icon name from `_SVGS` dict (e.g. `"scissors"`, `"upload"`, `"check"`)
- `color`: any valid CSS hex color string
- `size`: pixel size (same for width and height)
- Result is cached by `(name, color, size)`.

```python
px = svg_pixmap("upload", "#FFFFFF", 15)
label.setPixmap(px)
```

### `svg_icon(name: str, color: str = "#374151", size: int = 20) → QIcon`
Same as `svg_pixmap` but returns a `QIcon`. Use for `QPushButton.setIcon()` and `QAction`.

```python
btn.setIcon(svg_icon("scissors", BLUE, 16))
```

---

## utils.py

```python
from utils import _fitz_pix_to_qpixmap, _make_back_button, _WheelToHScroll
```

### `_fitz_pix_to_qpixmap(pix) → QPixmap`
Converts a `fitz.Pixmap` (RGB, 8-bit) to a `QPixmap`.
- Handles both `pix.samples_mv` (memoryview, newer PyMuPDF) and `pix.samples` (bytes, older).
- The returned `QPixmap` owns its data (`.copy()` is called).

```python
pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
qpix = _fitz_pix_to_qpixmap(pix)
label.setPixmap(qpix)
```

### `_make_back_button(text: str, callback, color: str = G700) → QPushButton`
Factory that returns a styled back-navigation button with an `arrow-left` icon.
- `text`: label shown next to the arrow (e.g. `"Back"`)
- `callback`: callable connected to `clicked` signal
- `color`: icon and text color (default `G700`)
- Fixed height: 36 px. Transparent background with `G100` hover.

```python
btn = _make_back_button("Back to Home", self._go_home)
```

### `_WheelToHScroll(QObject)`
Event filter that routes vertical wheel events on a `QScrollArea` viewport to its horizontal scrollbar. Used on all thumbnail strip scroll areas.

```python
self._wheel_filter = _WheelToHScroll(scroll_area)
```

The filter is installed automatically in `__init__`. Keep a reference to prevent garbage collection.

---

## library_page.py

The `LibraryState` class is the only public interface other modules need. The widget classes (`HeroBanner`, `FolderCard`, etc.) are used internally by `main.py` and are not consumed by tool modules.

```python
from library_page import LibraryState
```

### `LibraryState(on_dirty=None)`
Constructor.
- `on_dirty`: optional callable invoked whenever the state changes (for triggering UI refreshes).

### `LibraryState.track(path: str) → None`
Record that a file was opened. Creates a new entry or updates `last_opened` if the path already exists.

### `LibraryState.set_favorite(path: str, val: bool) → None`
Set or clear the favorite flag on a tracked file.

### `LibraryState.trash(path: str) → None`
Soft-delete a file (sets `trashed = True`).

### `LibraryState.restore(path: str) → None`
Un-trash a file.

### `LibraryState.delete_permanently(path: str) → None`
Remove a file entry from the library entirely.

### `LibraryState.add_folder(folder_path: str) → bool`
Start tracking a filesystem folder. Returns `True` if added, `False` if already tracked.

### `LibraryState.delete_folder(folder_path: str) → None`
Stop tracking a folder. Does not delete files on disk.

### `LibraryState.folder_color(folder_path: str) → str`
Returns the hex color assigned to the folder.

### `LibraryState.all_active(q: str = "") → list[dict]`
Returns all non-trashed file entries, optionally filtered by substring query `q`.

### `LibraryState.recent(n: int = 20, q: str = "") → list[dict]`
Returns the `n` most recently opened files (by `last_opened`), optionally filtered.

### `LibraryState.favorites(q: str = "") → list[dict]`
Returns all favorited, non-trashed files, optionally filtered.

### `LibraryState.trashed() → list[dict]`
Returns all trashed file entries.

### `LibraryState.in_folder(folder_path: str, q: str = "") → list[dict]`
Scans `folder_path` on disk for `.pdf` files, cross-references with tracked entries, returns combined dicts. Files not yet tracked appear with `last_opened = None`.

### `LibraryState.folder_stats(folder_path: str) → tuple[int, int]`
Returns `(pdf_count, total_size_bytes)` by scanning the folder on disk.

### `LibraryState.folders() → list[dict]`
Returns all tracked folder entries.

### `LibraryState.data` (property) `→ dict`
Returns the raw in-memory state dict. Shape: `{"files": [...], "folders": [...]}`. Prefer the query methods over direct access.

---

## Tool Widget Contract

Every tool widget (`ViewTool`, `SplitTool`, `ExcerptTool`, `PDFtoCSVTool`) must satisfy the following interface to integrate with `main.py`:

### `cleanup() → None`
Called by `PDFreeApp` before the widget is removed from the stacked widget. Must close all open `fitz.Document` objects and release resources.

### `_modified: bool` (instance attribute, optional)
If `True`, `PDFreeApp` will prompt the user to save before navigating away. Tools that write directly to disk on action (SplitTool, PDFtoCSVTool) do not need this.

### Constructor signature
```python
def __init__(self, parent=None):
```
No other arguments. If a tool needs a file path at startup, expose a `load_file(path: str)` method that `main.py` calls after instantiation.

---

## main.py — PDFreeApp Signals (consumed by child widgets)

### `file_selected` (QuickStartZone signal) `→ str`
Emitted when the user drops or browses a file in the Quick-Start zone. Carries the absolute file path.

### `open_req` (HeroBanner/library signal) `→ str`
Emitted when the library requests that a file be opened in a tool. `PDFreeApp` handles this by calling `_open_tool("view")` and passing the path to the viewer.
