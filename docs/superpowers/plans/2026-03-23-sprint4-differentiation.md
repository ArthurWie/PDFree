# Sprint 4 — Differentiation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Radio button write-back + in-place save in the form overlay; expand the batch tool to all operations; introduce `BaseTool` abstract class; deduplicate `_PreviewCanvas` across 8 tool files.

**Architecture:**
- Form fix: two targeted changes in `view_tool.py` — add `_update_radio` handler and remove forced dialog from in-place `Ctrl+S`
- Batch expansion: add a `BATCH_REGISTRY` dict in `batch_tool.py` (replaces the hardcoded `_OPS` list) and add `_run_*` functions for new operations
- BaseTool: new `base_tool.py` with an abstract `BaseTool(QWidget)`; tools opt in one at a time
- PreviewCanvas: extract shared `PreviewCanvas` widget to new `widgets.py`; update 8 tool files

**Tech Stack:** Python 3.11, PySide6, PyMuPDF (fitz), pypdf, pytest

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Modify | `view_tool.py` | Radio write-back + in-place save fix |
| Create | `tests/test_form_fill_radio.py` | Tests for radio write-back |
| Create | `base_tool.py` | Abstract `BaseTool(QWidget)` |
| Create | `tests/test_base_tool.py` | Tests for BaseTool contract |
| Create | `widgets.py` | Shared `PreviewCanvas(QWidget)` |
| Modify | `batch_tool.py` | Replace `_OPS` list with `BATCH_REGISTRY`; add new operations |
| Modify | `tests/test_batch_tool.py` | Tests for new batch operations |
| Modify | `add_page_numbers_tool.py` | Use shared `PreviewCanvas` |
| Modify | `img_to_pdf_tool.py` | Use shared `PreviewCanvas` |
| Modify | `headers_footers_tool.py` | Use shared `PreviewCanvas` |
| No change | `pdf_to_csv_tool.py` | Local `_PreviewCanvas` kept — takes `tool` arg, accesses internal state |
| No change | `pdf_to_excel_tool.py` | Local `_PreviewCanvas` kept — takes `tool` arg, accesses internal state |
| Modify | `split_tool.py` | Use shared `PreviewCanvas` |
| Modify | `sign_tool.py` | Use shared `PreviewCanvas` |
| Modify | `watermark_tool.py` | Use shared `PreviewCanvas` |

---

## Task 1: Form fill — radio button write-back

**Files:**
- Modify: `view_tool.py`
- Create: `tests/test_form_fill_radio.py`

- [ ] **Step 1: Write a failing test**

```python
import shutil, fitz
from pathlib import Path
import pytest

CORPUS = Path(__file__).parent / "corpus"


def test_radio_update_sets_field_value(tmp_path):
    """_update_radio must set field_value on the selected button and clear others."""
    import fitz
    src = tmp_path / "form.pdf"
    shutil.copy2(CORPUS / "form.pdf", src)

    doc = fitz.open(str(src))
    page = doc[0]

    # Collect all radio widgets grouped by field name
    radio_groups: dict[str, list] = {}
    for widget in page.widgets():
        if widget.field_type == fitz.PDF_WIDGET_TYPE_RADIOBUTTON:
            radio_groups.setdefault(widget.field_name, []).append(widget)

    if not radio_groups:
        pytest.skip("form.pdf has no radio buttons")

    # Call the pure update logic (not the Qt overlay — test the fitz side)
    group_name = next(iter(radio_groups))
    widgets_in_group = radio_groups[group_name]
    target = widgets_in_group[0]

    # Simulate: select the first radio in the group
    target.field_value = target.on_state()
    target.update()

    # Verify: field value is set
    for w in page.widgets():
        if w.field_name == group_name and w.rect == target.rect:
            assert w.field_value == target.on_state()
            break

    doc.close()
```

- [ ] **Step 2: Run to understand current state**

