# Eraser Tool + Text Box Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an eraser tool that deletes annotations by click and drag; add a hover drag handle to reposition text box annotations; replace the single-line text box dialog with an inline multiline QTextEdit overlay.

**Architecture:** All changes are isolated to `view_tool.py`. Two small widget subclasses (`_DragHandle`, `_InlineTextEditor`) are added to the file and instantiated inside `PDFCanvas.__init__`. ViewTool methods access them through the `self._canvas` property. Tests create a ViewTool with a real fitz PDF and drive behavior by calling internal methods directly.

**Tech Stack:** Python 3.11+, PySide6, PyMuPDF (fitz), pytest

---

## File Map

| File | Action | What changes |
|---|---|---|
| `view_tool.py` | Modify | `Tool` enum, `_TOOLS`, `PDFCanvas.__init__`, `ViewTool._set_tool`, `ViewTool._on_mouse_down`, `ViewTool._on_mouse_move`, `ViewTool._on_double_click`, `ViewTool._open_textbox_dialog` (replaced) |
| `tests/test_view_eraser.py` | Create | Eraser click and drag tests |
| `tests/test_view_textbox.py` | Create | Drag handle + inline editor tests |

---

## Task 1: Add `Tool.ERASER` to enum, toolbar, cursor, and shortcut

**Files:**
- Modify: `view_tool.py` (Tool enum ~line 146, `_TOOLS` ~line 165, `_set_tool` ~line 2774, shortcut map ~line 748)

- [ ] **Step 1: Verify E is taken by EXCERTER**

  Open `view_tool.py` and confirm line ~759:
  ```python
  Qt.Key.Key_E: Tool.EXCERTER,
  ```
  E is taken. The eraser shortcut will be `W`.

- [ ] **Step 2: Add `Tool.ERASER` to the enum**

  In the `Tool(Enum)` block (~line 146), after `Tool.ARROW`:
  ```python
  ERASER = "eraser"
  ```

- [ ] **Step 3: Add toolbar entry to `_TOOLS`**

  In `_TOOLS` (~line 165), after the SIGN entry and before EXCERTER:
  ```python
  (Tool.ERASER, "⌫", "Eraser", "W"),
  ```

- [ ] **Step 4: Add cursor mapping in `_set_tool`**

  In the `cursors` dict inside `_set_tool` (~line 2781), add:
  ```python
  Tool.ERASER: Qt.CursorShape.ForbiddenCursor,
  ```

- [ ] **Step 5: Add keyboard shortcut**

  In the `shortcut_map` dict inside `PDFCanvas.keyPressEvent` (~line 748), add:
  ```python
  Qt.Key.Key_W: Tool.ERASER,
  ```

- [ ] **Step 6: Run existing tests to confirm no regressions**

  ```bash
  cd C:/Users/arthu/Desktop/PDFree
  pytest tests/test_view_tabs.py tests/test_view_position.py -v
  ```
  Expected: all pass.

- [ ] **Step 7: Commit**

  ```bash
  git add view_tool.py
  git commit -m "feat: add Tool.ERASER enum value, toolbar entry, shortcut W"
  ```

---

## Task 2: Eraser click — delete annotation under cursor

**Files:**
- Modify: `view_tool.py` (`_on_mouse_down` ~line 3853)
- Create: `tests/test_view_eraser.py`

