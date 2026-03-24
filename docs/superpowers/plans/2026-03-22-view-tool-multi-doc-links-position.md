# View Tool: Multi-Document, Links, Reading Position — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tabs + split view, clickable links, and per-file reading position memory to the PDF viewer.

**Architecture:** Extract per-document state into a `_RenderPane(QWidget)` class inside `view_tool.py`. `ViewTool` becomes a host that wraps one or more `_RenderPane` instances in a `QTabWidget` and optional `QSplitter`. `PDFCanvas` gains a reference to `_RenderPane` for render state and calls back to `ViewTool` for toolbar/tool state. `LibraryState` gains `set_last_page` / `get_last_page`.

**Tech Stack:** Python 3.11, PySide6 (`QTabWidget`, `QSplitter`, `QTabBar`), PyMuPDF (`fitz.Page.get_links()`), `QDesktopServices`, `pytest`

**Spec:** `docs/superpowers/specs/2026-03-22-view-tool-multi-doc-links-position-design.md`

---

## Pre-flight: Baseline

Before touching any code, run the full test suite and record the count.

- [ ] Run `pytest --tb=short -q` from the project root. All tests must pass. Record the passing count.
- [ ] If any tests fail, stop and fix them before continuing.

---

## File Map

| File | What changes |
|---|---|
| `view_tool.py` | Add `_RenderPane` class; refactor `ViewTool` to use it; add `QTabWidget`, `QSplitter`, link detection, position restore |
| `library_page.py` | Add `set_last_page()` and `get_last_page()` to `LibraryState` |
| `tests/test_library_state.py` | Add tests for new `LibraryState` methods |
| `tests/test_render_pane.py` | New: tests for `_RenderPane` interface |
| `tests/test_view_tabs.py` | New: tests for tab management and close flow |
| `tests/test_view_split.py` | New: tests for split view |
| `tests/test_view_links.py` | New: tests for clickable link routing |
| `tests/test_view_position.py` | New: tests for last-page persistence |
| `docs/project-state/ARCHITECTURE.md` | Update module map and annotation section |
| `docs/project-state/FEATURES.md` | Append new features per CLAUDE.md protocol |
| `docs/CHANGELOG.md` | Add entry for each change per CLAUDE.md protocol |

---

## Task 1: LibraryState — `set_last_page` / `get_last_page`

This task is fully independent of the viewer refactor and should be done first.

**Files:**
- Modify: `library_page.py` (after the `set_favorite` method, around line 221)
- Test: `tests/test_library_state.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_library_state.py`:

```python
def test_get_last_page_unknown_path(state):
    assert state.get_last_page("/does/not/exist.pdf") == 0


def test_get_last_page_absent_field(state, tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"%PDF-1.4")
    state.track(str(p))
    # Entry exists but no last_page field yet
    assert state.get_last_page(str(p)) == 0


def test_set_last_page_updates(state, tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"%PDF-1.4")
    state.track(str(p))
    state.set_last_page(str(p), 5)
    assert state.get_last_page(str(p)) == 5


def test_set_last_page_unknown_is_noop(state):
    # Must not raise and must not create an entry
    state.set_last_page("/does/not/exist.pdf", 3)
    assert state.get_last_page("/does/not/exist.pdf") == 0


def test_set_last_page_trashed_is_noop(state, tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"%PDF-1.4")
    state.track(str(p))
    state.trash(str(p))
    state.set_last_page(str(p), 7)
    # Assert immediately — while still trashed — that the write was skipped
    assert state.get_last_page(str(p)) == 0
    # Also verify after restore that the field was never set
    state.restore(str(p))
    assert state.get_last_page(str(p)) == 0
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_library_state.py::test_get_last_page_unknown_path tests/test_library_state.py::test_set_last_page_updates -v
```

Expected: `AttributeError: 'LibraryState' object has no attribute 'get_last_page'`

- [ ] **Step 3: Implement the two methods in `library_page.py`**

Add after `set_favorite` (around line 228):

```python
def get_last_page(self, path: str) -> int:
    """Return the last-viewed page index for path, or 0 if unknown."""
    path = str(Path(path).resolve())
    for e in self._data["files"]:
        if e["path"] == path:
            return e.get("last_page", 0)
    return 0

def set_last_page(self, path: str, page: int) -> None:
    """Persist the last-viewed page for path. No-op if path not tracked or trashed."""
    path = str(Path(path).resolve())
    for e in self._data["files"]:
        if e["path"] == path and not e.get("trashed", False):
            e["last_page"] = page
            self._request_save()
            return
```

- [ ] **Step 4: Run the new tests**

```
pytest tests/test_library_state.py -v
```

Expected: all pass including the 5 new tests.

- [ ] **Step 5: Run full suite to check for regressions**

```
pytest --tb=short -q
```

Expected: same pass count as baseline.

- [ ] **Step 6: Commit**

```bash
git add library_page.py tests/test_library_state.py
git commit -m "feat: add set_last_page / get_last_page to LibraryState"
```

---

## Task 2: `_RenderPane` — state container + public interface

Create `_RenderPane` as a `QWidget` in `view_tool.py`. This task migrates per-document **state variables** from `ViewTool.__init__` into `_RenderPane.__init__`. The rendering widgets (`PDFCanvas`, nav bar, thumbnail strip) stay in `ViewTool` for now and will move in Task 3. `ViewTool` creates `self._pane = _RenderPane(self)` and accesses per-doc state through it.

**Key insight:** `_RenderPane` holds state; `ViewTool._pane` holds the current active pane. After this task, `ViewTool` works identically to before — all existing tests pass.

**Files:**
- Modify: `view_tool.py`
- Test: `tests/test_render_pane.py` (new)

- [ ] **Step 1: Write the failing interface test**

Create `tests/test_render_pane.py`:

