# Adaptive Open/Add PDF Button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two separate "Open" and "+ Add PDF" toolbar buttons in ViewTool with a single adaptive button that reads "Open PDF" when no tabs are open and "+ Add PDF" (green) when one or more tabs are open.

**Architecture:** All changes are in `view_tool.py`. A new `_open_or_add_pdf` method replaces `_pick_pdf` and `_open_file_dialog` — it always calls `open_file()` which handles tab creation. A new `_update_open_btn` method is called at the end of `open_file()`, `_close_tab()`, and `__init__` to keep the button in sync with `_tab_widget.count()`.

**Tech Stack:** Python 3.11+, PySide6, PyMuPDF (fitz)

**Spec:** `docs/superpowers/specs/2026-03-23-adaptive-open-button-design.md`

---

### Task 1: Write failing tests for button state

**Files:**
- Modify: `tests/test_view_tabs.py`

- [ ] **Step 1: Add four new tests at the end of `tests/test_view_tabs.py`**

```python
def test_open_btn_initial_label(qapp):
    """Button reads 'Open PDF' when no tabs are open."""
    from view_tool import ViewTool
    vt = ViewTool()
    assert hasattr(vt, "_open_btn")
    assert vt._open_btn.text() == "Open PDF"
    vt.cleanup()


def test_open_btn_label_after_open(qapp, pdf_file):
    """Button reads '+ Add PDF' after a file is opened."""
    from view_tool import ViewTool
    vt = ViewTool()
    vt.open_file(pdf_file)
    assert vt._open_btn.text() == "+ Add PDF"
    vt.cleanup()


def test_open_btn_label_after_close_all(qapp, pdf_file):
    """Button reverts to 'Open PDF' after the last tab is closed."""
    from view_tool import ViewTool
    vt = ViewTool()
    vt.open_file(pdf_file)
    vt._close_tab(0)
    assert vt._open_btn.text() == "Open PDF"
    vt.cleanup()


def test_open_btn_label_with_initial_path(qapp, pdf_file):
    """Button reads '+ Add PDF' when ViewTool is constructed with initial_path."""
    from view_tool import ViewTool
    vt = ViewTool(initial_path=pdf_file)
    assert vt._open_btn.text() == "+ Add PDF"
    vt.cleanup()
```

- [ ] **Step 2: Run new tests to confirm they fail**

```
pytest tests/test_view_tabs.py::test_open_btn_initial_label tests/test_view_tabs.py::test_open_btn_label_after_open tests/test_view_tabs.py::test_open_btn_label_after_close_all tests/test_view_tabs.py::test_open_btn_label_with_initial_path -v
```

Expected: 4 FAILs — `AttributeError: 'ViewTool' object has no attribute '_open_btn'` (or similar)

---

### Task 2: Replace toolbar buttons in `_build_ui`

**Files:**
- Modify: `view_tool.py` (lines ~1504–1526)

Context: Inside `_build_ui`, the toolbar is assembled. There is currently:
```python
open_btn = _hbtn("Open")
open_btn.clicked.connect(self._pick_pdf)
left_lay.addWidget(open_btn)
...
add_btn = _hbtn(
    "+ Add PDF", bg=GREEN, hover="#15803D", fg=WHITE, border=GREEN, bold=True
)
add_btn.clicked.connect(self._open_file_dialog)
left_lay.addWidget(add_btn)
```

- [ ] **Step 1: Replace both buttons with a single adaptive button**

Remove the two button blocks and the `left_lay.addSpacing(8)` between them (line ~1520), replacing the entire section with:
```python
self._open_btn = _hbtn("Open PDF")
self._open_btn.clicked.connect(self._open_or_add_pdf)
left_lay.addWidget(self._open_btn)
```

- [ ] **Step 2: Re-wire the corner `+` tab button**

Find (around line 2039):
```python
add_tab_btn.clicked.connect(self._open_file_dialog)
```
Change to:
```python
add_tab_btn.clicked.connect(self._open_or_add_pdf)
```

---

### Task 3: Add `_open_or_add_pdf` and `_update_open_btn` methods

**Files:**
- Modify: `view_tool.py` (FILE LOADING section, around line 2951)

- [ ] **Step 1: Add `GREEN_HOVER` to the colors import**

Find the `from colors import (` block near the top of `view_tool.py`. It already imports `GREEN`. Add `GREEN_HOVER` to the same import list.

- [ ] **Step 2: Add `_open_or_add_pdf` just before `_pick_pdf`**

```python
def _open_or_add_pdf(self):
    p, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
    if p:
        self.open_file(p)
```

- [ ] **Step 3: Add `_update_open_btn` directly after `_open_or_add_pdf`**