- [ ] **Step 1: Write the failing test**

  Create `tests/test_view_eraser.py`:
  ```python
  """Tests for the eraser tool in ViewTool."""

  import sys
  import pytest


  def _get_or_create_app():
      from PySide6.QtWidgets import QApplication
      return QApplication.instance() or QApplication(sys.argv)


  @pytest.fixture(scope="module")
  def qapp():
      return _get_or_create_app()


  @pytest.fixture
  def pdf_with_rect_annot(tmp_path):
      """PDF with a single rect annotation at a known position."""
      import fitz
      doc = fitz.open()
      page = doc.new_page(width=200, height=200)
      annot = page.add_rect_annot(fitz.Rect(50, 50, 100, 100))
      annot.update()
      p = tmp_path / "annot.pdf"
      doc.save(str(p))
      doc.close()
      return str(p)


  def _open_and_render(qapp, pdf_path):
      from view_tool import ViewTool
      from PySide6.QtWidgets import QApplication
      vt = ViewTool()
      vt.show()
      vt.open_file(pdf_path)
      QApplication.processEvents()
      QApplication.processEvents()
      return vt


  def test_eraser_click_deletes_annotation(qapp, pdf_with_rect_annot):
      from view_tool import Tool
      vt = _open_and_render(qapp, pdf_with_rect_annot)
      page = vt.doc[0]
      assert len(list(page.annots())) == 1

      # Get canvas coords of annotation center (PDF coords 75, 75)
      cx, cy = vt._pdf_to_canvas(75.0, 75.0)
      vt._set_tool(Tool.ERASER)
      vt._on_mouse_down(cx, cy)

      page = vt.doc[0]
      assert len(list(page.annots())) == 0
      assert vt._modified
      vt.cleanup()


  def test_eraser_click_empty_area_does_nothing(qapp, pdf_with_rect_annot):
      from view_tool import Tool
      vt = _open_and_render(qapp, pdf_with_rect_annot)
      page = vt.doc[0]
      assert len(list(page.annots())) == 1

      # Canvas coords far from annotation (PDF coords 5, 5)
      cx, cy = vt._pdf_to_canvas(5.0, 5.0)
      vt._set_tool(Tool.ERASER)
      vt._on_mouse_down(cx, cy)

      page = vt.doc[0]
      assert len(list(page.annots())) == 1
      vt.cleanup()
  ```

- [ ] **Step 2: Run test to verify it fails**

  ```bash
  pytest tests/test_view_eraser.py -v
  ```
  Expected: FAIL — `Tool.ERASER` may not be in `_on_mouse_down`, or no handler yet.

- [ ] **Step 3: Implement eraser click in `_on_mouse_down`**

  In `ViewTool._on_mouse_down` (~line 3853), after the `elif self._tool == Tool.STICKY_NOTE:` branch, add:

  ```python
  elif self._tool == Tool.ERASER:
      click_pt = fitz.Point(px, py)
      page = self.doc[self.current_page]
      for annot in page.annots():
          if annot.rect.contains(click_pt):
              self._push_undo()
              page.delete_annot(annot)
              self._modified = True
              self._show_page(self.current_page)
              break
  ```

- [ ] **Step 4: Run test to verify it passes**

  ```bash
  pytest tests/test_view_eraser.py -v
  ```
  Expected: both tests PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add view_tool.py tests/test_view_eraser.py
  git commit -m "feat: eraser tool click deletes annotation under cursor"
  ```

---

## Task 3: Eraser drag — delete all swept annotations

**Files:**
- Modify: `view_tool.py` (`_on_mouse_move` ~line 3893)
- Modify: `tests/test_view_eraser.py`

- [ ] **Step 1: Write the failing test**

  Append to `tests/test_view_eraser.py`:
  ```python
  @pytest.fixture
  def pdf_with_two_annots(tmp_path):
      """PDF with two rect annotations at known non-overlapping positions."""
      import fitz
      doc = fitz.open()
      page = doc.new_page(width=400, height=200)
      a1 = page.add_rect_annot(fitz.Rect(10, 10, 60, 60))
      a1.update()
      a2 = page.add_rect_annot(fitz.Rect(200, 10, 250, 60))
      a2.update()
      p = tmp_path / "two_annots.pdf"
      doc.save(str(p))
      doc.close()
      return str(p)


  def test_eraser_drag_deletes_swept_annotations(qapp, pdf_with_two_annots):
      from view_tool import Tool
      from PySide6.QtWidgets import QApplication
      vt = _open_and_render(qapp, pdf_with_two_annots)
      page = vt.doc[0]
      assert len(list(page.annots())) == 2

      vt._set_tool(Tool.ERASER)

      # Simulate mouse-down at first annotation center (PDF 35, 35)
      cx1, cy1 = vt._pdf_to_canvas(35.0, 35.0)
      vt._on_mouse_down(cx1, cy1)
      QApplication.processEvents()

      # Simulate mouse-move to second annotation center (PDF 225, 35)
      cx2, cy2 = vt._pdf_to_canvas(225.0, 35.0)
      vt._on_mouse_move(cx2, cy2)
      QApplication.processEvents()

      page = vt.doc[0]
      assert len(list(page.annots())) == 0
      vt.cleanup()
  ```

- [ ] **Step 2: Run test to verify it fails**

  ```bash
  pytest tests/test_view_eraser.py::test_eraser_drag_deletes_swept_annotations -v
  ```
  Expected: FAIL — second annotation is not deleted on drag.

- [ ] **Step 3: Implement eraser drag in `_on_mouse_move`**

  In `ViewTool._on_mouse_move`, after the `if self._drag_start is None: return` guard, inside the existing elif chain, add before the final `elif self._tool == Tool.FREEHAND:` (or append at the end of the chain):

  ```python
  elif self._tool == Tool.ERASER:
      click_pt = fitz.Point(px, py)
      page = self.doc[self.current_page]
      for annot in list(page.annots()):
          if annot.rect.contains(click_pt):
              self._push_undo()
              page.delete_annot(annot)
              self._modified = True
              self._show_page(self.current_page)
              break
  ```

- [ ] **Step 4: Run all eraser tests**

  ```bash
  pytest tests/test_view_eraser.py -v
  ```
  Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add view_tool.py tests/test_view_eraser.py
  git commit -m "feat: eraser tool drag erases all swept annotations"
  ```