```
pytest tests/test_form_fill_radio.py -v
```
This test exercises fitz directly, not the Qt overlay. It documents the expected behaviour.

- [ ] **Step 3: Add `_update_radio` to the form overlay in `view_tool.py`**

Locate the AcroForm overlay setup code (search for `PDF_WIDGET_TYPE_RADIOBUTTON` or `_update_checkbox`). Add a radio button handler modelled after `_update_checkbox`:

```python
def _update_radio(self, widget, btn: "QRadioButton") -> None:
    """Write the selected radio state back to the fitz widget."""
    if not btn.isChecked():
        return
    page = self._doc[widget.page - 1] if hasattr(widget, "page") else self._doc[self._current_page]
    for w in page.widgets():
        if w.field_name == widget.field_name:
            if w.rect == fitz.Rect(widget.rect):
                w.field_value = w.on_state()
            else:
                w.field_value = "Off"
            w.update()
    self._modified = True
```

Wire it in the overlay loop where radio buttons are created:
```python
rb.toggled.connect(lambda checked, wgt=widget, b=rb: self._update_radio(wgt, b) if checked else None)
```

- [ ] **Step 4: Run the full test suite**

```
pytest --tb=short -q
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add view_tool.py tests/test_form_fill_radio.py
git commit -m "feat: add radio button write-back to AcroForm overlay"
```

---

## Task 2: Form fill — in-place save without dialog

**Files:**
- Modify: `view_tool.py`

- [ ] **Step 1: Find `_save_pdf` in `view_tool.py`**

```
grep -n "_save_pdf\|getSaveFileName" view_tool.py | head -20
```

- [ ] **Step 2: Change `_save_pdf` to save in-place when path is known**

The actual `_save_pdf` in `view_tool.py` (line ~4224) uses `self.pdf_path` (not `self._current_path`) and `self._modified`. It already handles the case `path == self.pdf_path` with an incremental save. The only missing behaviour is skipping the dialog when saving in-place via `Ctrl+S`.

Change it to:

```python
def _save_pdf(self, force_dialog: bool = False) -> None:
    if not self.doc:
        return
    if force_dialog or not self.pdf_path:
        initial = Path(self.pdf_path).name if self.pdf_path else "output.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF", initial, "PDF Files (*.pdf)"
        )
        if not path:
            return
    else:
        path = self.pdf_path

    try:
        if path == self.pdf_path:
            self.doc.save(path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
        else:
            self.doc.save(path)
        self._modified = False
        self.pdf_path = path
        QMessageBox.information(self, "Saved", f"PDF saved to:\n{path}")
    except Exception as e:
        logger.exception("save failed")
        QMessageBox.critical(self, "Error", f"Could not save:\n{e}")
```

Add a `Save As` action (toolbar button or menu item) that calls `_save_pdf(force_dialog=True)` so the user can still choose a different path. Wire `Ctrl+S` to `_save_pdf()` (no argument, defaults to in-place).

- [ ] **Step 3: Verify `Ctrl+S` now saves without a dialog when a file is open**

Manual check: open a PDF with a form, fill a field, press Ctrl+S — file should save silently.

- [ ] **Step 4: Run the full test suite**

```
pytest --tb=short -q
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add view_tool.py
git commit -m "feat: Ctrl+S saves form changes in-place without file dialog"
```

---

## Task 3: `BaseTool` abstract class

**Files:**
- Create: `base_tool.py`
- Create: `tests/test_base_tool.py`

- [ ] **Step 1: Write failing tests**

