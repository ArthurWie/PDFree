# Code Conventions

Extracted from the existing codebase. These are the patterns already in use and the official rules going forward.

---

## File and Module Names

- All Python source files use `snake_case`: `main.py`, `library_page.py`, `view_tool.py`, `split_tool.py`, `excerpt_tool.py`, `pdf_to_csv_tool.py`, `utils.py`, `colors.py`, `icons.py`.
- Tool modules are named `<verb_or_noun>_tool.py` when they are a standalone tool screen (e.g. `view_tool.py`, `split_tool.py`). Exception: `pdf_to_csv_tool.py` uses a descriptor prefix.
- Non-tool modules are named by their role: `colors.py`, `icons.py`, `utils.py`, `library_page.py`, `main.py`.

**Rule:** Add new tool modules as `<tool_name>_tool.py`. Add new shared infrastructure as a plain noun (`<role>.py`).

---

## Class Names

- Public tool widget classes: `PascalCase` matching the module name — `ViewTool`, `SplitTool`, `ExcerptTool`, `PDFtoCSVTool`.
- Public data/state classes: `PascalCase` — `LibraryState`, `Snippet`.
- Public UI component classes (used externally): `PascalCase` — `HeroBanner`, `FolderCard`, `QuickStartZone`.
- Private/internal helper classes (used only within the module): `_PascalCase` (leading underscore) — `_PreviewCanvas`, `_SigCanvas`, `_RecentSwatch`, `_NavBtn`, `_SectionHdr`, `_NewFolderCard`, `_WheelToHScroll`.
- Enum classes: `PascalCase` — `Tool`.

**Inconsistency flagged:** The class `_PreviewCanvas` is independently defined in both `split_tool.py` and `pdf_to_csv_tool.py` with the same name but different implementations. This is not a conflict (different namespaces), but it can cause confusion. **Recommendation:** keep the pattern as-is since the classes are not shared, but if either is ever moved to `utils.py`, rename to `_SplitPreviewCanvas` / `_CSVPreviewCanvas`.

---

## Method and Function Names