```python
"""Tests for _RenderPane public interface."""
import sys
import pytest


def _get_or_create_app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="module")
def qapp():
    return _get_or_create_app()


def test_render_pane_class_exists():
    from view_tool import _RenderPane  # noqa: F401


def test_render_pane_interface(qapp):
    from view_tool import ViewTool
    vt = ViewTool()
    pane = vt.active_pane
    assert pane is not None
    # State properties
    assert hasattr(pane, "active_page")
    assert hasattr(pane, "page_count")
    assert hasattr(pane, "is_modified")
    assert hasattr(pane, "can_undo")
    assert hasattr(pane, "can_redo")
    assert hasattr(pane, "path")
    # Methods
    assert callable(getattr(pane, "cleanup", None))
    assert callable(getattr(pane, "undo", None))
    assert callable(getattr(pane, "redo", None))
    vt.cleanup()


def test_render_pane_defaults(qapp):
    from view_tool import ViewTool
    vt = ViewTool()
    pane = vt.active_pane
    assert pane.active_page == 0
    assert pane.page_count == 0
    assert pane.is_modified is False
    assert pane.can_undo is False
    assert pane.can_redo is False
    assert pane.path == ""
    vt.cleanup()


def test_viewtool_modified_delegates_to_pane(qapp):
    from view_tool import ViewTool
    vt = ViewTool()
    assert vt._modified is False
    vt.active_pane._is_modified = True
    assert vt._modified is True
    vt.cleanup()
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_render_pane.py -v
```

Expected: `ImportError` or `AttributeError` — `_RenderPane` does not exist yet.

- [ ] **Step 3: Add `_RenderPane` class to `view_tool.py`**

Add this class **before** `ViewTool` (around line 920). It is a thin container for per-document state:

```python
class _RenderPane(QWidget):
    """Per-document state container for ViewTool."""

    page_changed = Signal(int)
    modified = Signal()
    load_failed = Signal(str)

    def __init__(self, view_tool):
        super().__init__(view_tool)
        self._view_tool = view_tool  # back-reference for toolbar state

        # Document
        self._doc = None
        self._path = ""
        self._page_count = 0
        self._current_page = 0
        self._zoom = FIT_PAGE
        self._rotation = 0
        self._is_modified = False

        # Undo / Redo
        self._undo_stack: list[tuple] = []
        self._redo_stack: list[tuple] = []

        # Search state
        self._search_results: list[tuple] = []
        self._search_flat: list[tuple] = []
        self._search_idx = -1

        # Form overlay widgets
        self._form_widgets: list = []

        # Thumbnail state
        self._thumb_frames: list = []
        self._thumb_cache: collections.OrderedDict = collections.OrderedDict()
        self._highlighted_thumb_idx: int = -1
        self._thumb_render_next = 0
        self._thumb_timer = None

        # Link cache (populated after each page render)
        self._link_cache: list[tuple] = []  # [(fitz.Rect, link_dict), ...]

        # Async render
        self._render_gen = 0
        self._render_worker = None  # QThread ref for cleanup

    # ---- Public interface -------------------------------------------------

    @property
    def active_page(self) -> int:
        return self._current_page

    @property
    def page_count(self) -> int:
        return self._page_count

    @property
    def is_modified(self) -> bool:
        return self._is_modified

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    @property
    def path(self) -> str:
        return self._path

    def undo(self):
        self._view_tool._undo()

    def redo(self):
        self._view_tool._redo()

    def cleanup(self):
        """Close fitz document and release resources. Call from main thread."""
        self._render_gen = -1
        # _RenderWorker is a QRunnable (not QThread), so use a completion flag.
        # Set _render_gen = -1 (done above) so any in-flight worker skips its
        # done-callback. Then wait up to 5 s for the thread pool to drain.
        if self._render_worker is not None:
            if not QThreadPool.globalInstance().waitForDone(5000):
                logger.warning("render worker did not finish in 5 s — proceeding")
            self._render_worker = None
        for w in list(self._form_widgets):
            w.setParent(None)
            w.deleteLater()
        self._form_widgets.clear()
        if self._doc is not None:
            self._doc.close()
            self._doc = None
```

- [ ] **Step 4: Update `ViewTool.__init__` to create `self._pane` and delegate**

In `ViewTool.__init__`, after the state variables block (around line 1013), add:

```python
self._pane = _RenderPane(self)
```

Add `active_pane` property and update `_modified` to aggregate:

```python
@property
def active_pane(self) -> "_RenderPane":
    return self._pane

@property
def _modified(self) -> bool:
    return self._pane.is_modified

@_modified.setter
def _modified(self, val: bool):
    self._pane._is_modified = val
```

Then replace direct state accesses in `ViewTool` methods:
- `self.doc` → `self._pane._doc` (and keep `self.doc` as a property: `return self._pane._doc`)
- `self.total_pages` → `self._pane._page_count` (keep property)
- `self.current_page` → `self._pane._current_page` (keep property)
- `self.zoom` → `self._pane._zoom` (keep property)
- `self._rotation` → `self._pane._rotation`
- `self._undo_stack` → `self._pane._undo_stack`
- `self._redo_stack` → `self._pane._redo_stack`
- `self._search_results` → `self._pane._search_results`
- `self._search_flat` → `self._pane._search_flat`
- `self._search_idx` → `self._pane._search_idx`
- `self._form_widgets` → `self._pane._form_widgets`
- `self._thumb_frames` → `self._pane._thumb_frames`
- `self._thumb_cache` → `self._pane._thumb_cache`
- `self._highlighted_thumb_idx` → `self._pane._highlighted_thumb_idx`
- `self._thumb_render_next` → `self._pane._thumb_render_next`
- `self._thumb_timer` → `self._pane._thumb_timer`
- `self._render_gen` → `self._pane._render_gen`

**Strategy:** Add compatibility properties on `ViewTool` for each attribute so that no method body needs to change in this step:

```python
# Compatibility shims — delegate to active_pane
@property
def doc(self): return self._pane._doc
@doc.setter
def doc(self, v): self._pane._doc = v

@property
def total_pages(self): return self._pane._page_count
@total_pages.setter
def total_pages(self, v): self._pane._page_count = v

@property
def current_page(self): return self._pane._current_page
@current_page.setter
def current_page(self, v): self._pane._current_page = v

@property
def zoom(self): return self._pane._zoom
@zoom.setter
def zoom(self, v): self._pane._zoom = v

@property
def _rotation(self): return self._pane._rotation
@_rotation.setter
def _rotation(self, v): self._pane._rotation = v

@property
def _undo_stack(self): return self._pane._undo_stack
@_undo_stack.setter
def _undo_stack(self, v): self._pane._undo_stack = v

@property
def _redo_stack(self): return self._pane._redo_stack
@_redo_stack.setter
def _redo_stack(self, v): self._pane._redo_stack = v

@property
def _search_results(self): return self._pane._search_results
@_search_results.setter
def _search_results(self, v): self._pane._search_results = v

@property
def _search_flat(self): return self._pane._search_flat
@_search_flat.setter
def _search_flat(self, v): self._pane._search_flat = v

@property
def _search_idx(self): return self._pane._search_idx
@_search_idx.setter
def _search_idx(self, v): self._pane._search_idx = v

@property
def _form_widgets(self): return self._pane._form_widgets
@_form_widgets.setter
def _form_widgets(self, v): self._pane._form_widgets = v

@property
def _thumb_frames(self): return self._pane._thumb_frames
@_thumb_frames.setter
def _thumb_frames(self, v): self._pane._thumb_frames = v

@property
def _thumb_cache(self): return self._pane._thumb_cache
@_thumb_cache.setter
def _thumb_cache(self, v): self._pane._thumb_cache = v

@property
def _highlighted_thumb_idx(self): return self._pane._highlighted_thumb_idx
@_highlighted_thumb_idx.setter
def _highlighted_thumb_idx(self, v): self._pane._highlighted_thumb_idx = v

@property
def _thumb_render_next(self): return self._pane._thumb_render_next
@_thumb_render_next.setter
def _thumb_render_next(self, v): self._pane._thumb_render_next = v

@property
def _thumb_timer(self): return self._pane._thumb_timer
@_thumb_timer.setter
def _thumb_timer(self, v): self._pane._thumb_timer = v

@property
def _render_gen(self): return self._pane._render_gen
@_render_gen.setter
def _render_gen(self, v): self._pane._render_gen = v
```