---

## Task 4: Text box drag handle widget + hover show/hide

**Files:**
- Modify: `view_tool.py` (`PDFCanvas.__init__` ~line 406, ViewTool `_on_mouse_move` ~line 3893)
- Create: `tests/test_view_textbox.py`

- [ ] **Step 1: Write the failing test**

  Create `tests/test_view_textbox.py`:
  ```python
  """Tests for text box drag handle and inline editor in ViewTool."""

  import sys
  import pytest


  def _get_or_create_app():
      from PySide6.QtWidgets import QApplication
      return QApplication.instance() or QApplication(sys.argv)


  @pytest.fixture(scope="module")
  def qapp():
      return _get_or_create_app()


  @pytest.fixture
  def pdf_with_freetext(tmp_path):
      """PDF with a FREE_TEXT annotation at a known position."""
      import fitz
      doc = fitz.open()
      page = doc.new_page(width=400, height=400)
      annot = page.add_freetext_annot(
          fitz.Rect(50, 50, 200, 80),
          "Hello",
          fontsize=12,
      )
      annot.update()
      p = tmp_path / "freetext.pdf"
      doc.save(str(p))
      doc.close()
      return str(p)


  def _open_and_render(qapp, pdf_path):
      from view_tool import ViewTool
      from PySide6.QtWidgets import QApplication
      vt = ViewTool()
      vt.show()
      vt.open_file(pdf_path)
      QApplication.processEvents()
      QApplication.processEvents()
      return vt


  def test_tb_handle_exists_on_canvas(qapp, pdf_with_freetext):
      vt = _open_and_render(qapp, pdf_with_freetext)
      assert hasattr(vt._canvas, "_tb_handle")
      vt.cleanup()


  def test_tb_handle_visible_when_hovering_freetext(qapp, pdf_with_freetext):
      from PySide6.QtWidgets import QApplication
      vt = _open_and_render(qapp, pdf_with_freetext)
      # Hover over center of annotation (PDF coords 125, 65)
      cx, cy = vt._pdf_to_canvas(125.0, 65.0)
      vt._on_mouse_move(cx, cy)
      QApplication.processEvents()
      assert vt._canvas._tb_handle.isVisible()
      vt.cleanup()


  def test_tb_handle_hidden_when_not_hovering(qapp, pdf_with_freetext):
      from PySide6.QtWidgets import QApplication
      vt = _open_and_render(qapp, pdf_with_freetext)
      # Move to an empty area (PDF coords 300, 300)
      cx, cy = vt._pdf_to_canvas(300.0, 300.0)
      vt._on_mouse_move(cx, cy)
      QApplication.processEvents()
      assert not vt._canvas._tb_handle.isVisible()
      vt.cleanup()
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  pytest tests/test_view_textbox.py::test_tb_handle_exists_on_canvas tests/test_view_textbox.py::test_tb_handle_visible_when_hovering_freetext tests/test_view_textbox.py::test_tb_handle_hidden_when_not_hovering -v
  ```
  Expected: FAIL — `_tb_handle` doesn't exist yet.

