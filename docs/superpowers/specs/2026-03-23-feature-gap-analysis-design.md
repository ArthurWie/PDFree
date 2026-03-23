# PDFree Feature Gap Analysis — Strategic Assessment
> Date: 2026-03-23
> Scope: v1.0 launch readiness and differentiation vs. Stirling-PDF
> Method: Full codebase exploration across 42 tools, 25 test files, all docs, CI pipeline, and Stirling-PDF comparison doc

---

## Context

PDFree is a 42-tool native desktop PDF application (Python 3.11 + PySide6 + PyMuPDF) with multi-platform CI/CD, comprehensive documentation, and a consistent worker-based architecture. The project is feature-complete in breadth but has specific gaps that affect v1.0 trust, everyday usability, and competitive differentiation.

This assessment is organized by the five strategic dimensions below. Each dimension ends with its contribution to the cross-cutting priority table at the end of this document.

---

## Dimension 1 — Security

### No code signing (P0 — ship blocker)
Windows SmartScreen blocks any unsigned `.exe` with a full-screen warning. macOS Gatekeeper quarantines unsigned `.app` bundles. The current workaround (right-click → Open, or Properties → Unblock) is documented in release notes but visibly damages trust with first-time users and is a hard barrier for corporate environments. This is the single largest credibility gap for v1.0.

**What is needed:** An Apple Developer ID certificate (macOS notarization) and a Windows code signing certificate (EV or OV) integrated into the CI release pipeline. The macOS step requires `codesign`, `xcrun notarytool`, and `stapler`; the Windows step requires `signtool.exe` or `osslsigncode` in the Actions workflow.

### No security scanning in CI (P1)
PDFree processes sensitive documents (signed PDFs, encrypted files, forms with personal data). The CI pipeline runs tests but has no static security analysis (bandit) and no dependency vulnerability scanning (pip-audit). Given the dependency surface — pyhanko, pymupdf, pdfplumber, ocrmypdf — at least one CVE in a transitive dependency is a near-certainty over time. This is invisible today.

**What is needed:** Add `bandit -r . -ll` and `pip-audit` steps to the test job in `release.yml`. Fail the build on high-severity findings.

### No automatic backup before destructive saves (P0)
Every tool that transforms or overwrites a PDF has no safety net. A failed conversion mid-write (crash, disk-full, permission error) can produce a truncated or corrupt output with no recovery path. No tool offers a "keep original as `.bak`" option.

**What is needed:** A shared utility in `utils.py` — `backup_original(path) -> Path` — that copies the source file to `<name>.bak` before any destructive operation. All tool workers call it before `fitz.save()`. The option can be opt-in via a global preference.

### PyMuPDF AGPL (acknowledged — business decision)
Already tracked in `docs/comparison-stirling.md`. Not actionable without resolving the Artifex commercial license question. Out of scope for this assessment.

---

## Dimension 2 — UX / User-Facing Features

### No continuous scroll in the viewer (P0)
The viewer supports single-page and two-up modes only. Every mainstream PDF viewer scrolls continuously between pages. Users expect to scroll down and have the next page appear naturally; the current model requires an explicit key press or click to advance. This is the most impactful viewer gap for everyday use and a direct differentiation weakness vs. web-based tools.

**What is needed:** A `ViewMode.CONTINUOUS` enum value in `view_tool.py`. The render pane replaces the single `QLabel` canvas with a `QScrollArea` containing a `QVBoxLayout` of per-page `QLabel` widgets, rendered lazily as the user scrolls. The existing `FIT_PAGE` / `FIT_WIDTH` zoom logic applies per-page. The undo/redo stack and search highlight overlay must be adapted to the multi-canvas model.

### No interactive form fill and save (P1)
The AcroForm overlay renders form widgets visually but the user cannot fill a form and save it from within the viewer. The workflow today requires separate tools: open in viewer, close it, open `form_unlock_tool`, export data. There is no "fill this form → save" path. For everyday document workflows, this is essential.

**What is needed:** The existing read-only AcroForm overlay widgets (text, checkbox, combo, radio, list, button) in `view_tool.py` need to become editable. On save (`Ctrl+S` or Save button), field values are written back to the PDF via `fitz.Widget.update()` before `fitz.Document.save()`.

### No thumbnail sidebar in viewer (P1)
There is no page thumbnail panel in the viewer. Navigating a 100-page document requires the page number input or key presses. All professional PDF viewers have a left sidebar for quick navigation.

**What is needed:** A collapsible `QDockWidget` or fixed left panel containing a `QListWidget` of page thumbnails (rendered at ~120px width). Clicking a thumbnail jumps to that page. Thumbnails reuse the existing LRU cache in `view_tool.py`.