Also remove the original attribute declarations from `ViewTool.__init__` that are now in `_RenderPane` (to avoid the shim properties seeing the instance variable instead of delegating).

- [ ] **Step 5: Update `ViewTool.cleanup()` to delegate to `_pane`**

```python
def cleanup(self):
    self._pane.cleanup()
    for p in self._temp_files:
        try:
            os.unlink(p)
        except OSError:
            pass
    self._temp_files.clear()
```

- [ ] **Step 6: Run the new tests**

```
pytest tests/test_render_pane.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 7: Run the full test suite**

```
pytest --tb=short -q
```

Expected: same pass count as baseline — no regressions.

- [ ] **Step 8: `ruff check view_tool.py` — fix any issues**

```
ruff check view_tool.py --fix
ruff format view_tool.py
```

- [ ] **Step 9: Commit**

```bash
git add view_tool.py tests/test_render_pane.py
git commit -m "refactor: extract _RenderPane state container from ViewTool"
```

---

## Task 3: Move UI into `_RenderPane`

Move the `PDFCanvas`, nav bar, and thumbnail strip out of `ViewTool._build_ui()` into `_RenderPane`. `PDFCanvas` gains a `_pane` reference and calls `self._pane._view_tool` for toolbar state. `ViewTool._build_ui()` adds the `_RenderPane` widget to its layout instead of the canvas directly.

**Files:**
- Modify: `view_tool.py`

**Background — `PDFCanvas` signature change:**
`PDFCanvas.__init__(self, view_tool)` currently stores `self.vt = view_tool`.
New signature: `PDFCanvas.__init__(self, pane)` where `pane` is the `_RenderPane` instance.
Inside `__init__`:
```python
self._pane = pane
self.vt = pane._view_tool   # toolbar/tool state back-reference (unchanged usage)
```
Every call site constructing `PDFCanvas(self)` (where `self` is `ViewTool`) must change to `PDFCanvas(self._pane)`. Grep `view_tool.py` for `PDFCanvas(` to find all call sites before changing the signature.

- [ ] **Step 1: Write the regression guard test**

Add to `tests/test_render_pane.py`:

```python
def test_pdftool_canvas_construction_unchanged(qapp):
    """PDFCanvas must still be constructable after the pane refactor."""
    from view_tool import ViewTool
    vt = ViewTool()
    # _pane must own a canvas
    assert hasattr(vt._pane, "_canvas")
    assert vt._pane._canvas is not None
    vt.cleanup()

def test_viewtool_canvas_shim(qapp):
    """vt.canvas shim must still point to the active pane's canvas."""
    from view_tool import ViewTool
    vt = ViewTool()
    assert vt.canvas is vt._pane._canvas
    vt.cleanup()
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_render_pane.py::test_pdftool_canvas_construction_unchanged tests/test_render_pane.py::test_viewtool_canvas_shim -v
```

Expected: `AttributeError` — `_pane` has no `_canvas` yet.

- [ ] **Step 3: Update `PDFCanvas.__init__` signature**

Change:
```python
class PDFCanvas(QWidget):
    def __init__(self, view_tool):
        super().__init__(view_tool)
        self.vt = view_tool
```

To:
```python
class PDFCanvas(QWidget):
    def __init__(self, pane):
        super().__init__(pane)
        self._pane = pane
        self.vt = pane._view_tool  # toolbar/tool state back-reference
```

In `PDFCanvas.paintEvent` and other methods, replace any direct attribute reads that should now come from `_pane`:
- `self.vt.doc` → `self._pane._doc`
- `self.vt.zoom` → `self._pane._zoom`
- `self.vt._rotation` → `self._pane._rotation`
- `self.vt.current_page` → `self._pane._current_page`
- `self.vt._page_ox` / `_page_oy` etc. → these are render state; add them to `_RenderPane` (see below)
- `self.vt._search_results` → `self._pane._search_results`

Reads that correctly stay on `self.vt` (toolbar/session state):
- `self.vt._tool` — active tool
- `self.vt._annot_color_idx` — selected color
- `self.vt._stroke_width`
- `self.vt._drag_start`, `_drag_current`, `_freehand_pts`
- `self.vt._selected_words`, `_selection_text`

- [ ] **Step 2: Move coordinate-mapping state to `_RenderPane`**

Add to `_RenderPane.__init__`:
```python
self._page_ox = 0.0
self._page_oy = 0.0
self._page2_ox = 0.0
self._page2_oy = 0.0
self._render_mat = fitz.Matrix(1, 1) if fitz else None
self._inv_mat = fitz.Matrix(1, 1) if fitz else None
self._page_iw = 0.0
self._page_ih = 0.0
```

Add shim properties on `ViewTool` for backward compatibility (same pattern as Task 2):
```python
@property
def _page_ox(self): return self._pane._page_ox
@_page_ox.setter
def _page_ox(self, v): self._pane._page_ox = v
# ... (repeat for _page_oy, _page2_ox, _page2_oy, _render_mat, _inv_mat, _page_iw, _page_ih)
```

- [ ] **Step 3: Build `_RenderPane._build_content_ui()`**

Add a method to `_RenderPane` that creates the canvas, nav bar, and thumbnail strip:

```python
def _build_content_ui(self):
    """Build the per-pane widgets: canvas, nav bar, thumbnail strip."""
    from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QScrollArea
    lay = QVBoxLayout(self)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)

    # Canvas
    self._canvas = PDFCanvas(self)
    lay.addWidget(self._canvas, stretch=1)

    # Nav bar (copy construction from ViewTool._build_ui nav section)
    # ... (move the nav bar widget construction here verbatim)

    # Thumbnail strip
    # ... (move thumbnail strip construction here verbatim)