- [ ] **Step 3: Add `_DragHandle` class and `_tb_handle` to `PDFCanvas`**

  Add the `_DragHandle` class just before the `PDFCanvas` class definition (~line 405):

  ```python
  class _DragHandle(QLabel):
      """Drag handle overlay shown when hovering over a FREE_TEXT annotation."""

      def __init__(self, canvas):
          super().__init__("⠿ drag", canvas)
          self._canvas = canvas
          self._drag_active = False
          self._drag_origin = None      # (canvas_x, canvas_y) at press
          self._annot_orig_rect = None  # fitz.Rect at press
          self.setStyleSheet(
              "QLabel { background: #1e3a5f; color: #93c5fd; border-radius: 3px; "
              "padding: 1px 6px; font-size: 11px; }"
          )
          self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
          self.setFixedHeight(18)
          self.hide()

      def mousePressEvent(self, event):
          if event.button() == Qt.MouseButton.LeftButton:
              vt = self._canvas._vt
              if vt._canvas._tb_hover_annot is not None:
                  vt._push_undo()
              self._drag_active = True
              pos = self.mapTo(self._canvas, event.position().toPoint())
              self._drag_origin = (pos.x(), pos.y())
              annot = self._canvas._tb_hover_annot
              if annot is not None:
                  self._annot_orig_rect = fitz.Rect(annot.rect)
          super().mousePressEvent(event)

      def mouseMoveEvent(self, event):
          if self._drag_active and self._drag_origin is not None:
              vt = self._canvas._vt
              pos = self.mapTo(self._canvas, event.position().toPoint())
              dx_c = pos.x() - self._drag_origin[0]
              dy_c = pos.y() - self._drag_origin[1]
              # Move the handle widget
              self.move(self.x() + int(dx_c), self.y() + int(dy_c))
              self._drag_origin = (pos.x(), pos.y())
          super().mouseMoveEvent(event)

      def mouseReleaseEvent(self, event):
          if self._drag_active and self._annot_orig_rect is not None:
              vt = self._canvas._vt
              annot = self._canvas._tb_hover_annot
              if annot is not None and vt.doc:
                  # Compute total canvas delta from original position
                  orig_cx, orig_cy = vt._pdf_to_canvas(
                      self._annot_orig_rect.x0, self._annot_orig_rect.y0
                  )
                  new_cx = self.x()
                  new_cy = self.y()
                  dx_c = new_cx - orig_cx
                  dy_c = new_cy - orig_cy
                  # Convert delta to PDF coords
                  orig_px, orig_py = vt._canvas_to_pdf(0.0, 0.0)
                  end_px, end_py = vt._canvas_to_pdf(dx_c, dy_c)
                  dpx = end_px - orig_px
                  dpy = end_py - orig_py
                  r = self._annot_orig_rect
                  new_rect = fitz.Rect(
                      r.x0 + dpx, r.y0 + dpy,
                      r.x1 + dpx, r.y1 + dpy,
                  )
                  annot.set_rect(new_rect)
                  annot.update()
                  vt._modified = True
                  vt._show_page(vt.current_page)
          self._drag_active = False
          self._drag_origin = None
          self._annot_orig_rect = None
          super().mouseReleaseEvent(event)
  ```

  Then in `PDFCanvas.__init__` (after `self._vt = pane._view_tool` is set), add:

  ```python
  self._tb_handle = _DragHandle(self)
  self._tb_hover_annot = None
  ```