- All methods and functions use `snake_case`.
- Private methods (not part of public interface): prefix with `_` — `_build_ui()`, `_show_page()`, `_on_mouse_down()`, `_render_thumbs()`.
- Qt event overrides do not use `_` prefix (they follow Qt's naming): `paintEvent()`, `mousePressEvent()`, `keyPressEvent()`, `resizeEvent()`.
- Signal handler slots use `_on_<signal_name>` — `_on_file_open()`, `_on_search()`, `_on_color_pick()`.
- Builder methods that construct a section of the UI use `_build_<panel_name>` — `_build_ui()`, `_build_left_panel()`, `_build_thumb_strip()`.
- Navigation methods use the verb form directly: `_next_page()`, `_prev_page()`, `_goto_page()`.

**Rule:** All new private methods get a `_` prefix. Qt event overrides never get a `_` prefix.

---

## Variable Names

- Local variables: `snake_case` — `page_idx`, `crop_rect`, `file_path`.
- Loop variables: short if obvious, otherwise descriptive — `for i, snip in enumerate(self._snippets)`.
- Widget local variables: abbreviated noun — `lbl`, `btn`, `lay`, `fr`, `sc`, `ic` are common abbreviations. For layouts: `h`, `v`, `row`, `col` are acceptable.
- Qt layout variables: `lay` for the main layout of a method, `h` / `v` for inner horizontal/vertical layouts.
- Private instance attributes: `_snake_case` prefix — `self._modified`, `self._zoom`, `self._page_idx`, `self._docs`.

---

## Constants

- Module-level constants: `UPPER_SNAKE_CASE` — `IMPLEMENTED`, `THUMB_W`, `LEFT_W`, `MAX_UNDO`, `FIT_PAGE`, `FIT_WIDTH`.
- Color tokens in `colors.py`: `UPPER_SNAKE_CASE` — `BLUE`, `RED`, `G200`, `BRAND`, `RED_DIM`.
- Tool-local color constants: same — `CUT_ACTIVE`, `CUT_INACTIVE`, `TOOL_ACTIVE`.
- Dict/list constants (lookup tables): `UPPER_SNAKE_CASE` — `CATEGORIES`, `TOOL_DESCRIPTIONS`, `ENCODING_MAP`, `DELIMITER_MAP`.

**Rule:** Never define a color literal inline if the same value is used in more than two places. Add it to `colors.py` instead.

---

## Import Ordering

Observed pattern (consistent across all modules):

```python
# 1. __future__ annotations (if used)
from __future__ import annotations

# 2. Standard library
import json
import os
from pathlib import Path

# 3. Third-party (PySide6 first, then PDF backends)
from PySide6.QtWidgets import (...)
from PySide6.QtCore import (...)
from PySide6.QtGui import (...)

import fitz
from pypdf import PdfReader, PdfWriter

# 4. Project-local
from colors import (...)
from icons import svg_pixmap, svg_icon
from utils import _fitz_pix_to_qpixmap, _WheelToHScroll
```

**Rule:** Always follow this order. Within each group, alphabetize by module name. `from` imports before bare `import` within the same group (PySide6 exception: it groups by submodule).

**Inconsistency flagged:** Some modules import colors tokens with `from colors import (...)` multi-line blocks, others on a single line. Multi-line is preferred for readability — it makes diffs cleaner.

---

## Type Annotations

Present in `library_page.py` (all public methods), `icons.py` (all functions), `utils.py` (all functions). Absent in `view_tool.py`, `split_tool.py`, `excerpt_tool.py`, `pdf_to_csv_tool.py` (except for `fitz` type hints in `excerpt_tool.py`).

**Inconsistency flagged.** Annotation coverage is uneven across the codebase.

**Recommendation:** Do not retroactively annotate existing code (per `CLAUDE.md`). Add annotations to any new code you write.

---

## State Management

- **Per-tool in-memory state**: Each tool widget owns its state as private instance attributes (`self._docs`, `self._page_idx`, `self._zoom`, `self._snippets`, etc.). No shared state store between tools.
- **Persisted state**: Only `LibraryState` persists state, via a JSON file at `~/.pdfree/library.json`. Writes are debounced with a 1 s `QTimer`.
- **Unsaved changes flag**: Tools that can have unsaved work expose `self._modified: bool`. Main.py checks this before navigation.
- **Undo stack**: ViewTool maintains a per-document list `_undo_stack` (max 30). No undo in other tools.

---

## Error Handling

- GUI errors (file not found, corrupt PDF): caught with specific exception types (`fitz.FileDataError`, `OSError`, `ValueError`), shown to the user via `QMessageBox.warning()` or a status label. Never silently swallowed.
- Optional dependency imports: wrapped in `try/except ImportError`, with a module-level flag (`_HAS_FITZ`, `_HAS_PLUMBER`) checked before use. The UI degrades gracefully with a warning rather than crashing.
- No bare `except:` anywhere in project code (enforced by `CLAUDE.md`).
- `_file_size()` in `library_page.py` demonstrates the recommended pattern for filesystem calls: return a safe default (0) on `OSError` rather than propagating.

---

## Signal and Slot Naming

- Custom signals defined as class-level `Signal(...)` attributes: `snake_case` — `file_selected`, `clicked`, `open_req`, `delete_req`.
- Slot methods connected to signals: `_on_<signal_or_event>` — `_on_file_open`, `_on_search`, `_on_quick_start`.

---

## UI Construction Pattern

All tools build their UI in `__init__` by calling `_build_ui()`, which delegates to sub-builders (`_build_left_panel()`, `_build_right_panel()`, `_build_thumb_strip()`). This keeps `__init__` short and separates construction from logic.

ViewTool and main.py build UI inline in `__init__` without a `_build_ui()` indirection. Both patterns are acceptable — use `_build_ui()` for tools with a left/right split (simpler navigation of the constructor).

---

## Docstrings

Module-level docstrings are present on all source files (single-line to short multi-line). Method docstrings are sparse — only present on public utility functions in `utils.py` and `icons.py`.

**Rule (per `CLAUDE.md`):** Do not add docstrings to code you did not write. Add a module-level docstring to any new file you create. Add method docstrings only to public functions in shared modules (`utils.py`, `icons.py`).

---

## Folder Structure

```
PDFree/
├── *.py                    # All source files live flat in the root
├── tests/                  # Pytest test files
│   ├── __init__.py
│   ├── test_library_state.py
│   └── test_pdf_to_csv.py
├── docs/                   # All documentation
│   ├── PR_STANDARDS.md
│   ├── DESIGN_STANDARDS.md
│   ├── CHANGELOG.md
│   ├── CONVENTIONS.md
│   ├── DATABASE.md
│   ├── API.md
│   ├── TESTING.md
│   ├── ENV.md
│   ├── TROUBLESHOOTING.md
│   └── project-state/
│       ├── FEATURES.md
│       └── ARCHITECTURE.md
├── .github/workflows/      # CI/CD
├── playground/             # Throwaway scripts (gitignored)
└── CLAUDE.md               # Must stay at root (auto-loaded)
```

**Rule:** All source files remain flat in the root. No `src/` layout. Tests go in `tests/`. Documentation goes in `docs/`. Throwaway exploration scripts go in `playground/` (gitignored).
