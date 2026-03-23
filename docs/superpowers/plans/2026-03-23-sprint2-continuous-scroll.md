# Sprint 2 — Continuous Scroll Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `ViewMode.CONTINUOUS` to the PDF viewer so pages scroll naturally end-to-end.

**Architecture:** `view_tool.py` has a `ViewMode` plain class (not `enum.Enum`) with string class attributes `SINGLE = "single"` and `TWO_UP = "two_up"`. The `_RenderPane` class builds a layout with `self._scroll_area` (a `QScrollArea` wrapping `self._canvas`). `ViewTool` holds `self._view_mode` and mode-switching methods `_set_mode_single()` / `_set_mode_twoup()`. Navigation uses `_show_page(idx)` on `ViewTool`. We add `CONTINUOUS = "continuous"` to `ViewMode`, a new `_ContinuousPane(QScrollArea)` class, a toolbar button, and `_set_mode_continuous()` on `ViewTool`. In continuous mode the single-canvas scroll area is hidden and replaced by the multi-page pane; teardown reverses this.

**Tech Stack:** Python 3.11, PySide6 (QScrollArea, QVBoxLayout, QLabel), PyMuPDF (fitz), QTimer, pytest

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Modify | `view_tool.py` | Add `ViewMode.CONTINUOUS`; add `_ContinuousPane` class; add toolbar button; add `_set_mode_continuous()`; adapt `_show_page` |
| Modify | `tests/test_view_twoup.py` | Add smoke test for `CONTINUOUS` value |
| Create | `tests/test_view_continuous.py` | Tests for `_ContinuousPane` |

---

## Task 1: Add `ViewMode.CONTINUOUS`

**Files:**
- Modify: `view_tool.py` (line ~186)
- Modify: `tests/test_view_twoup.py`

- [ ] **Step 1: Write a failing test**

In `tests/test_view_twoup.py`, add:

```python
from view_tool import ViewMode

def test_continuous_mode_exists():
    assert ViewMode.CONTINUOUS == "continuous"
```

- [ ] **Step 2: Run to verify it fails**

```
pytest tests/test_view_twoup.py::test_continuous_mode_exists -v
```
Expected: `AttributeError: type object 'ViewMode' has no attribute 'CONTINUOUS'`

- [ ] **Step 3: Add `CONTINUOUS` to `ViewMode` in `view_tool.py`**

Find the `ViewMode` class (around line 186). It is a plain class with string attributes, **not** an `enum.Enum`. Add one line:

```python
class ViewMode:
    SINGLE = "single"
    TWO_UP = "two_up"
    CONTINUOUS = "continuous"   # ← add this line only
```

Do not change the class declaration or existing values.

- [ ] **Step 4: Run to verify it passes**

```
pytest tests/test_view_twoup.py::test_continuous_mode_exists -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add view_tool.py tests/test_view_twoup.py
git commit -m "feat: add ViewMode.CONTINUOUS"
```

---

## Task 2: `_ContinuousPane` — lazy multi-page scrollable canvas

**Files:**
- Modify: `view_tool.py` (add class after `_RenderPane`)
- Create: `tests/test_view_continuous.py`

`_ContinuousPane` is a `QScrollArea` whose content widget holds a `QVBoxLayout` of per-page `QLabel` widgets. Pages are rendered lazily as the user scrolls. The pane opens its own `fitz.Document` from the file path — it does not share the parent's document object, so closing it is safe.

- [ ] **Step 1: Write failing tests**

Create `tests/test_view_continuous.py`:

```python
import shutil, fitz
from pathlib import Path
import pytest

CORPUS = Path(__file__).parent / "corpus"
PLAIN_PDF = str(CORPUS / "plain.pdf")
MULTI_PDF = str(CORPUS / "multipage.pdf")


def test_continuous_pane_page_count(qtbot):
    from view_tool import _ContinuousPane
    pane = _ContinuousPane(PLAIN_PDF)
    qtbot.addWidget(pane)
    doc = fitz.open(PLAIN_PDF)
    expected = doc.page_count
    doc.close()
    assert pane.page_count() == expected


def test_continuous_pane_scroll_to_page_does_not_raise(qtbot):
    from view_tool import _ContinuousPane
    pane = _ContinuousPane(MULTI_PDF)
    qtbot.addWidget(pane)
    pane.show()
    qtbot.waitExposed(pane)
    pane.scroll_to_page(0)


def test_continuous_pane_current_page_at_top(qtbot):
    from view_tool import _ContinuousPane
    pane = _ContinuousPane(PLAIN_PDF)
    qtbot.addWidget(pane)
    pane.show()
    qtbot.waitExposed(pane)
    assert pane.current_page() == 0


def test_continuous_pane_set_zoom(qtbot):
    from view_tool import _ContinuousPane
    pane = _ContinuousPane(PLAIN_PDF)
    qtbot.addWidget(pane)
    pane.show()
    qtbot.waitExposed(pane)
    pane.set_zoom(1.5)
    assert abs(pane.zoom() - 1.5) < 0.01
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_view_continuous.py -v
```
Expected: `ImportError: cannot import name '_ContinuousPane' from 'view_tool'`