- [ ] **Step 4: Add hover detection to `ViewTool._on_mouse_move`**

  In `ViewTool._on_mouse_move`, before the `if self._drag_start is None: return` guard, add a call to a new helper:

  ```python
  self._update_tb_handle(cx, cy)
  ```

  Then add the helper method anywhere in `ViewTool` (near `_open_textbox_dialog`):

  ```python
  def _update_tb_handle(self, cx: float, cy: float):
      """Show or hide the text-box drag handle based on hover position."""
      if not self.doc:
          self._canvas._tb_handle.hide()
          return
      px, py = self._canvas_to_pdf(cx, cy)
      hover_pt = fitz.Point(px, py)
      page = self.doc[self.current_page]
      for annot in page.annots():
          if annot.type[0] == fitz.PDF_ANNOT_FREE_TEXT:
              if annot.rect.contains(hover_pt):
                  self._canvas._tb_hover_annot = annot
                  hx, hy = self._pdf_to_canvas(annot.rect.x0, annot.rect.y0)
                  handle = self._canvas._tb_handle
                  handle.move(int(hx), int(hy))
                  handle.adjustSize()
                  handle.show()
                  handle.raise_()
                  return
      self._canvas._tb_hover_annot = None
      self._canvas._tb_handle.hide()
  ```

- [ ] **Step 5: Run the handle tests**

  ```bash
  pytest tests/test_view_textbox.py::test_tb_handle_exists_on_canvas tests/test_view_textbox.py::test_tb_handle_visible_when_hovering_freetext tests/test_view_textbox.py::test_tb_handle_hidden_when_not_hovering -v
  ```
  Expected: all 3 PASS.

- [ ] **Step 6: Commit**

  ```bash
  git add view_tool.py tests/test_view_textbox.py
  git commit -m "feat: add text box drag handle with hover show/hide"
  ```

---

## Task 5: Drag handle moves annotation

This behavior is already implemented inside `_DragHandle.mouseReleaseEvent` from Task 4. This task adds a test to verify it.

**Files:**
- Modify: `tests/test_view_textbox.py`

- [ ] **Step 1: Write the failing test**

  Append to `tests/test_view_textbox.py`:
  ```python
  def test_drag_handle_moves_freetext_annotation(qapp, pdf_with_freetext):
      import fitz
      from PySide6.QtCore import QPoint, Qt
      from PySide6.QtGui import QMouseEvent
      from PySide6.QtWidgets import QApplication
      vt = _open_and_render(qapp, pdf_with_freetext)

      # Hover to show handle
      cx, cy = vt._pdf_to_canvas(125.0, 65.0)
      vt._on_mouse_move(cx, cy)
      QApplication.processEvents()

      handle = vt._canvas._tb_handle
      assert handle.isVisible()

      orig_rect = fitz.Rect(vt.doc[0].annots().__next__().rect)

      # Simulate drag: press at handle pos, move 30px right, release
      press_pt = QPoint(handle.x() + 5, handle.y() + 5)
      move_pt = QPoint(press_pt.x() + 30, press_pt.y())
      release_pt = move_pt

      def _make_event(t, pos):
          return QMouseEvent(
              t,
              pos.toPointF() if hasattr(pos, "toPointF") else pos,
              Qt.MouseButton.LeftButton,
              Qt.MouseButton.LeftButton,
              Qt.KeyboardModifier.NoModifier,
          )

      # Map press/release to handle-local coords
      handle_press = handle.mapFromParent(press_pt)
      handle_move = handle.mapFromParent(move_pt)
      handle_release = handle.mapFromParent(release_pt)

      handle.mousePressEvent(_make_event(QMouseEvent.Type.MouseButtonPress, handle_press))
      handle.mouseMoveEvent(_make_event(QMouseEvent.Type.MouseMove, handle_move))
      handle.mouseReleaseEvent(_make_event(QMouseEvent.Type.MouseButtonRelease, handle_release))
      QApplication.processEvents()
      QApplication.processEvents()

      new_rect = fitz.Rect(vt.doc[0].annots().__next__().rect)
      assert new_rect.x0 != orig_rect.x0, "Annotation should have moved"
      vt.cleanup()
  ```