```python
def _update_open_btn(self):
    has_tabs = self._tab_widget.count() > 0
    if has_tabs:
        self._open_btn.setText("+ Add PDF")
        self._open_btn.setStyleSheet(
            f"QPushButton {{ background: {GREEN}; color: {WHITE}; "
            f"border: 1px solid {GREEN}; border-radius: 8px; "
            f"font: bold 13px 'Segoe UI'; padding: 0 16px; }}"
            f"QPushButton:hover {{ background: {GREEN_HOVER}; }}"
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

Note: `GREEN`, `WHITE`, `G700`, `G300`, `G100` are already imported from `colors` at the top of `view_tool.py`. `GREEN_HOVER` is defined in `colors.py` but is **not** currently imported. Add `GREEN_HOVER` to the `from colors import (...)` block at the top of `view_tool.py` before running this code.

---

### Task 4: Call `_update_open_btn` in the right places

**Files:**
- Modify: `view_tool.py`

- [ ] **Step 1: Call at end of `__init__`, after `_build_ui()` and initial_path block**

Find (around line 1450–1455):
```python
self._build_ui()
self._install_shortcuts()

if initial_path:
    self.pdf_path = initial_path
    self._load_pdf()
```

Replace with:
```python
self._build_ui()
self._install_shortcuts()
self._update_open_btn()

if initial_path:
    self.open_file(initial_path)
```

Two things changed here:
1. `_update_open_btn()` is called after `_build_ui()` so the initial style is set.
2. `initial_path` now calls `self.open_file(initial_path)` (which adds a tab) instead of the legacy `_load_pdf()` path. This means `self.pdf_path = initial_path` is also removed here — `open_file` handles that internally via `pane.load()`.

- [ ] **Step 2: Call at end of `open_file()`**

Find the end of the `open_file` method (around line 4428–4431):
```python
        self._render_thumbnails()
        self._build_toc()
        self._tab_widget.setVisible(True)
        self._vt_scroll_area.setVisible(False)
```

Add one line at the very end:
```python
        self._render_thumbnails()
        self._build_toc()
        self._tab_widget.setVisible(True)
        self._vt_scroll_area.setVisible(False)
        self._update_open_btn()
```

- [ ] **Step 3: Call at end of `_close_tab()`**

Find the end of `_close_tab` (around line 4504–4506):
```python
        pane.cleanup()
        self._tab_widget.removeTab(index)
        if self._tab_widget.count() == 0:
            self._tab_widget.setVisible(False)
```

Add one line at the very end:
```python
        pane.cleanup()
        self._tab_widget.removeTab(index)
        if self._tab_widget.count() == 0:
            self._tab_widget.setVisible(False)
        self._update_open_btn()
```

---

### Task 5: Remove dead methods

**Files:**
- Modify: `view_tool.py`

- [ ] **Step 1: Delete `_pick_pdf` (around line 2960–2965)**

```python
def _pick_pdf(self):
    p, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
    if not p:
        return
    self.pdf_path = p
    self._load_pdf()
```

Delete the entire method body.

- [ ] **Step 2: Delete `_open_file_dialog` (around line 2955–2958)**

```python
def _open_file_dialog(self):
    p, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
    if p:
        self.open_file(p)
```

Delete the entire method body.

- [ ] **Step 3: Delete `_add_pdf` (around line 3008–3034)**

```python
def _add_pdf(self):
    if not self.doc:
        self._pick_pdf()
        return
    p, _ = QFileDialog.getOpenFileName(self, "Add PDF", "", "PDF Files (*.pdf)")
    ...
```

Delete the entire method body (all ~27 lines).

---

### Task 6: Run new tests — should pass now

- [ ] **Step 1: Run the four new tests**

```
pytest tests/test_view_tabs.py::test_open_btn_initial_label tests/test_view_tabs.py::test_open_btn_label_after_open tests/test_view_tabs.py::test_open_btn_label_after_close_all tests/test_view_tabs.py::test_open_btn_label_with_initial_path -v
```

Expected: 4 PASSes

---

### Task 7: Run full test suite and lint

- [ ] **Step 1: Run full test suite**

```
pytest --tb=short -q
```

Expected: all tests pass, no regressions

- [ ] **Step 2: Run ruff formatter**

```
ruff format view_tool.py tests/test_view_tabs.py
```

- [ ] **Step 3: Run ruff linter**

```
ruff check view_tool.py tests/test_view_tabs.py
```

Expected: no errors

---

### Task 8: Commit

- [ ] **Step 1: Stage and commit**

```bash
git add view_tool.py tests/test_view_tabs.py
git commit -m "feat: replace open/add-pdf buttons with single adaptive button"
```
