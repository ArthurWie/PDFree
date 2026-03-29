# Design: Eraser Tool + Text Box Improvements

**Date:** 2026-03-30
**Scope:** `view_tool.py`

## Goals

1. Add an eraser tool that deletes annotations by click and by drag.
2. Allow existing text box annotations to be repositioned via a hover drag handle.
3. Replace the single-line text box dialog with an inline multiline editor.

## Non-Goals

- A unified annotation selection/handle system (deferred).
- Moving any annotation type other than `PDF_ANNOT_FREE_TEXT`.
- Resizing text boxes via handles.

---

## 1. Eraser Tool

### Enum and toolbar

Add `Tool.ERASER = "eraser"` to the `Tool` enum.

Add a toolbar entry:

```python
(Tool.ERASER, "⌫", "Eraser", "E")
```

The keyboard shortcut `E` is already wired in the shortcut map (`Qt.Key.Key_E: Tool.EXCERTER` is the current binding — **this must be verified before assigning E to Eraser**). If `E` is taken by Excerter, assign a different key (e.g. `W`) and update the docstring.

Cursor: `Qt.CursorShape.ForbiddenCursor`.

### Behavior

**Click (mouse-down):**
- Convert canvas coords to PDF coords via `_canvas_to_pdf`.
- Hit-test `page.annots()`: find the first annotation whose `annot.rect.contains(click_pt)`.
- If found: `_push_undo()`, `page.delete_annot(annot)`, set `_modified = True`, call `_show_page`.

**Drag (mouse-move while button held):**
- On each move event, repeat the same hit-test and deletion for the current PDF point.
- Each deletion pushes undo individually (so Ctrl+Z undoes one annotation at a time).
- Refresh canvas after each deletion.

**Mouse-up:** no additional action.

---

## 2. Text Box — Drag Handle to Move

### Overlay widget

A `QLabel` named `_tb_handle` is created once as a child of the canvas widget. It is hidden by default.

### Show/hide logic

On every `mouseMoveEvent` on the canvas (regardless of active tool):
- Convert canvas coords to PDF coords.
- Iterate `page.annots()` for `PDF_ANNOT_FREE_TEXT` annotations.
- If the mouse is inside an annotation's canvas rect: position and show `_tb_handle` at the top-left of that rect.
- Otherwise: hide `_tb_handle`.

Track the annotation being hovered as `_tb_hover_annot`.

### Drag logic

- `_tb_drag_active` flag and `_tb_drag_origin` (canvas point) are set when the user presses the mouse button on `_tb_handle`.
- On mouse-move while `_tb_drag_active`: compute delta in PDF coords, call `_tb_hover_annot.set_rect(new_rect)`, `_tb_hover_annot.update()`, refresh canvas. Reposition the handle to follow.
- On mouse-up: `_push_undo()` is called **before** the first move (on drag start), `_modified = True`, `_show_page`.

---

## 3. Text Box — Inline Multiline Editor

### Overlay widget

A `QTextEdit` named `_tb_editor` is created once as a child of the canvas widget. It is hidden by default. Styled to match the app's dark theme.

### Opening the editor

The existing `_open_textbox_dialog` is replaced. Two triggers:

1. **New text box:** User clicks on an empty area with `Tool.TEXT_BOX` active. The editor is shown at the click position with an initial size (e.g. 200×100 px canvas coords). Empty content.
2. **Edit existing:** User double-clicks a `PDF_ANNOT_FREE_TEXT` annotation. The editor is positioned at the annotation's canvas rect. Pre-populated with `annot.info.get("content", "")`.

In both cases `_tb_editing_annot` holds the annotation being edited (or `None` for a new box), and `_tb_editor_pdf_origin` stores the PDF top-left for the new annotation.

### Committing

On focus-out or Escape:
- Read `_tb_editor.toPlainText()`.
- If editing an existing annotation: `page.delete_annot(_tb_editing_annot)`.
- If text is non-empty: create a new `page.add_freetext_annot(rect, text, ...)` with rect sized to content (width from longest line, height from line count × fontsize).
- `_push_undo()`, `_modified = True`, `_show_page`, hide `_tb_editor`.

If text is empty and it was a new box: discard silently.

### Font size

Font size is derived from `_stroke_width * 3` (same as current logic, minimum 8pt).

---

## Testing

- Click eraser on each annotation type (highlight, underline, freehand, rect, circle, line, arrow, text box, sticky note) — annotation is deleted.
- Drag eraser across multiple annotations — all swept annotations are deleted.
- Hover over a text box — handle appears; drag handle — annotation moves to new position.
- Double-click a text box — inline editor opens with existing text.
- Edit text with multiple lines (Enter) — multiline text is saved to the annotation.
- Click outside or press Escape — editor commits, annotation updated.
- Create a new text box by clicking with Text Box tool — inline editor opens, text saved on dismiss.
- Undo (Ctrl+Z) after each operation reverts correctly.