### Batch tool covers only 4 operations (P1)
`batch_tool.py` exposes compress, rotate, add page numbers, and add/remove password. There are 42 tools. Power users who want to batch-watermark, batch-redact, batch-convert to PDF/A, or batch-extract images have no path. This is a significant limitation for the use case where PDFree is strongest: local processing of many files at once.

**What is needed:** Refactor `batch_tool.py` to drive operations through the tool registry rather than a hardcoded list. Each tool that supports a headless "apply to file" interface exposes a `batch_apply(input_path, output_path, **kwargs) -> None` classmethod. The batch UI generates per-operation option panels dynamically.

### No character-level text selection (P2)
Text selection in the viewer is flow-based. Users cannot select a precise phrase without capturing surrounding content. This is a known hard problem with raster-rendered PDFs.

**What is needed:** Use `fitz.Page.get_text("rawdict")` to extract character bounding boxes. Render an invisible hit-test overlay of character rectangles on mouse-down. On drag, highlight intersecting character rects and accumulate selected text. This is a substantial rewrite of the selection layer in `view_tool.py`.

---

## Dimension 3 — Developer Experience & Tooling

### 22 of 42 tools have no unit tests (P0)
More than half the tool surface area has no dedicated tests. The untested tools include the most-used operations: split, merge, compress, rotate, crop, remove, reorder, extract images, flatten, headers/footers, compare, add page numbers, change metadata, add image, and all conversion tools. A regression in `compress_tool.py` or `rotate_tool.py` would ship undetected.

**Untested tools (22):**
`split_tool`, `merge_tool`, `compress_tool`, `rotate_tool`, `crop_tool`, `remove_tool`, `reorder_tool`, `compare_tool`, `extract_images_tool`, `flatten_tool`, `headers_footers_tool`, `remove_annotations_tool`, `change_metadata_tool`, `add_image_tool`, `add_page_numbers_tool`, `sanitize_tool`, `img_to_pdf_tool`, `pdf_to_word_tool`, `pdf_to_img_tool`, `html_to_pdf_tool`, `office_to_pdf_tool`, `ocr_tool`

**What is needed:** One test file per tool, testing the worker's `run()` method directly with a real PDF fixture from `tests/corpus/`. Each test verifies the output file exists, is a valid PDF, and the operation had the expected effect (e.g., split produces N files, rotate changes page rotation, compress reduces file size).

### No linting gate in CI (P1)
`ruff format` and `ruff check` are documented as local requirements in CLAUDE.md but not enforced in CI. Unformatted or lint-failing code can merge.

**What is needed:** Add `ruff format --check .` and `ruff check .` steps to the `test` job in `release.yml`, before pytest runs.

### No code coverage reporting (P1)
pytest runs on every push but no coverage metrics are collected. The 22-tool testing gap is invisible to reviewers and maintainers.

**What is needed:** Add `pytest-cov` to dev dependencies. Run `pytest --cov=. --cov-report=term-missing --cov-fail-under=60` in CI. Set the initial threshold at 60% and raise it as tests are added.

### No `.env.example` (P2)
Only `PDFREE_STATE_DIR` is documented, and only in `docs/ENV.md`. There is no `.env.example` file at the repo root.

**What is needed:** A `.env.example` with `PDFREE_STATE_DIR=~/.pdfree` and any other env vars as they are added.

---

## Dimension 4 — Architecture & Code Quality

### No `BaseTool` abstract class (P1)
The two-panel layout + `QThread` worker pattern is consistent across all 42 tools but enforced purely by convention. There is no base class that formalizes the contract: `_modified: bool`, `cleanup()`, `load_file(path)`, left/right panel split, worker signal wiring. New contributors learn the pattern by reading existing tools. The batch tool also cannot query what operations are available — it hardcodes its 4 operations instead of interrogating the tool registry.

**What is needed:** An abstract `BaseTool(QWidget)` in a new `base_tool.py` with `@abstractmethod cleanup()` and `@property _modified`. Tools opt into the `batch_apply` interface by implementing a classmethod. Existing tools migrate incrementally — the base class is introduced and tools are migrated one at a time without breaking the app.

### `view_tool.py` is 4641 lines (P1)
The viewer contains the annotation suite, search bar, form overlay, two-up mode, printing, measurement tool, link handling, undo/redo, and thumbnail cache in one file. This is the highest-risk file for merge conflicts and regressions.

**What is needed:** Extract into four focused modules:
- `_render_pane.py` — page rendering, zoom, scroll, pixmap cache, undo/redo stack
- `_annotation_tools.py` — all 13 annotation types and their toolbar
- `_form_overlay.py` — AcroForm widget creation and value read/write
- `_search_bar.py` — search input, highlight overlay, match count

`view_tool.py` becomes the assembly shell (~500 lines).

### Batch tool processes files sequentially (P2)
`batch_tool.py` uses a single `QThread` and processes files one at a time. The `worker_semaphore` exists to safely cap concurrency but the batch tool does not use it.