```

This method is called from `ViewTool._build_ui()` after constructing `self._pane`:
```python
self._pane._build_content_ui()
self._content_layout.addWidget(self._pane)  # replaces addWidget(self._canvas)
```

Also update `ViewTool._build_ui()` to remove the direct canvas / nav bar / thumbnail strip widget construction (they now live in `_RenderPane._build_content_ui()`).

Add a `canvas` shim on `ViewTool` so all existing `self.canvas` references still work:
```python
@property
def canvas(self):
    return self._pane._canvas
```

- [ ] **Step 4: Run full test suite**

```
pytest --tb=short -q
```

Expected: same pass count as baseline.

- [ ] **Step 5: `ruff check` + `ruff format`**

- [ ] **Step 6: Commit**

```bash
git add view_tool.py
git commit -m "refactor: move PDFCanvas and nav widgets into _RenderPane"
```

---

## Task 4: QTabWidget — open, switch, deduplicate

Wrap `_RenderPane` in a `QTabWidget`. For now, one tab is always open (the current file). Add a `+` button. Switching tabs swaps the active `_RenderPane`.

**Files:**
- Modify: `view_tool.py`
- Test: `tests/test_view_tabs.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_view_tabs.py`:

```python
"""Tests for ViewTool tab management."""
import sys
import pytest
from pathlib import Path


def _get_or_create_app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="module")
def qapp():
    return _get_or_create_app()


@pytest.fixture
def pdf(tmp_path):
    """Minimal 1-page PDF."""
    import fitz
    doc = fitz.open()
    doc.new_page()
    p = tmp_path / "test.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


@pytest.fixture
def pdf2(tmp_path):
    import fitz
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    p = tmp_path / "test2.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


def test_single_tab_on_open(qapp, pdf):
    from view_tool import ViewTool
    vt = ViewTool(initial_path=pdf)
    assert vt._tab_widget.count() == 1
    vt.cleanup()


def test_open_second_tab(qapp, pdf, pdf2):
    from view_tool import ViewTool
    vt = ViewTool(initial_path=pdf)
    vt._open_tab(pdf2)
    assert vt._tab_widget.count() == 2
    vt.cleanup()


def test_duplicate_open_focuses_existing(qapp, pdf):
    from view_tool import ViewTool
    vt = ViewTool(initial_path=pdf)
    vt._open_tab(pdf)
    assert vt._tab_widget.count() == 1  # no duplicate
    vt.cleanup()


def test_switch_tab_changes_active_pane(qapp, pdf, pdf2):
    from view_tool import ViewTool
    vt = ViewTool(initial_path=pdf)
    vt._open_tab(pdf2)
    vt._tab_widget.setCurrentIndex(0)
    first_path = vt.active_pane.path
    vt._tab_widget.setCurrentIndex(1)
    second_path = vt.active_pane.path
    assert first_path != second_path
    vt.cleanup()


def test_empty_state_when_no_tabs(qapp):
    from view_tool import ViewTool
    vt = ViewTool()
    assert vt._tab_widget.count() == 0
    vt.cleanup()
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_view_tabs.py -v
```

Expected: `AttributeError: 'ViewTool' object has no attribute '_tab_widget'`

- [ ] **Step 3: Add `QTabWidget` to `ViewTool._build_ui()`**

Import `QTabWidget` at top of file (already in scope since `QSplitter` is imported; add `QTabWidget` to the imports).

In `ViewTool._build_ui()`, replace the block that adds `self._pane` to the layout with:

```python
from PySide6.QtWidgets import QTabWidget
self._tab_widget = QTabWidget()
self._tab_widget.setTabsClosable(True)
self._tab_widget.setMovable(False)
self._tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)
self._tab_widget.currentChanged.connect(self._on_tab_changed)
self._content_layout.addWidget(self._tab_widget)

# Add the initial pane as the first tab (if initial_path provided, done in _load_pdf)
# Show empty state when no tabs
self._empty_state = self._build_empty_state()  # reuse existing drop zone widget
self._content_layout.addWidget(self._empty_state)
self._sync_empty_state()
```

- [ ] **Step 4: Add `_open_tab`, `_on_tab_changed`, `_on_tab_close_requested`, `_sync_empty_state`**

```python
def _open_tab(self, path: str):
    """Open path in a new tab, or focus it if already open."""
    canonical = str(Path(path).resolve())
    for i in range(self._tab_widget.count()):
        pane = self._tab_widget.widget(i)
        if str(Path(pane.path).resolve()) == canonical:
            self._tab_widget.setCurrentIndex(i)
            return
    pane = _RenderPane(self)
    pane._build_content_ui()
    # Connect page_changed once at creation
    pane.page_changed.connect(
        lambda pg, p=pane: self._on_pane_page_changed(p, pg)
    )
    label = self._tab_label(path)
    self._tab_widget.addTab(pane, label)
    self._tab_widget.setCurrentWidget(pane)
    self._sync_empty_state()
    pane.load(path)

def _tab_label(self, path: str) -> str:
    name = Path(path).stem
    return (name[:20] + "\u2026") if len(name) > 20 else name

def _on_tab_changed(self, index: int):
    if index < 0:
        return
    self._pane = self._tab_widget.widget(index)
    self._sync_toolbar_to_pane()
    self._sync_search_panel_to_pane()

def _on_tab_close_requested(self, index: int):
    self._close_tab(index)