- [ ] **Step 3: Implement `_ContinuousPane` in `view_tool.py`**

Add the class after the `_RenderPane` class definition. Use `_fitz_pix_to_qpixmap` from `utils.py` (already imported at the top of `view_tool.py`).

```python
class _ContinuousPane(QScrollArea):
    """Continuous-scroll multi-page PDF pane.

    Opens its own fitz.Document. Renders pages lazily as the user scrolls.
    """

    page_changed = Signal(int)

    def __init__(self, pdf_path: str, zoom: float = 1.0, parent=None):
        super().__init__(parent)
        self._path = pdf_path
        self._zoom = zoom
        self._doc = fitz.open(pdf_path)
        self._labels: list[QLabel] = []
        self._rendered: set[int] = set()

        content = QWidget()
        self._inner = QVBoxLayout(content)
        self._inner.setSpacing(8)
        self._inner.setContentsMargins(8, 8, 8, 8)

        for i in range(self._doc.page_count):
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            page = self._doc.load_page(i)
            w = int(page.rect.width * zoom)
            h = int(page.rect.height * zoom)
            lbl.setFixedSize(w, h)
            self._labels.append(lbl)
            self._inner.addWidget(lbl)

        self.setWidget(content)
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setStyleSheet(f"QScrollArea {{ background: {G50}; border: none; }}")
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)
        QTimer.singleShot(0, self._render_visible)

    # --- Public interface ------------------------------------------------

    def page_count(self) -> int:
        return self._doc.page_count

    def current_page(self) -> int:
        vp_top = self.verticalScrollBar().value()
        for i, lbl in enumerate(self._labels):
            if lbl.geometry().bottom() >= vp_top:
                return i
        return 0

    def zoom(self) -> float:
        return self._zoom

    def set_zoom(self, zoom: float) -> None:
        self._zoom = zoom
        self._rendered.clear()
        for i, lbl in enumerate(self._labels):
            page = self._doc.load_page(i)
            lbl.setFixedSize(int(page.rect.width * zoom), int(page.rect.height * zoom))
            lbl.clear()
        self.widget().adjustSize()
        QTimer.singleShot(0, self._render_visible)

    def scroll_to_page(self, index: int) -> None:
        if not (0 <= index < len(self._labels)):
            return
        # Use QTimer to defer until after layout geometry is finalised
        QTimer.singleShot(0, lambda: self._do_scroll(index))

    # --- Private ---------------------------------------------------------

    def _do_scroll(self, index: int) -> None:
        lbl = self._labels[index]
        self.verticalScrollBar().setValue(lbl.geometry().top())

    def _on_scroll(self) -> None:
        self._render_visible()
        self.page_changed.emit(self.current_page())

    def _render_visible(self) -> None:
        vp_top = self.verticalScrollBar().value()
        vp_bottom = vp_top + self.viewport().height()
        for i, lbl in enumerate(self._labels):
            geo = lbl.geometry()
            if geo.bottom() < vp_top or geo.top() > vp_bottom:
                continue
            if i in self._rendered:
                continue
            self._render_page(i)

    def _render_page(self, index: int) -> None:
        page = self._doc.load_page(index)
        mat = fitz.Matrix(self._zoom, self._zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        pm = _fitz_pix_to_qpixmap(pix)
        self._labels[index].setPixmap(pm)
        self._rendered.add(index)

    def closeEvent(self, event):
        self._doc.close()
        super().closeEvent(event)
```

Note: `G50` is already defined in `colors.py` and imported in `view_tool.py`. If it is not imported, use `G100` instead.

- [ ] **Step 4: Run to verify tests pass**

```
pytest tests/test_view_continuous.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add view_tool.py tests/test_view_continuous.py
git commit -m "feat: add _ContinuousPane scrollable multi-page pane"
```

---

## Task 3: Wire continuous mode into the `ViewTool` toolbar and state

**Files:**
- Modify: `view_tool.py`

`ViewTool` holds `self._view_mode`, `self._btn_mode_single`, `self._btn_mode_twoup` and the toolbar where these buttons live (around line 1576). `_set_mode_single()` and `_set_mode_twoup()` live around line 3324.