**What is needed:** Spawn one `_BatchItemWorker` per file. Each worker acquires the semaphore before running and releases it on completion. The UI collects signals from all workers and updates per-file status rows independently.

### Duplicate `_PreviewCanvas` (P2)
`split_tool.py` and `pdf_to_csv_tool.py` each define their own `_PreviewCanvas` independently. A bug in one is unlikely to be fixed in the other.

**What is needed:** Extract a shared `PreviewCanvas(QLabel)` into `utils.py` or a new `widgets.py`. Both tools import it.

---

## Dimension 5 — Production Readiness

### No backup before destructive saves (P0 — see Dimension 1)
Restated here: there is no recovery path if a tool save fails mid-write. The fix is a shared `backup_original()` utility called in all tool workers before `fitz.save()`.

### File locking not detected (P1)
On Windows, if the target PDF is open in another application, `fitz.save()` fails with a `PermissionError`. The current error handling surfaces this as a generic "operation failed" message. A targeted check with a clear message ("The file is open in another application — close it and try again") would prevent a significant share of user confusion.

**What is needed:** In each tool worker's `run()` method, wrap the initial file open in a targeted `PermissionError` handler before the main operation begins. Alternatively, add a shared `assert_file_writable(path)` utility in `utils.py` that probes write access before the worker starts.

### Auto-updater is detect-only (P2)
`updater.py` detects a newer release and shows a banner, but the user must manually navigate to the release page and download. A direct link to the platform-specific download URL in the banner would remove one friction step without requiring auto-install infrastructure.

**What is needed:** The `update_available` signal payload includes the GitHub release download URL for the current platform (Windows: `*_Setup.exe`, macOS: `*.dmg`, Linux: `*.AppImage`). The banner shows a "Download" button that opens the URL in the system browser.

### No crash reporting (P2)
Rotating log files capture exceptions but there is no mechanism for users to submit them. When something fails silently, there is no signal to the developer.

**What is needed:** A global `sys.excepthook` override in `main.py` that catches unhandled exceptions, writes the traceback to the log, and shows a modal offering to copy the last log entry to the clipboard for pasting into a GitHub issue. No third-party service required.

---

## Cross-Cutting Priority Table

| # | Gap | Dimension | Priority | Effort | v1.0 blocker | Differentiator |
|---|-----|-----------|----------|--------|:---:|:---:|
| 1 | Code signing (Windows + macOS) | Security | P0 | Medium | ✅ | — |
| 2 | Backup before destructive saves | Security / Prod | P0 | Small | ✅ | — |
| 3 | Continuous scroll in viewer | UX | P0 | Large | ✅ | ✅ |
| 4 | 22 untested tools | DX | P0 | Large | ✅ | — |
| 5 | Interactive form fill + save | UX | P1 | Large | — | ✅ |
| 6 | Thumbnail sidebar in viewer | UX | P1 | Medium | — | ✅ |
| 7 | Expand batch tool to all operations | UX | P1 | Medium | — | ✅ |
| 8 | File locking detection | Prod | P1 | Small | — | — |
| 9 | Linting gate in CI | DX | P1 | Small | — | — |
| 10 | Code coverage reporting | DX | P1 | Small | — | — |
| 11 | `BaseTool` abstract class | Architecture | P1 | Medium | — | — |
| 12 | Split `view_tool.py` into modules | Architecture | P1 | Large | — | — |
| 13 | Security scanning in CI | Security | P1 | Small | — | — |
| 14 | One-click updater download link | Prod | P2 | Small | — | ✅ |
| 15 | Batch tool parallelization | Architecture | P2 | Small | — | ✅ |
| 16 | Character-level text selection | UX | P2 | Large | — | ✅ |
| 17 | Crash reporting (clipboard modal) | Prod | P2 | Small | — | — |
| 18 | Deduplicate `_PreviewCanvas` | Architecture | P2 | Small | — | — |
| 19 | `.env.example` | DX | P2 | Tiny | — | — |

### Recommended sequencing for v1.0

**Sprint 1 — Trust (all P0, small/medium effort first):**
Backup utility → file locking detection → linting CI gate → coverage CI gate → security scanning CI gate → code signing setup

**Sprint 2 — Viewer (the two large P0/P1 UX items):**
Continuous scroll → thumbnail sidebar

**Sprint 3 — Test coverage (P0 DX, large effort):**
22 missing tool unit tests, in order of tool usage frequency

**Sprint 4 — Differentiation (P1 UX):**
Interactive form fill + save → expand batch tool → `BaseTool` base class

**Sprint 5 — Polish (P2):**
One-click updater link → batch parallelization → crash reporting → `_PreviewCanvas` dedup → `.env.example`

**Deferred:**
`view_tool.py` module split and character-level text selection — both are Large effort with no v1.0 blocker status. Schedule for post-launch.