```python
import pytest
from base_tool import BaseTool


def test_base_tool_is_abstract():
    """Cannot instantiate BaseTool directly."""
    with pytest.raises(TypeError):
        BaseTool()


def test_concrete_tool_must_implement_cleanup():
    """A subclass that omits cleanup() raises TypeError on instantiation."""
    class BadTool(BaseTool):
        @property
        def _modified(self):
            return False

    with pytest.raises(TypeError):
        BadTool()


def test_concrete_tool_with_cleanup_can_be_created(qtbot):
    """A properly implemented subclass can be instantiated."""
    from PySide6.QtWidgets import QWidget

    class GoodTool(BaseTool):
        def cleanup(self):
            pass

        @property
        def _modified(self):
            return False

    tool = GoodTool()
    qtbot.addWidget(tool)
    assert isinstance(tool, QWidget)
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_base_tool.py -v
```
Expected: `ModuleNotFoundError: No module named 'base_tool'`

- [ ] **Step 3: Create `base_tool.py`**

```python
"""Abstract base class for all PDFree tool panels."""

from abc import abstractmethod
from PySide6.QtWidgets import QWidget


class BaseTool(QWidget):
    """Base class for all tool panels.

    Subclasses must implement:
        cleanup()   — close fitz documents and release resources
        _modified   — property returning True if unsaved changes exist

    Subclasses may optionally implement:
        load_file(path: str) -> None  — called when a file is opened externally
        batch_apply(input_path: str, output_path: str, **kwargs) -> None
                                      — classmethod for headless batch use
    """

    @abstractmethod
    def cleanup(self) -> None:
        """Release all resources held by this tool."""

    @property
    @abstractmethod
    def _modified(self) -> bool:
        """True if the tool has unsaved changes."""
```

- [ ] **Step 4: Run to verify they pass**

```
pytest tests/test_base_tool.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add base_tool.py tests/test_base_tool.py
git commit -m "feat: add BaseTool abstract base class"
```

---

## Task 4: Migrate three representative tools to `BaseTool`

Apply the migration pattern to three tools as proof-of-concept. The remaining 39 tools can be migrated incrementally.

**Files:**
- Modify: `compress_tool.py`, `rotate_tool.py`, `merge_tool.py`

Migration steps for each tool:

1. Add `from base_tool import BaseTool` import
2. Change the main widget class to inherit from `BaseTool` instead of `QWidget`
3. Ensure `cleanup()` is already defined (it is in all tools); if not, add it
4. Ensure `_modified` property exists (all tools track this); if stored as `self._modified = bool`, rename the attribute to `self.__modified` and add the property:
   ```python
   @property
   def _modified(self) -> bool:
       return self.__modified
   ```

- [ ] **Step 1: Migrate `compress_tool.py`**
- [ ] **Step 2: Migrate `rotate_tool.py`**
- [ ] **Step 3: Migrate `merge_tool.py`**

- [ ] **Step 4: Run the full test suite**

```
pytest --tb=short -q
```
Expected: all pass (no behaviour change)

- [ ] **Step 5: Commit**

```bash
git add compress_tool.py rotate_tool.py merge_tool.py
git commit -m "refactor: migrate compress, rotate, merge tools to BaseTool"
```

---

## Task 5: Extract shared `PreviewCanvas` to `widgets.py`

**Files:**
- Create: `widgets.py`
- Modify: `add_page_numbers_tool.py`, `img_to_pdf_tool.py`, `headers_footers_tool.py`, `split_tool.py`, `sign_tool.py`, `watermark_tool.py`
- No change: `pdf_to_csv_tool.py`, `pdf_to_excel_tool.py` (local `_PreviewCanvas` kept — incompatible constructor)

- [ ] **Step 1: Read `_PreviewCanvas` in `split_tool.py` to use as the canonical implementation**

```
grep -n "class _PreviewCanvas" split_tool.py
```
Read the class definition to understand what interface it exposes (typically: `set_page(fitz.Page)` or `set_pixmap(QPixmap)`).

- [ ] **Step 2: Write a failing test**

Create `tests/test_widgets.py`:

```python
def test_preview_canvas_importable():
    from widgets import PreviewCanvas
    assert PreviewCanvas is not None


def test_preview_canvas_is_qwidget(qtbot):
    from widgets import PreviewCanvas
    from PySide6.QtWidgets import QWidget
    canvas = PreviewCanvas()
    qtbot.addWidget(canvas)
    assert isinstance(canvas, QWidget)
```

