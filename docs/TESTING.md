# Testing

---

## Framework

**pytest** — version pinned in `requirements.txt` as `pytest>=8.0`.

---

## Running Tests

```bash
# From the project root
pytest tests/

# Verbose output
pytest tests/ -v

# Run a single file
pytest tests/test_library_state.py -v

# Run a single test
pytest tests/test_library_state.py::test_track_adds_file -v
```

> **Note:** pytest is listed in `requirements.txt` but is not currently installed in `.venv`. Run `pip install -r requirements.txt` to install it before running the test suite. See `docs/ENV.md` for full setup steps.

---

## Test File Locations

All test files live in `tests/`. The directory has an `__init__.py` (empty) to make it a package, which allows pytest to discover tests cleanly without path manipulation.

```
tests/
├── __init__.py
├── test_library_state.py    # LibraryState and pure helpers from library_page.py
└── test_pdf_to_csv.py       # Pure-logic static methods on PDFtoCSVTool
```

---

## Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Test file | `test_<module_name>.py` | `test_library_state.py` |
| Test function | `test_<what_it_tests>` | `test_track_adds_file` |
| Fixture | noun describing what it provides | `state`, `tmp_path` |
| Group separator | inline comment block | `# --- LibraryState ---` |

---

## What Is Tested

### `test_library_state.py`
Tests `LibraryState` and the pure helper functions from `library_page.py`. No Qt objects are instantiated — all tests run headlessly.

| Test | Covers |
|---|---|
| `test_fmt_size_*` | `_fmt_size()` formatting (bytes, KB, MB) |
| `test_age_str_*` | `_age_str()` relative time formatting |
| `test_file_size_*` | `_file_size()` with missing and real files |
| `test_state_starts_empty` | Fresh `LibraryState` has empty files and folders |
| `test_track_adds_file` | `track()` creates a new entry |
| `test_track_updates_existing` | `track()` is idempotent (no duplicate entries) |
| `test_favorite` | `set_favorite()` sets and clears the flag |
| `test_trash_and_restore` | `trash()` sets flag; manual restore clears it |
| `test_state_persists` | State written by one instance is readable by another |
| `test_state_path_env_var` | `PDFREE_STATE_DIR` env var changes the state path |

**Key fixture:** `state(tmp_path, monkeypatch)` — creates a `LibraryState` pointed at a temporary directory via `PDFREE_STATE_DIR`. Tests are fully isolated from the real `~/.pdfree/library.json`.

### `test_pdf_to_csv.py`
Tests static/class methods on `PDFtoCSVTool` that contain pure logic. No Qt app or PDF files required.

| Test | Covers |
|---|---|
| `test_parse_*` | `_parse_page_range()` — "all", empty, single, range, comma, mixed, out-of-bounds, inverted, deduplication |
| `test_column_consistency_*` | `_check_column_consistency()` — uniform, inconsistent, empty, single row |
| `test_parse_date_*` | `_try_parse_date()` — ISO, DD/MM/YYYY, non-dates, empty |
| `test_convert_*` | `_convert_cell_type()` — empty, integer, float, text, date, with numbers disabled |

---

## What Is Not Tested

The following are not covered by automated tests. Manual verification is currently required:

| Area | Reason |
|---|---|
| Qt UI rendering (ViewTool, SplitTool, ExcerptTool) | Requires a display and Qt application instance — excluded from headless CI |
| PDF annotation round-trips | Requires real PDF files and fitz — not yet set up as fixtures |
| PDF to CSV extraction end-to-end | Requires real PDFs with tables |
| Drag-and-drop, mouse events, keyboard shortcuts | UI event testing requires Qt test harness (not set up) |
| PyInstaller packaging | Manual smoke test on Windows and macOS after build |

---

## Adding New Tests

1. Create `tests/test_<module_name>.py` if the file does not exist.
2. Write tests for any pure-logic function first (functions that don't touch Qt or the filesystem).
3. For functions that touch the filesystem, use `tmp_path` (built-in pytest fixture).
4. For functions that read `PDFREE_STATE_DIR`, use `monkeypatch.setenv("PDFREE_STATE_DIR", str(tmp_path))`.
5. Never import Qt widgets at module level in test files — the test runner may not have a display. Import inside the test function if needed, or skip with `pytest.mark.skipif`.

**Template:**
```python
"""Tests for <module_name>."""

import pytest


def test_<function>_<scenario>():
    from <module> import <thing>
    result = <thing>(<input>)
    assert result == <expected>
```

---

## CI

Tests run automatically on every push via GitHub Actions (`.github/workflows/release.yml`). The release workflow currently focuses on building installers; a separate test job should be added.

**Recommended addition to `release.yml`:**
```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install pytest pymupdf pypdf pdfplumber
      - run: pytest tests/ -v
```

Note: PySide6 is excluded from CI dependencies since headless Qt tests are not set up. Tests that import Qt widgets must be skipped or guarded in CI.