- [ ] **Step 2: Run test**

  ```bash
  pytest tests/test_view_textbox.py::test_drag_handle_moves_freetext_annotation -v
  ```
  Expected: PASS (behavior was already implemented in Task 4).

  If it fails due to `annots().__next__()` after `_show_page` re-renders async, add extra `QApplication.processEvents()` calls or access the doc directly before render completes.

- [ ] **Step 3: Commit**

  ```bash
  git add tests/test_view_textbox.py
  git commit -m "test: verify drag handle moves text box annotation"
  ```

---

## Task 6: Inline text editor widget + open for new text box

**Files:**
- Modify: `view_tool.py` (`PDFCanvas.__init__`, `ViewTool._on_mouse_down`, `ViewTool._open_textbox_dialog` replacement)
- Modify: `tests/test_view_textbox.py`

- [ ] **Step 1: Write the failing test**

  Append to `tests/test_view_textbox.py`:
  ```python
  @pytest.fixture
  def empty_pdf(tmp_path):
      import fitz
      doc = fitz.open()
      doc.new_page(width=400, height=400)
      p = tmp_path / "empty.pdf"
      doc.save(str(p))
      doc.close()
      return str(p)


  def test_tb_editor_exists_on_canvas(qapp, empty_pdf):
      vt = _open_and_render(qapp, empty_pdf)
      assert hasattr(vt._canvas, "_tb_editor")
      vt.cleanup()


  def test_clicking_with_textbox_tool_opens_inline_editor(qapp, empty_pdf):
      from view_tool import Tool
      from PySide6.QtWidgets import QApplication
      vt = _open_and_render(qapp, empty_pdf)
      vt._set_tool(Tool.TEXT_BOX)
      # Click on empty area (PDF coords 100, 100)
      cx, cy = vt._pdf_to_canvas(100.0, 100.0)
      vt._on_mouse_down(cx, cy)
      QApplication.processEvents()
      assert vt._canvas._tb_editor.isVisible()
      assert vt._canvas._tb_editor.toPlainText() == ""
      vt.cleanup()
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  pytest tests/test_view_textbox.py::test_tb_editor_exists_on_canvas tests/test_view_textbox.py::test_clicking_with_textbox_tool_opens_inline_editor -v
  ```
  Expected: FAIL — `_tb_editor` doesn't exist yet.

- [ ] **Step 3: Add `_InlineTextEditor` class**

  Add just before `_DragHandle` in `view_tool.py`:

  ```python
  class _InlineTextEditor(QTextEdit):
      """Inline multiline editor overlay for FREE_TEXT annotations."""

      committed = Signal()

      def __init__(self, canvas):
          super().__init__(canvas)
          self._canvas = canvas
          self.setStyleSheet(
              "QTextEdit { background: #1e293b; color: #e5e7eb; border: 2px solid #3B82F6; "
              "border-radius: 4px; font-family: 'Segoe UI'; font-size: 12px; padding: 4px; }"
          )
          self.hide()

      def focusOutEvent(self, event):
          super().focusOutEvent(event)
          self.committed.emit()

      def keyPressEvent(self, event):
          if event.key() == Qt.Key.Key_Escape:
              self.committed.emit()
          else:
              super().keyPressEvent(event)
  ```

- [ ] **Step 4: Add `_tb_editor` to `PDFCanvas.__init__`**

  In `PDFCanvas.__init__`, after the `_tb_handle` line:

  ```python
  self._tb_editor = _InlineTextEditor(self)
  self._tb_editing_annot = None   # fitz annotation being edited, or None for new
  self._tb_editor_pdf_origin = None  # (px, py) top-left for new annotation
  self._tb_editor.committed.connect(self._vt._commit_tb_editor)
  ```