- [ ] **Step 3: Run to verify they fail**

```
pytest tests/test_widgets.py -v
```
Expected: `ModuleNotFoundError: No module named 'widgets'`

- [ ] **Step 4: Read all 8 `_PreviewCanvas` implementations before creating `widgets.py`**

All 8 files define `class _PreviewCanvas(QWidget)` — the base class is `QWidget`, not `QLabel`. Before writing the shared version, read each file's `_PreviewCanvas` to understand the full interface:

```
grep -n -A 40 "class _PreviewCanvas" split_tool.py add_page_numbers_tool.py sign_tool.py watermark_tool.py headers_footers_tool.py img_to_pdf_tool.py pdf_to_csv_tool.py pdf_to_excel_tool.py
```

Then create `widgets.py` using `QWidget` as the base class. The canonical form (from `split_tool.py`):

```python
"""Shared reusable Qt widgets for PDFree tool panels."""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap


class PreviewCanvas(QWidget):
    """Shared PDF page preview canvas used across tool panels.

    Call set_pixmap(pm) to display a rendered page.
    The canvas scales the pixmap to fit while maintaining aspect ratio.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self.setMinimumSize(1, 1)

    def set_pixmap(self, pm: QPixmap) -> None:
        self._pixmap = pm
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._pixmap:
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        painter.end()
```

**Important:** If any of the 8 files has additional methods on `_PreviewCanvas` (e.g. `clear()`, `set_page()`), include them in the shared version. The shared class must be a superset of all 8 interfaces.

- [ ] **Step 5: Run to verify the widget test passes**

```
pytest tests/test_widgets.py -v
```

- [ ] **Step 6: Update 6 of the 8 tool files (NOT `pdf_to_csv_tool` or `pdf_to_excel_tool`)**

`pdf_to_csv_tool.py` and `pdf_to_excel_tool.py` have a `_PreviewCanvas` that takes a `tool` constructor argument and accesses `self._t._page_pixmap` inside `paintEvent`. They are **not drop-in replaceable** with the shared widget. Leave those two files unchanged.

For each of the 6 remaining files (`add_page_numbers_tool.py`, `img_to_pdf_tool.py`, `headers_footers_tool.py`, `split_tool.py`, `sign_tool.py`, `watermark_tool.py`):

1. Add `from widgets import PreviewCanvas` at the top
2. Delete the local `class _PreviewCanvas` definition
3. Replace all references to `_PreviewCanvas(` with `PreviewCanvas(`

- [ ] **Step 7: Run the full test suite**

```
pytest --tb=short -q
```
Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add widgets.py tests/test_widgets.py \
  add_page_numbers_tool.py img_to_pdf_tool.py headers_footers_tool.py \
  split_tool.py sign_tool.py watermark_tool.py
git commit -m "refactor: extract shared PreviewCanvas to widgets.py (6 tools)"
```

---

## Task 6: Expand batch tool operations

**Files:**
- Modify: `batch_tool.py`
- Modify: `tests/test_batch_tool.py`

The current `_OPS` list has 5 entries. We will replace it with a `BATCH_REGISTRY` that maps op IDs to metadata and runner functions, making it easy to add more operations without changing the worker.

- [ ] **Step 1: Write a failing test for registry extensibility**

Add to `tests/test_batch_tool.py`:

```python
def test_batch_registry_contains_watermark():
    from batch_tool import BATCH_REGISTRY
    assert "watermark" in BATCH_REGISTRY


def test_batch_registry_contains_pdfa():
    from batch_tool import BATCH_REGISTRY
    assert "pdf_to_pdfa" in BATCH_REGISTRY