def _close_tab(self, index: int):
    pane = self._tab_widget.widget(index)
    if pane is None:
        return
    if pane.is_modified:
        name = Path(pane.path).name
        reply = QMessageBox.question(
            self,
            "Unsaved changes",
            f"Save changes to {name} before closing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return
        if reply == QMessageBox.StandardButton.Save:
            self._save_pane(pane)
    self._tab_widget.removeTab(index)
    pane.cleanup()
    pane.setParent(None)
    pane.deleteLater()
    self._sync_empty_state()

def _sync_empty_state(self):
    has_tabs = self._tab_widget.count() > 0
    self._tab_widget.setVisible(has_tabs)
    self._empty_state.setVisible(not has_tabs)

def _on_pane_page_changed(self, pane: "_RenderPane", page: int):
    from library_page import LibraryState
    LibraryState().set_last_page(pane.path, page)

def _sync_toolbar_to_pane(self):
    """Refresh toolbar state from the newly active pane."""
    # Update undo/redo button enabled states, zoom label, page entry, etc.
    self._update_zoom_label()
    if self._pane.page_count:
        self._page_entry.setText(str(self._pane.active_page + 1))
        self._total_lbl.setText(str(self._pane.page_count))

def _sync_search_panel_to_pane(self):
    """Restore search panel state from the newly active pane."""
    self._search_results = self._pane._search_results
    self._search_flat = self._pane._search_flat
    self._search_idx = self._pane._search_idx
    count = len(self._search_flat)
    if count:
        self._search_count_lbl.setText(
            f"{self._search_idx + 1} of {count}" if self._search_idx >= 0 else f"0 of {count}"
        )
    else:
        self._search_count_lbl.setText("")
```

Also add `load(path)` method to `_RenderPane` that wraps the existing `_load_pdf` logic (calling into `ViewTool._load_pdf` with the pane as context, or duplicating the core logic directly in `_RenderPane`). The simplest approach: keep `ViewTool._load_pdf` but have it write state to `self._pane`:

```python
# In _RenderPane
def load(self, path: str):
    """Public entry point — called by ViewTool tab management."""
    self._view_tool.pdf_path = path
    self._view_tool._load_pdf()
```

Note: `pdf_path` is still on `ViewTool` for now; it will be moved to `_RenderPane` in a later cleanup step.

Also update `active_pane` to return the current tab's widget:

```python
@property
def active_pane(self) -> "_RenderPane":
    w = self._tab_widget.currentWidget()
    return w if w is not None else self._pane
```

- [ ] **Step 5: Run the new tab tests**

```
pytest tests/test_view_tabs.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 6: Run full suite**

```
pytest --tb=short -q
```

Expected: no regressions.

- [ ] **Step 6b: `ruff format` + `ruff check`**

```
ruff format view_tool.py && ruff check view_tool.py
```

- [ ] **Step 7: Commit**

```bash
git add view_tool.py tests/test_view_tabs.py
git commit -m "feat: add QTabWidget multi-document support to ViewTool"
```

---

## Task 5: Tab close flow + app-quit dialog

Add `Ctrl+W` shortcut, keyboard tab cycling, tab modified indicator (`•`), and the aggregate quit dialog.

**Files:**
- Modify: `view_tool.py`
- Test: `tests/test_view_tabs.py` (extend)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_view_tabs.py`:

```python
def test_close_unmodified_tab_no_dialog(qapp, pdf):
    from view_tool import ViewTool
    vt = ViewTool(initial_path=pdf)
    assert not vt.active_pane.is_modified
    vt._close_tab(0)
    assert vt._tab_widget.count() == 0
    vt.cleanup()


def test_viewtool_modified_aggregates_panes(qapp, pdf, pdf2):
    from view_tool import ViewTool
    vt = ViewTool(initial_path=pdf)
    vt._open_tab(pdf2)
    assert vt._modified is False
    vt._tab_widget.widget(0)._is_modified = True
    assert vt._modified is True
    vt._tab_widget.widget(0)._is_modified = False
    assert vt._modified is False
    vt.cleanup()


def test_modified_tab_label_has_bullet(qapp, pdf):
    from view_tool import ViewTool
    vt = ViewTool(initial_path=pdf)
    pane = vt.active_pane
    pane._is_modified = True
    vt._refresh_tab_label(0)
    label = vt._tab_widget.tabText(0)
    assert label.startswith("\u2022")
    vt.cleanup()
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_view_tabs.py::test_close_unmodified_tab_no_dialog tests/test_view_tabs.py::test_modified_tab_label_has_bullet -v
```

- [ ] **Step 3: Add `_refresh_tab_label`, update `_modified` aggregate, add `Ctrl+W`**

```python
def _refresh_tab_label(self, index: int):
    pane = self._tab_widget.widget(index)
    if pane is None:
        return
    label = self._tab_label(pane.path)
    if pane.is_modified:
        label = "\u2022 " + label
    self._tab_widget.setTabText(index, label)
    self._tab_widget.setTabToolTip(index, pane.path)
```

Connect `pane.modified` signal to refresh:
```python
pane.modified.connect(lambda i=index: self._refresh_tab_label(i))
```

Update `_modified` aggregate property:
```python
@property
def _modified(self) -> bool:
    for i in range(self._tab_widget.count()):
        if self._tab_widget.widget(i).is_modified:
            return True
    if self._split_pane is not None and self._split_pane.is_modified:
        return True
    return False
```

(Add `self._split_pane = None` in `__init__` — used by split view in Task 6.)

Add Ctrl+W in `_install_shortcuts`:
```python
QShortcut(QKeySequence("Ctrl+W"), self, self._close_active_tab)
QShortcut(QKeySequence("Ctrl+Tab"), self, self._next_tab)
QShortcut(QKeySequence("Ctrl+Shift+Tab"), self, self._prev_tab)
```

```python
def _close_active_tab(self):
    idx = self._tab_widget.currentIndex()
    if idx >= 0:
        self._close_tab(idx)

def _next_tab(self):
    n = self._tab_widget.count()
    if n > 1:
        self._tab_widget.setCurrentIndex(
            (self._tab_widget.currentIndex() + 1) % n
        )

def _prev_tab(self):
    n = self._tab_widget.count()
    if n > 1:
        self._tab_widget.setCurrentIndex(
            (self._tab_widget.currentIndex() - 1) % n
        )
```

Add aggregate quit dialog — override `closeEvent` in `ViewTool` (not the app, since `main.py` owns the window, but `ViewTool` can expose a `confirm_close() -> bool` method that `main.py` calls):

```python
def confirm_close(self) -> bool:
    """Return True if it is safe to close. Shows save dialog if needed."""
    modified_panes = [
        self._tab_widget.widget(i)
        for i in range(self._tab_widget.count())
        if self._tab_widget.widget(i).is_modified
    ]
    if self._split_pane and self._split_pane.is_modified:
        modified_panes.append(self._split_pane)
    if not modified_panes:
        return True
    n = len(modified_panes)
    # QMessageBox.StandardButton has no SaveAll — use custom buttons.
    box = QMessageBox(self)
    box.setWindowTitle("Unsaved changes")
    box.setText(
        f"You have unsaved changes in {n} open document(s).\n\n"
        "Save all, discard all, or cancel?"
    )
    save_btn = box.addButton("Save All", QMessageBox.ButtonRole.AcceptRole)
    discard_btn = box.addButton("Discard All", QMessageBox.ButtonRole.DestructiveRole)
    box.addButton(QMessageBox.StandardButton.Cancel)
    box.exec()
    clicked = box.clickedButton()
    if clicked is discard_btn:
        return True
    if clicked is save_btn:
        for pane in modified_panes:
            if not self._save_pane(pane):
                return False
        return True
    return False  # Cancel
```

- [ ] **Step 4: Run the tests**

```
pytest tests/test_view_tabs.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Run full suite**

```
pytest --tb=short -q
```

- [ ] **Step 5b: `ruff format` + `ruff check`**

```
ruff format view_tool.py && ruff check view_tool.py
```

- [ ] **Step 6: Commit**

```bash
git add view_tool.py tests/test_view_tabs.py
git commit -m "feat: tab close flow, Ctrl+W, modified indicator, quit dialog"
```

---

## Task 6: Split view

Add a split button to the toolbar. Split mode reparents the active `_RenderPane` into a `QSplitter`; a second auxiliary pane opens the same file.

**Files:**
- Modify: `view_tool.py`
- Test: `tests/test_view_split.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_view_split.py`:

```python
"""Tests for split view."""
import sys
import pytest


def _get_or_create_app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="module")
def qapp():
    return _get_or_create_app()


@pytest.fixture
def pdf(tmp_path):
    import fitz
    doc = fitz.open()
    for _ in range(5):
        doc.new_page()
    p = tmp_path / "test.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


def test_split_activate_creates_right_pane(qapp, pdf):
    from view_tool import ViewTool
    vt = ViewTool(initial_path=pdf)
    vt._activate_split()
    assert vt._split_pane is not None
    vt.cleanup()


def test_split_right_pane_at_page_zero(qapp, pdf):
    from view_tool import ViewTool
    vt = ViewTool(initial_path=pdf)
    vt._activate_split()
    assert vt._split_pane.active_page == 0
    vt.cleanup()


def test_split_panes_independent(qapp, pdf):
    from view_tool import ViewTool
    vt = ViewTool(initial_path=pdf)
    vt._activate_split()
    # Navigate left pane to page 2
    vt._pane._current_page = 2
    # Right pane should still be at 0
    assert vt._split_pane.active_page == 0
    vt.cleanup()


def test_split_collapse_removes_right_pane(qapp, pdf):
    from view_tool import ViewTool
    vt = ViewTool(initial_path=pdf)
    vt._activate_split()
    assert vt._split_pane is not None
    vt._collapse_split()
    assert vt._split_pane is None
    vt.cleanup()


def test_split_collapse_shows_tab_widget(qapp, pdf):
    from view_tool import ViewTool
    vt = ViewTool(initial_path=pdf)
    vt._activate_split()
    vt._collapse_split()
    assert vt._tab_widget.isVisible()
    vt.cleanup()
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_view_split.py -v
```

Expected: `AttributeError: 'ViewTool' object has no attribute '_activate_split'`

- [ ] **Step 3: Add split infrastructure**

In `ViewTool.__init__`, add:
```python
self._split_pane: "_RenderPane | None" = None
self._split_splitter = None
self._split_tab_index = -1  # which tab was moved to left slot
```

Add to toolbar in `_build_ui()`:
```python
split_btn = QPushButton("⬜⬜")
split_btn.setToolTip("Split view")
split_btn.setCheckable(True)
split_btn.clicked.connect(self._toggle_split)
self._btn_split = split_btn
toolbar_row.addWidget(split_btn)
```

Implement:
```python
def _toggle_split(self):
    if self._split_pane is None:
        self._activate_split()
    else:
        self._collapse_split()

def _activate_split(self):
    from PySide6.QtWidgets import QSplitter
    if self._split_pane is not None:
        return
    active_idx = self._tab_widget.currentIndex()
    if active_idx < 0:
        return
    left_pane = self._tab_widget.widget(active_idx)
    # Remove from tab widget (reparent)
    self._split_tab_index = active_idx
    label = self._tab_widget.tabText(active_idx)
    self._tab_widget.removeTab(active_idx)

    # Build splitter
    splitter = QSplitter(Qt.Orientation.Horizontal)
    left_pane.setParent(splitter)
    splitter.addWidget(left_pane)

    # Right pane
    right_pane = _RenderPane(self)
    right_pane._build_content_ui()
    right_pane.page_changed.connect(
        lambda pg, p=right_pane: self._on_pane_page_changed(p, pg)
    )
    splitter.addWidget(right_pane)
    splitter.setSizes([500, 500])

    self._split_splitter = splitter
    self._split_pane = right_pane

    # Hide tab widget, show splitter
    self._content_layout.removeWidget(self._tab_widget)
    self._tab_widget.hide()
    self._content_layout.addWidget(splitter)
    self._pane = left_pane

    # Load same file into right pane at page 0
    if left_pane.path:
        right_pane._view_tool = self
        right_pane.load(left_pane.path)
        right_pane._current_page = 0

def _collapse_split(self):
    if self._split_pane is None:
        return
    # Cleanup right pane
    self._split_pane.cleanup()
    self._split_pane.setParent(None)
    self._split_pane.deleteLater()
    self._split_pane = None

    # Get left pane back from splitter
    left_pane = self._split_splitter.widget(0)
    left_pane.setParent(None)

    # Re-insert into tab widget
    label = self._tab_label(left_pane.path) if left_pane.path else "New"
    idx = min(self._split_tab_index, self._tab_widget.count())
    self._tab_widget.insertTab(idx, left_pane, label)
    self._tab_widget.setCurrentIndex(idx)

    # Remove splitter
    self._split_splitter.setParent(None)
    self._split_splitter.deleteLater()
    self._split_splitter = None

    # Show tab widget
    self._content_layout.addWidget(self._tab_widget)
    self._tab_widget.show()
    self._sync_empty_state()
    self._btn_split.setChecked(False)
```

- [ ] **Step 4: Update `ViewTool.cleanup()` to clean up split pane**

```python
def cleanup(self):
    if self._split_pane is not None:
        self._split_pane.cleanup()
    for i in range(self._tab_widget.count()):
        self._tab_widget.widget(i).cleanup()
    for p in self._temp_files:
        try:
            os.unlink(p)
        except OSError:
            pass
    self._temp_files.clear()
```

- [ ] **Step 5: Run split tests**

```
pytest tests/test_view_split.py -v
```

Expected: all pass.

- [ ] **Step 6: Run full suite**

```
pytest --tb=short -q
```

- [ ] **Step 7: Commit**

```bash
git add view_tool.py tests/test_view_split.py
git commit -m "feat: split view with independent left/right panes"
```

---

## Task 7: Clickable links

Build link cache in `_RenderPane`, add hover cursor + paint overlay in `PDFCanvas`, implement click-priority logic.

**Files:**
- Modify: `view_tool.py`
- Test: `tests/test_view_links.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_view_links.py`:

```python
"""Tests for clickable link routing in _RenderPane."""
import sys
import pytest
from unittest.mock import patch, MagicMock


def _get_or_create_app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="module")
def qapp():
    return _get_or_create_app()


@pytest.fixture
def pdf_with_links(tmp_path):
    """PDF with one internal (LINK_GOTO) and one external (LINK_URI) link."""
    import fitz
    doc = fitz.open()
    p1 = doc.new_page()
    doc.new_page()
    # Internal link from page 0 to page 1
    p1.insert_link({"kind": fitz.LINK_GOTO, "from": fitz.Rect(10, 10, 100, 30), "page": 1})
    # External link
    p1.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(10, 50, 100, 70), "uri": "https://example.com"})
    path = tmp_path / "links.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def test_link_cache_populated_after_render(qapp, pdf_with_links):
    from view_tool import ViewTool
    vt = ViewTool(initial_path=pdf_with_links)
    pane = vt.active_pane
    # After load, link cache should have entries for page 0
    assert len(pane._link_cache) == 2
    vt.cleanup()


def test_link_goto_navigates(qapp, pdf_with_links):
    from view_tool import ViewTool
    import fitz
    vt = ViewTool(initial_path=pdf_with_links)
    pane = vt.active_pane
    link_dict = {"kind": fitz.LINK_GOTO, "page": 1}
    pane._fire_link(link_dict)
    assert pane.active_page == 1
    vt.cleanup()


def test_link_uri_opens_browser(qapp, pdf_with_links):
    from view_tool import ViewTool
    import fitz
    vt = ViewTool(initial_path=pdf_with_links)
    pane = vt.active_pane
    link_dict = {"kind": fitz.LINK_URI, "uri": "https://example.com"}
    with patch("view_tool.QDesktopServices") as mock_ds:
        pane._fire_link(link_dict)
        mock_ds.openUrl.assert_called_once()
    vt.cleanup()


def test_link_unhandled_kind_logs_debug(qapp, pdf_with_links):
    import fitz
    from view_tool import ViewTool
    vt = ViewTool(initial_path=pdf_with_links)
    pane = vt.active_pane
    link_dict = {"kind": fitz.LINK_LAUNCH, "file": "foo.pdf"}
    import logging
    with patch.object(logging.getLogger("view_tool"), "debug") as mock_debug:
        pane._fire_link(link_dict)
        mock_debug.assert_called()
    vt.cleanup()
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_view_links.py -v
```

Expected: `AttributeError: '_RenderPane' has no attribute '_fire_link'`

- [ ] **Step 3: Add link cache population to `_RenderPane`**

Add `QDesktopServices` and `QUrl` to imports at the top of `view_tool.py`:
```python
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
```

Add `_update_link_cache` and `_fire_link` to `_RenderPane`:

```python
def _update_link_cache(self):
    """Rebuild link rect cache for the current page."""
    self._link_cache.clear()
    if self._doc is None:
        return
    try:
        page = self._doc[self._current_page]
        self._link_cache = [(lnk["from"], lnk) for lnk in page.get_links()]
    except Exception:
        pass

def _fire_link(self, link: dict):
    import fitz
    kind = link.get("kind")
    if kind == fitz.LINK_URI:
        QDesktopServices.openUrl(QUrl(link.get("uri", "")))
    elif kind == fitz.LINK_GOTO:
        target = link.get("page", 0)
        if 0 <= target < self._page_count:
            self._view_tool._show_page(target)
    else:
        logger.debug("unhandled link: %s", link)
```

Call `_update_link_cache()` at the end of `_on_render_done` (after the pixmap is set).

- [ ] **Step 4: Add hover + click logic to `PDFCanvas`**

In `PDFCanvas.mouseMoveEvent`, before existing handler code:

```python
def mouseMoveEvent(self, event):
    pos = event.position()
    # Check link hover
    for rect, _ in self._pane._link_cache:
        canvas_rect = self._pane._view_tool._pdf_rect_to_canvas(rect)
        if canvas_rect.contains(pos):
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self._hovered_link_rect = canvas_rect
            self.update()
            # Continue to existing handler (for selection etc.)
            break
    else:
        self.unsetCursor()
        if self._hovered_link_rect is not None:
            self._hovered_link_rect = None
            self.update()
    # ... existing mouseMoveEvent body ...
```

Add `self._hovered_link_rect = None` and `self._link_press_pos = None` to `PDFCanvas.__init__`.

In `PDFCanvas.mousePressEvent`, add at the start:
```python
self._link_press_pos = event.position()
```

In `PDFCanvas.mouseReleaseEvent`, add link-click detection at the start:
```python
release_pos = event.position()
if self._link_press_pos is not None:
    dx = release_pos.x() - self._link_press_pos.x()
    dy = release_pos.y() - self._link_press_pos.y()
    if (dx*dx + dy*dy) <= 16:  # 4px threshold squared
        for rect, link in self._pane._link_cache:
            canvas_rect = self._pane._view_tool._pdf_rect_to_canvas(rect)
            if canvas_rect.contains(self._link_press_pos):
                self._pane._fire_link(link)
                self._link_press_pos = None
                return  # consume event — no annotation
self._link_press_pos = None
# ... existing mouseReleaseEvent body ...
```

In `PDFCanvas.paintEvent`, add a link hover overlay after the page is drawn:
```python
if self._hovered_link_rect is not None:
    col = QColor(BLUE)
    col.setAlphaF(0.20)
    p.fillRect(self._hovered_link_rect, col)
```

- [ ] **Step 5: Run the link tests**

```
pytest tests/test_view_links.py -v
```

Expected: all pass.

- [ ] **Step 6: Run full suite**

```
pytest --tb=short -q
```

- [ ] **Step 7: Commit**

```bash
git add view_tool.py tests/test_view_links.py
git commit -m "feat: clickable links with hover highlight and click-priority logic"
```

---

## Task 8: Reading position memory

Wire `page_changed` → `set_last_page` and restore `last_page` on file open. (Task 4 already connects `page_changed` — here we add the restore side and the clamping.)

**Files:**
- Modify: `view_tool.py`
- Test: `tests/test_view_position.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_view_position.py`:

```python
"""Tests for reading position memory."""
import sys
import pytest
from pathlib import Path


def _get_or_create_app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="module")
def qapp():
    return _get_or_create_app()


@pytest.fixture
def multipage_pdf(tmp_path):
    import fitz
    doc = fitz.open()
    for _ in range(5):
        doc.new_page()
    p = tmp_path / "multi.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


def test_last_page_restored_on_reopen(qapp, multipage_pdf, tmp_path, monkeypatch):
    from library_page import LibraryState, _STATE_PATH
    import library_page
    state_file = tmp_path / "library.json"
    monkeypatch.setattr(library_page, "_STATE_PATH", state_file)

    from view_tool import ViewTool
    # First open — track and navigate to page 3
    vt = ViewTool(initial_path=multipage_pdf)
    LibraryState().track(multipage_pdf)
    LibraryState().set_last_page(multipage_pdf, 3)
    vt.cleanup()

    # Second open — should restore page 3
    vt2 = ViewTool(initial_path=multipage_pdf)
    assert vt2.active_pane.active_page == 3
    vt2.cleanup()


def test_out_of_range_page_clamped(qapp, multipage_pdf, tmp_path, monkeypatch):
    from library_page import LibraryState, _STATE_PATH
    import library_page
    state_file = tmp_path / "library2.json"
    monkeypatch.setattr(library_page, "_STATE_PATH", state_file)

    LibraryState().track(multipage_pdf)
    LibraryState().set_last_page(multipage_pdf, 99)

    from view_tool import ViewTool
    vt = ViewTool(initial_path=multipage_pdf)
    assert vt.active_pane.active_page == 4  # 5 pages → max index 4
    vt.cleanup()
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_view_position.py -v
```

Expected: page restores to 0 (not 3) since the restore logic doesn't exist yet.

- [ ] **Step 3: Add restore logic to `_RenderPane.load()`**

In `_RenderPane.load()` (or in `ViewTool._load_pdf`, after `self.doc = fitz.open(...)` and `self.total_pages = len(self.doc)`), add:

```python
from library_page import LibraryState
last = LibraryState().get_last_page(path)
start_page = min(last, self._pane._page_count - 1) if self._pane._page_count > 0 else 0
self._pane._current_page = start_page
```

Then pass `start_page` to `_show_page(start_page)` instead of `_show_page(0)`.

- [ ] **Step 4: Run the position tests**

```
pytest tests/test_view_position.py -v
```

Expected: both pass.

- [ ] **Step 5: Run full suite**

```
pytest --tb=short -q
```

- [ ] **Step 6: Commit**

```bash
git add view_tool.py tests/test_view_position.py
git commit -m "feat: restore last-viewed page on file open"
```

---

## Task 9: Docs, lint, final check

Update `ARCHITECTURE.md`, `FEATURES.md`, `CHANGELOG.md`, run lint, confirm full suite passes.

**Files:**
- Modify: `docs/project-state/ARCHITECTURE.md`
- Modify: `docs/project-state/FEATURES.md`
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: Update `ARCHITECTURE.md`**

In the module map section, add `_RenderPane` as a class inside `view_tool.py`. In the "Annotation System" section, note that the undo/redo stack has moved to `_RenderPane`. In the "Threading Model" section, note that `_render_worker` is now owned by `_RenderPane`.

- [ ] **Step 2: Update `FEATURES.md`**

Under the `view_tool.py — PDF Viewer` section, append:

- **Multi-Document Tabs** — QTabWidget hosts multiple `_RenderPane` instances; open, switch, close, dedup.
- **Split View** — QSplitter shows two independent panes side by side; toggle via toolbar button.
- **Clickable Links** — `LINK_URI` opens system browser; `LINK_GOTO` navigates in-pane; hover highlight.
- **Reading Position Memory** — `LibraryState` persists `last_page` per file; restored on reopen.

Under the `library_page.py — Document Library` section, append:

- **Last Page Persistence** — `set_last_page` / `get_last_page` on `LibraryState`; written on every page navigation.

- [ ] **Step 3: Update `CHANGELOG.md`**

Add an entry at the top:

```markdown
## [Unreleased]

### Added
- Multi-document tab bar in the PDF viewer (QTabWidget, Ctrl+W, Ctrl+Tab, dedup)
- Split view: side-by-side independent PDF panes (QSplitter)
- Clickable links: LINK_URI opens browser, LINK_GOTO navigates in-pane, hover highlight
- Reading position memory: last-viewed page persisted and restored per file
```

- [ ] **Step 4: `ruff format` + `ruff check`**

```
ruff format view_tool.py library_page.py
ruff check view_tool.py library_page.py --fix
ruff check view_tool.py library_page.py
```

Expected: no errors.

- [ ] **Step 5: Full test suite**

```
pytest --tb=short -q
```

Expected: all tests pass. Count must be >= baseline (all original tests pass, plus new ones).

- [ ] **Step 6: Commit**

```bash
git add docs/project-state/ARCHITECTURE.md docs/project-state/FEATURES.md docs/CHANGELOG.md view_tool.py library_page.py
git commit -m "docs: update ARCHITECTURE.md, FEATURES.md, CHANGELOG.md for viewer refactor"
```

---

## Summary checklist (Definition of Done)

- [ ] `_RenderPane` extracted; no regressions (`pytest` baseline maintained)
- [ ] Tab bar: open, switch, close (with prompt), `Ctrl+W`, dedup, empty state
- [ ] `ViewTool._modified` aggregates all panes; `False` when all clean
- [ ] App quit with unsaved panes → aggregate Save All / Discard All / Cancel dialog
- [ ] `ViewTool.cleanup()` closes all pane fitz docs; verified via `pane._doc.is_closed`
- [ ] Split view: activate, independent page/zoom, collapse restores tab widget
- [ ] Links: `LINK_URI` → browser (mocked), `LINK_GOTO` → navigate, drag doesn't fire
- [ ] Position: restored on reopen, out-of-range clamped, unknown path returns 0
- [ ] `page_changed` connected once per pane; no double-fire on tab switch
- [ ] `ARCHITECTURE.md` updated
- [ ] `ruff format` + `ruff check` clean
- [ ] Full test suite passes