The continuous pane replaces `self.active_pane._scroll_area` inside `_RenderPane`'s own layout when active. The `_RenderPane._build_ui` creates `QVBoxLayout` → `_scroll_area` at index 0.

- [ ] **Step 1: Add `self._continuous_pane = None` to `ViewTool.__init__`**

Find `self._view_mode = ViewMode.SINGLE` (line ~1393). After it, add:

```python
self._continuous_pane: "_ContinuousPane | None" = None
```

- [ ] **Step 2: Add the continuous-scroll toolbar button**

Find the `_btn_mode_twoup` creation (line ~1585). After `mode_lay.addWidget(self._btn_mode_twoup)`, add:

```python
self._btn_mode_continuous = QPushButton("≡")
self._btn_mode_continuous.setCheckable(True)
self._btn_mode_continuous.setChecked(False)
self._btn_mode_continuous.setFixedHeight(32)
self._btn_mode_continuous.setToolTip("Continuous scroll")
self._btn_mode_continuous.setStyleSheet(_mode_style)
self._btn_mode_continuous.clicked.connect(self._set_mode_continuous)
mode_lay.addWidget(self._btn_mode_continuous)
```

- [ ] **Step 3: Uncheck the continuous button when switching to single or two-up**

In `_set_mode_single()` (line ~3324), add:

```python
self._btn_mode_continuous.setChecked(False)
self._teardown_continuous()
```

In `_set_mode_twoup()` (line ~3332), add similarly:

```python
self._btn_mode_continuous.setChecked(False)
self._teardown_continuous()
```

- [ ] **Step 4: Add `_set_mode_continuous()` and `_teardown_continuous()` to `ViewTool`**

Add after `_set_mode_twoup`:

```python
def _set_mode_continuous(self) -> None:
    if self._continuous_pane is not None:
        return  # already active
    self._view_mode = ViewMode.CONTINUOUS
    self._btn_mode_single.setChecked(False)
    self._btn_mode_twoup.setChecked(False)
    self._btn_mode_continuous.setChecked(True)
    if not self.doc:
        return
    pane = self.active_pane
    pane._scroll_area.hide()
    zoom = self._effective_zoom() if self.zoom in (FIT_PAGE, FIT_WIDTH) else self.zoom
    self._continuous_pane = _ContinuousPane(pane.pdf_path, zoom=zoom, parent=pane)
    pane.layout().insertWidget(0, self._continuous_pane)
    self._continuous_pane.page_changed.connect(self._on_continuous_page_changed)
    QTimer.singleShot(50, lambda: self._continuous_pane.scroll_to_page(self.current_page))

def _teardown_continuous(self) -> None:
    if self._continuous_pane is None:
        return
    page = self._continuous_pane.current_page()
    self._continuous_pane.page_changed.disconnect()
    self._continuous_pane.setParent(None)
    self._continuous_pane.deleteLater()
    self._continuous_pane = None
    self.active_pane._scroll_area.show()
    self._show_page(page)

def _on_continuous_page_changed(self, page: int) -> None:
    self._page_entry.setText(str(page + 1))
    self._highlight_thumb(page)
```

- [ ] **Step 5: Run the full test suite**

```
pytest --tb=short -q
```
Expected: all existing tests pass; new continuous tests pass

- [ ] **Step 6: Commit**

```bash
git add view_tool.py
git commit -m "feat: wire continuous scroll mode into ViewTool toolbar"
```

---

## Task 4: Adapt `_show_page` to continuous mode

**Files:**
- Modify: `view_tool.py`

When `ViewMode.CONTINUOUS` is active, the page-number input and Prev/Next buttons should scroll the continuous pane rather than flipping the single canvas.

- [ ] **Step 1: Add a guard at the top of `_show_page`**

Find `def _show_page(self, idx: int):` (line ~3210). Add at the very top of the method:

```python
def _show_page(self, idx: int):
    if self._continuous_pane is not None:
        self._continuous_pane.scroll_to_page(idx)
        self._page_entry.setText(str(idx + 1))
        return
    # ... existing body unchanged ...
```

- [ ] **Step 2: Add a guard at the top of `_set_zoom` / zoom handlers**

Find the zoom methods (around line 3345) that call `_show_page`. They already delegate to `_show_page`, so the guard added above will handle them automatically. Verify that `_zoom_fit_width` and `_zoom_in/out` call `_show_page`. If instead they call `_render_page` directly, also add:

```python
if self._continuous_pane is not None:
    self._continuous_pane.set_zoom(self._effective_zoom())
    return
```

at the top of `_render_page`.

- [ ] **Step 3: Run the full test suite**

```
pytest --tb=short -q
```
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add view_tool.py
git commit -m "feat: adapt page navigation and zoom to continuous scroll mode"
```