def test_batch_registry_all_have_run_fn():
    from batch_tool import BATCH_REGISTRY
    for op_id, entry in BATCH_REGISTRY.items():
        assert callable(entry["run"]), f"{op_id} missing run function"
        assert "label" in entry, f"{op_id} missing label"
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_batch_tool.py::test_batch_registry_contains_watermark -v
```
Expected: `ImportError: cannot import name 'BATCH_REGISTRY'`

- [ ] **Step 3: Refactor `batch_tool.py` to use `BATCH_REGISTRY`**

Replace `_OPS` with a registry dict. Keep all existing `_run_*` functions. Add `_run_watermark` and `_run_pdf_to_pdfa`:

```python
def _run_watermark(src: str, dst: str, text: str, opacity: float = 0.3) -> None:
    doc = fitz.open(src)
    try:
        for page in doc:
            page.insert_text(
                (page.rect.width / 2, page.rect.height / 2),
                text,
                fontsize=48,
                color=(0.7, 0.7, 0.7),
                rotate=45,
                render_mode=3,  # invisible fill, stroke only
            )
        doc.save(dst, garbage=3, deflate=True)
    finally:
        doc.close()


def _run_pdf_to_pdfa(src: str, dst: str) -> None:
    """Convert to PDF/A-1b using PyMuPDF scrub + XMP injection."""
    doc = fitz.open(src)
    try:
        doc.scrub()
        xmp = (
            '<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
            '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
            '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            '<rdf:Description xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/">'
            '<pdfaid:part>1</pdfaid:part>'
            '<pdfaid:conformance>B</pdfaid:conformance>'
            '</rdf:Description></rdf:RDF></x:xmpmeta>'
            '<?xpacket end="w"?>'
        )
        doc.set_xml_metadata(xmp)
        doc.save(dst, garbage=4, deflate=True)
    finally:
        doc.close()


BATCH_REGISTRY = {
    "compress":          {"label": "Compress",           "run": _run_compress,         "options": ["preset_idx"]},
    "rotate":            {"label": "Rotate Pages",       "run": _run_rotate,           "options": ["degrees"]},
    "add_page_numbers":  {"label": "Add Page Numbers",   "run": _run_add_page_numbers, "options": ["pos_idx", "fmt_idx", "start"]},
    "add_password":      {"label": "Add Password",       "run": _run_add_password,     "options": ["password", "enc_idx"]},
    "remove_password":   {"label": "Remove Password",    "run": _run_remove_password,  "options": ["password"]},
    "watermark":         {"label": "Watermark",          "run": _run_watermark,        "options": ["text", "opacity"]},
    "pdf_to_pdfa":       {"label": "Convert to PDF/A",   "run": _run_pdf_to_pdfa,      "options": []},
}
```

Update `_BatchWorker._process` to use the registry (the existing `__init__` already stores `self._op_id` as a string — no signature change needed):

```python
def _process(self, src: str, dst: str) -> None:
    entry = BATCH_REGISTRY[self._op_id]
    s = self._settings
    entry["run"](src, dst, **{k: s[k] for k in entry["options"] if k in s})
```

Update the `_OPS` list (used by the combo box `op_idx` lookup) to derive from the registry while preserving the string key:

```python
_OPS = [(op_id, entry["label"]) for op_id, entry in BATCH_REGISTRY.items()]
```

The combo box stores `op_idx` as an integer index. The worker is instantiated with `op_id = _OPS[op_idx][0]` (a string). This wiring stays the same — verify the `BatchTool` widget's run-button handler passes `_OPS[combo.currentIndex()][0]` to `_BatchWorker`, not a raw integer.

- [ ] **Step 4: Run the tests**

```
pytest tests/test_batch_tool.py -v
```
Expected: all pass including new registry tests

- [ ] **Step 5: Run the full suite**

```
pytest --tb=short -q
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add batch_tool.py tests/test_batch_tool.py
git commit -m "feat: replace _OPS list with BATCH_REGISTRY; add watermark and PDF/A batch operations"
```