- [ ] **Step 5: Replace `_open_textbox_dialog` with `_open_tb_editor`**

  In `ViewTool`, rename `_open_textbox_dialog` to `_open_tb_editor` and replace its body entirely:

  ```python
  def _open_tb_editor(self, pdf_x: float, pdf_y: float, existing_annot=None):
      canvas = self._canvas
      editor = canvas._tb_editor

      # Position and size the editor in canvas coords
      if existing_annot is not None:
          r = existing_annot.rect
          x0c, y0c = self._pdf_to_canvas(r.x0, r.y0)
          x1c, y1c = self._pdf_to_canvas(r.x1, r.y1)
          w = max(100, int(x1c - x0c))
          h = max(40, int(y1c - y0c))
          editor.move(int(x0c), int(y0c))
          old_text = existing_annot.info.get("content", "")
      else:
          x0c, y0c = self._pdf_to_canvas(pdf_x, pdf_y)
          w, h = 200, 100
          editor.move(int(x0c), int(y0c))
          old_text = ""

      editor.setFixedSize(w, h)
      canvas._tb_editing_annot = existing_annot
      canvas._tb_editor_pdf_origin = (pdf_x, pdf_y)
      editor.setPlainText(old_text)
      editor.show()
      editor.raise_()
      editor.setFocus()
  ```

- [ ] **Step 6: Update the call site in `_on_mouse_down`**

  Find the line (~line 3888):
  ```python
  elif self._tool == Tool.TEXT_BOX:
      self._open_textbox_dialog(px, py)
  ```
  Change to:
  ```python
  elif self._tool == Tool.TEXT_BOX:
      self._open_tb_editor(px, py)
  ```

- [ ] **Step 7: Run new tests**

  ```bash
  pytest tests/test_view_textbox.py::test_tb_editor_exists_on_canvas tests/test_view_textbox.py::test_clicking_with_textbox_tool_opens_inline_editor -v
  ```
  Expected: both PASS.

- [ ] **Step 8: Commit**

  ```bash
  git add view_tool.py tests/test_view_textbox.py
  git commit -m "feat: add inline QTextEdit overlay for text box creation"
  ```

---

## Task 7: Inline editor — open for edit existing + commit

**Files:**
- Modify: `view_tool.py` (`_on_double_click`, add `_commit_tb_editor`)
- Modify: `tests/test_view_textbox.py`

- [ ] **Step 1: Write the failing tests**

  Append to `tests/test_view_textbox.py`:
  ```python
  def test_double_click_freetext_opens_editor_with_existing_text(qapp, pdf_with_freetext):
      from PySide6.QtWidgets import QApplication
      vt = _open_and_render(qapp, pdf_with_freetext)
      # Double-click at annotation center (PDF 125, 65)
      cx, cy = vt._pdf_to_canvas(125.0, 65.0)
      vt._on_double_click(cx, cy)
      QApplication.processEvents()
      assert vt._canvas._tb_editor.isVisible()
      assert vt._canvas._tb_editor.toPlainText() == "Hello"
      vt.cleanup()


  def test_commit_tb_editor_saves_multiline_text(qapp, pdf_with_freetext):
      import fitz
      from PySide6.QtWidgets import QApplication
      vt = _open_and_render(qapp, pdf_with_freetext)
      cx, cy = vt._pdf_to_canvas(125.0, 65.0)
      vt._on_double_click(cx, cy)
      QApplication.processEvents()

      editor = vt._canvas._tb_editor
      editor.setPlainText("Line one\nLine two")
      vt._commit_tb_editor()
      QApplication.processEvents()
      QApplication.processEvents()

      assert not editor.isVisible()
      page = vt.doc[0]
      annots = list(page.annots())
      assert len(annots) == 1
      content = annots[0].info.get("content", "")
      assert "Line one" in content
      assert "Line two" in content
      vt.cleanup()


  def test_commit_empty_new_textbox_discards(qapp, empty_pdf):
      from PySide6.QtWidgets import QApplication
      from view_tool import Tool
      vt = _open_and_render(qapp, empty_pdf)
      vt._set_tool(Tool.TEXT_BOX)
      cx, cy = vt._pdf_to_canvas(100.0, 100.0)
      vt._on_mouse_down(cx, cy)
      QApplication.processEvents()

      # Commit with empty text
      vt._canvas._tb_editor.setPlainText("")
      vt._commit_tb_editor()
      QApplication.processEvents()
      QApplication.processEvents()

      page = vt.doc[0]
      assert len(list(page.annots())) == 0
      vt.cleanup()
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  pytest tests/test_view_textbox.py::test_double_click_freetext_opens_editor_with_existing_text tests/test_view_textbox.py::test_commit_tb_editor_saves_multiline_text tests/test_view_textbox.py::test_commit_empty_new_textbox_discards -v
  ```
  Expected: FAIL — `_commit_tb_editor` doesn't exist; double-click still calls old path.

- [ ] **Step 3: Update `_on_double_click` to use `_open_tb_editor`**

  In `ViewTool._on_double_click` (~line 4126), find:
  ```python
  if atype == fitz.PDF_ANNOT_FREE_TEXT:
      self._open_textbox_dialog(px, py, existing_annot=annot)
      return
  ```
  Change to:
  ```python
  if atype == fitz.PDF_ANNOT_FREE_TEXT:
      self._open_tb_editor(px, py, existing_annot=annot)
      return
  ```

- [ ] **Step 4: Add `_commit_tb_editor` to `ViewTool`**

  Add the method near `_open_tb_editor`:

  ```python
  def _commit_tb_editor(self):
      canvas = self._canvas
      editor = canvas._tb_editor
      if not editor.isVisible():
          return
      editor.hide()
      text = editor.toPlainText()
      existing_annot = canvas._tb_editing_annot
      pdf_x, pdf_y = canvas._tb_editor_pdf_origin or (0.0, 0.0)
      canvas._tb_editing_annot = None
      canvas._tb_editor_pdf_origin = None

      if not text and existing_annot is None:
          return

      self._push_undo()
      page = self.doc[self.current_page]
      _, _, fitz_rgb = self._annot_color
      fontsize = max(8, self._stroke_width * 3)

      if existing_annot is not None:
          old_rect = existing_annot.rect
          page.delete_annot(existing_annot)
          if text:
              lines = text.split("\n")
              width = max(old_rect.width, max(len(l) for l in lines) * fontsize * 0.6)
              height = max(old_rect.height, len(lines) * fontsize * 1.4 + fontsize)
              rect = fitz.Rect(old_rect.x0, old_rect.y0, old_rect.x0 + width, old_rect.y0 + height)
              annot = page.add_freetext_annot(rect, text, fontsize=fontsize,
                                              text_color=fitz_rgb, fontname="helv",
                                              fill_color=None)
              annot.update()
      else:
          if text:
              lines = text.split("\n")
              width = max(100, max(len(l) for l in lines) * fontsize * 0.6)
              height = len(lines) * fontsize * 1.4 + fontsize
              rect = fitz.Rect(pdf_x, pdf_y, pdf_x + width, pdf_y + height)
              annot = page.add_freetext_annot(rect, text, fontsize=fontsize,
                                              text_color=fitz_rgb, fontname="helv",
                                              fill_color=None)
              annot.update()

      self._modified = True
      self._show_page(self.current_page)
  ```

- [ ] **Step 5: Run all textbox tests**

  ```bash
  pytest tests/test_view_textbox.py -v
  ```
  Expected: all tests PASS.

- [ ] **Step 6: Run full test suite**

  ```bash
  pytest -x -q
  ```
  Expected: no regressions. Fix any failures before proceeding.

- [ ] **Step 7: Commit**

  ```bash
  git add view_tool.py tests/test_view_textbox.py
  git commit -m "feat: inline multiline editor for text box create and edit"
  ```

---

## Task 8: Final check — linting + full suite

**Files:** none new

- [ ] **Step 1: Run ruff formatter**

  ```bash
  cd C:/Users/arthu/Desktop/PDFree
  ruff format view_tool.py tests/test_view_eraser.py tests/test_view_textbox.py
  ```

- [ ] **Step 2: Run ruff linter**

  ```bash
  ruff check view_tool.py tests/test_view_eraser.py tests/test_view_textbox.py
  ```
  Fix any reported issues.

- [ ] **Step 3: Run full test suite**

  ```bash
  pytest -q
  ```
  Expected: all pass. Fix any failures.

- [ ] **Step 4: Commit formatting fixes (if any)**

  ```bash
  git add view_tool.py tests/test_view_eraser.py tests/test_view_textbox.py
  git commit -m "chore: apply ruff formatting to eraser and textbox files"
  ```
