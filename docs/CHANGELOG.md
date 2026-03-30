# Changelog

All changes in reverse chronological order. Dates are YYYY-MM-DD.

---

## [1.0.0] — 2026-03-31

### Added
- Multi-document tab support: open multiple PDFs simultaneously in the viewer; each tab maintains independent zoom, rotation, page position, and undo stack
- Split view: side-by-side display of two independent panes; left pane from active tab, right pane is independent and opens same file at page 0
- Clickable links: URI links open in system browser via `QDesktopServices`; GOTO links navigate within the document; hover shows PointingHandCursor
- Reading position memory: last-viewed page persisted in `library.json` via `LibraryState.get_last_page()` / `set_last_page()`; restored on file reopen with clamping
- Unsaved-changes dialogs: per-tab Save/Discard/Cancel on tab close; aggregate Save All/Discard All/Cancel on app quit
- `_RenderPane` class: new per-document state container extracted from `ViewTool` (holds doc, page count, zoom, rotation, undo/redo, search state, form widgets)
- `LibraryState.get_last_page()` / `set_last_page()`: retrieve and persist the last-viewed page number for any PDF path
- `validate_signature_tool.py`: new tool — validates all embedded digital signatures in a PDF via pyhanko; reports trust status, document integrity, signer DN, signing time, and timestamp presence in scrollable result cards
- `sign_tool.py`: optional TSA timestamping — "TIMESTAMP (OPTIONAL)" field in left panel; when non-empty, passes `HTTPTimeStamper` to `signers.sign_pdf()` for RFC 3161 timestamp embedding
- `main.py`: wired `validate_signature` into IMPLEMENTED, CATEGORIES (Sign & Security), TOOL_DESCRIPTIONS, and `_open_tool` dispatch
- `icons.py`: added `shield-check` icon (shield outline with inner check path)
- `tests/test_validate_signature.py`: 5 tests covering empty-list for plain PDF, missing-file raises, required result keys, validation error caught, no-signatures mocked empty list
- `sign_tool.py`: cryptographic PDF signing with PKCS#12 certificates via pyhanko; signature placement presets; background worker; page preview with signature box overlay
- `pyhanko>=0.21` dependency added to requirements.txt
- `view_tool.py`: search results panel — scrollable list below search bar showing every match with page number and text snippet; clicking a row jumps to that result; current match highlighted in blue; panel auto-shows/hides with search bar
- `tests/test_integration.py`: 11 integration tests covering merge (page count, order, error path), split by ranges, compress lossless + lossy, and watermark stamp across all positions
- `add_password_tool.py`: permission flag editing for already-encrypted PDFs — loads encrypted file by prompting for owner password, reads current permission flags into checkboxes, shows re-encrypt banner; saves with new passwords + updated permissions
- `view_tool.py`: LRU thumbnail pixmap cache — replaces unbounded list with a 200-entry `OrderedDict`; evicts oldest entry (clears its label) when the limit is hit, keeping memory bounded for large documents
- `PDFree-linux.spec`: PyInstaller onedir spec for Linux builds
- `.github/workflows/release.yml`: Linux CI job — builds onedir bundle, assembles AppDir, produces `PDFree-x86_64.AppImage` via appimagetool; release job now uploads all three platform artifacts
- `form_unlock_tool.py`: new tool — clears the ReadOnly bit on every AcroForm widget field; reports how many fields were unlocked
- `main.py`: wired `html_to_pdf`, `office_to_pdf`, `pdf_to_csv`, `form_unlock` into IMPLEMENTED, CATEGORIES, TOOL_DESCRIPTIONS, and `_open_tool` dispatch
- `tests/test_form_unlock.py`: 5 tests covering unlock success, valid output, no-field no-op, source unchanged, missing-file error
- `tests/corpus/`: 6 committed PDF fixtures — plain, multipage, password-protected, form, annotated, corrupt
- `tests/test_corpus.py`: 13 corpus smoke tests covering open, text, fields, annotations, auth, corrupt tolerance
- `view_tool.py`: large-file warning — files >150 MB prompt the user before loading (P1.4)
- `form_export_tool.py`: new tool — iterates all AcroForm widgets via `fitz.Page.widgets()`, displays field name/type/value in a sortable table, exports as JSON or CSV; background QThread worker for extraction
- `main.py`: wired `form_export` into IMPLEMENTED, CATEGORIES (Sign & Security), TOOL_DESCRIPTIONS, and `_open_tool` dispatch
- `tests/test_form_export.py`: 8 tests covering field count, names, values, page numbers, empty PDF, JSON roundtrip, CSV roundtrip, CSV header
- `redact_tool.py`: text/regex auto-redaction — "FIND & REDACT TEXT" section in left panel with search entry, case-sensitive and regex toggles, and "Add All Matches" button; iterates all pages using `fitz.Page.search_for()` or regex extraction, appends matched rects to `_all_rects`, refreshes current page canvas and reports total match count
- `tests/test_redact_text.py`: 5 tests covering plain search, redaction removes text, regex match extraction, case-insensitive search, no-match case

### Changed
- `PDFCanvas` now accepts `_RenderPane` instead of `ViewTool` directly; canvas stores `self._pane` for document state and `self._vt` for toolbar state
- Undo/redo stack moved to per-pane ownership in `_RenderPane` (was global per-ViewTool)

### Internal
- Extracted `_RenderPane(QWidget)` as per-document state and UI container from `ViewTool`; moved page rendering, navigation, and undo/redo into this class

---

## 2026-03-19

### feat: add two-up scroll mode tests

- Two-up (facing pages) layout in ViewTool was already fully implemented (`_render_page_twoup`, `_set_mode_twoup`, `_set_mode_single`, paint event handling `_pixmap2`, navigation step of 2).
- Added 11 tests in `tests/test_view_twoup.py`: ViewMode constants, navigation step logic, method signatures, mode toggle state, button checked state.

---

### feat: expose accessibility permission in Add Password

- Added "Allow extraction for accessibility" checkbox to the PERMISSIONS section.
- Maps to `fitz.PDF_PERM_ACCESSIBILITY` (PDF spec bit 10 — extract text/graphics for accessibility).
- Checked by default (permissive). Uncheck to set `preventExtractForAccessibility`.
- Affected: add_password_tool.py — `PERMISSIONS`, `_save()`.

---

### feat: search match count display

- Search bar in ViewTool now shows "N of M" (e.g. "3 of 17") instead of "N/M".
- Zero-results label changed from "0 results" to "No results".
- Affected: view_tool.py — `_goto_search_result()`, `_do_search()`.

---

### feat: add fullscreen mode

- F11 toggles fullscreen via `QMainWindow.showFullScreen()` / `showNormal()`.
- `PDFreeApp._toggle_fullscreen()` checks `isFullScreen()` and switches accordingly.
- `QShortcut(QKeySequence(Qt.Key.Key_F11))` wired in `__init__`.

---

### feat: add i18n scaffolding

- `i18n.py` — `tr(text)` wrapper around `QCoreApplication.translate("PDFree", text)`; `QT_TRANSLATE_NOOP(context, text)` no-op marker for module-level strings.
- `main.py` — all CATEGORIES titles and tool names, all TOOL_DESCRIPTIONS values, all TAB_CATEGORIES keys wrapped with `QT_TRANSLATE_NOOP`; `tr()` called at widget-creation sites (ToolCard name/description, RecentCard name/description, tab buttons, `_tool_display_name`, home screen labels).
- `translations/pdffree_en.ts` — base English catalogue generated by `pyside6-lupdate main.py i18n.py`; 82 translatable strings extracted.
- Pattern: add new translatable strings with `QT_TRANSLATE_NOOP("PDFree", "string")` at definition and `tr(var)` at widget-creation time; run `pyside6-lupdate` to update the catalogue.
- 8 tests in `tests/test_i18n.py`.

---

### feat: add PDF/A export tool

- `pdfa_tool.py` (`PDFATool`) — best-effort conversion to PDF/A-1b, -2b, or -3b.
- Three version cards (PDF/A-1b / -2b / -3b); selected card highlighted.
- Four sanitisation checkboxes: remove JavaScript, embedded files, hidden text, thumbnails — applied via `fitz.Document.scrub()`.
- `convert_to_pdfa()` pure helper: scrubs, injects XMP `pdfaid:part` / `pdfaid:conformance` declaration via `fitz.Document.set_xml_metadata()`, saves with `garbage=4, deflate=True, encryption=NONE`.
- Background `_PDFAWorker(QThread)` keeps UI responsive; emits `progress`, `finished`, `failed` signals.
- Amber "best-effort" notice in right panel referencing VeraPDF for certified validation.
- 8 tests in `tests/test_pdfa_tool.py`.
- Wired into `IMPLEMENTED`, `CATEGORIES` (Advanced), and `TOOL_DESCRIPTIONS`.

---

### feat: add bookmark editor tool

- `bookmarks_tool.py` (`BookmarksTool`) — view, add, remove, rename, and reorder PDF bookmarks.
- Right panel: `QTreeWidget` showing the full TOC hierarchy. Selecting an entry populates the left panel editor (title, target page, nesting level 1–6).
- Left panel: edit fields with "Apply Changes", plus Add / Remove / Move Up / Move Down actions.
- Remove deletes the selected entry and all its children (entire subtree).
- Move Up / Move Down reorder sibling entries while keeping children attached.
- Pure helpers `toc_remove`, `toc_move_up`, `toc_move_down` operate on the flat `[[level, title, page]]` list; fully tested independently.
- Reads existing TOC via `fitz.Document.get_toc()`; writes via `doc.set_toc()`.
- 16 tests in `tests/test_bookmarks.py`.
- Wired into `IMPLEMENTED`, `CATEGORIES` (View & Edit), and `TOOL_DESCRIPTIONS`.

---

### feat: add page labels tool

- `page_labels_tool.py` (`PageLabelsTool`) — define custom page numbering ranges for any PDF.
- Supports all 6 PDF label styles: Arabic (D), Roman lower (r), Roman upper (R), Alpha lower (a), Alpha upper (A), None.
- Each range specifies: first page, style, optional prefix, and start number. Multiple ranges combine (e.g. Roman for pages 1–4, Arabic for pages 5+).
- Right panel shows a live preview table (Physical Page → Label) that updates as ranges are edited.
- Reads and populates existing label ranges from the loaded PDF via `fitz.Document.get_page_labels()`.
- Saves via `fitz.Document.set_page_labels()` + `doc.save()`.
- 14 tests in `tests/test_page_labels.py`.
- Wired into `IMPLEMENTED`, `CATEGORIES` (View & Edit), and `TOOL_DESCRIPTIONS`.

---

### feat: add dark mode / theme toggle

- `theme.py` — defines LIGHT and DARK colour palettes; `apply_theme(dark)` mutates `colors` module constants so all subsequently created widgets use the new palette; saves preference to `theme.json` in the log directory.
- `colors.py` — added `HOME_BORDER`, `HOME_SEARCH_BG`, `HOME_SEARCH_TXT`, `HOME_TEXT` tokens; updated `SIDEBAR_BG` to match actual home-screen value.
- `main.py` — `_build_home*` and related methods updated to use `colors.X` references instead of raw hex literals; moon/sun toggle button added to home header; `_toggle_theme()` applies theme and rebuilds home; startup applies saved preference via `apply_theme(is_dark())`.
- Theme affects all newly created widgets; tools opened after a toggle use the new palette. Home screen rebuilds immediately on toggle.
- 6 tests in `tests/test_theme.py`.

---

### feat: add batch processing tool

- `batch_tool.py` (`BatchTool`) — apply one operation to multiple PDFs at once.
- Operations: Compress (lossless/lossy presets), Rotate Pages, Add Page Numbers, Add Password, Remove Password.
- File list with per-file status badges (Pending / Processing / Done / Error), drag-and-drop support, remove button.
- `_BatchWorker(QThread)` processes files sequentially; emits `file_done` / `file_failed` / `all_done` signals.
- Output folder configurable; defaults to the directory of the first input file.
- Wired into `IMPLEMENTED`, `CATEGORIES` (Advanced), and `TOOL_DESCRIPTIONS` in `main.py`.
- 13 tests in `tests/test_batch_tool.py`.

---

## 2026-03-17

### feat: add 8 new tools — flatten, sanitize, extract images, scale pages, headers/footers, N-up layout, PDF to Excel, compare

- `flatten_tool.py` (`FlattenTool`) — bake annotations/form fields into static content via `fitz.bake()`; optionally remove JS and links via `fitz.scrub()`.
- `sanitize_tool.py` (`SanitizeTool`) — strip JS, embedded files, metadata, thumbnails, XML streams via `fitz.scrub()`; optional repair pass.
- `extract_images_tool.py` (`ExtractImagesTool`) — enumerate embedded images via `fitz.get_page_images()`, deduplicate by xref, export as PNG or JPEG.
- `scale_pages_tool.py` (`ScalePagesTool`) — resize all pages to A4/Letter/A3 or custom mm dimensions; letterbox or stretch mode.
- `headers_footers_tool.py` (`HeadersFootersTool`) — stamp left/center/right header and footer text on every page; variable substitution (`{page}`, `{total}`, `{date}`, `{filename}`); live preview.
- `nup_tool.py` (`NUpTool`) — 2-up, 4-up, and booklet layouts using `fitz.show_pdf_page()`.
- `pdf_to_excel_tool.py` (`PDFToExcelTool`) — extract tables via pdfplumber, write to `.xlsx` with openpyxl; bold headers, auto-fit columns.
- `compare_tool.py` (`CompareTool`) — side-by-side visual diff (pixel block comparison, red highlight overlay) and text diff (difflib word-level, coloured HTML).
- Added `openpyxl>=3.1` to `requirements.txt`.
- Wired all 8 tools into `IMPLEMENTED` and `_load_tool()` in `main.py`.
- Added `headers_footers`, `nup`, `pdf_to_excel` entries to `CATEGORIES` and `TOOL_DESCRIPTIONS`.

---

## 2026-03-15 (change metadata tool)

### feat: add Change Metadata tool

- New `change_metadata_tool.py`: `ChangeMetadataTool` — view and edit all 8 standard PDF metadata fields.
- Left panel: drop zone + 8 editable fields (Title, Author, Subject, Keywords, Creator, Producer, Creation Date, Modification Date); Keywords is multi-line, others single-line.
- Right panel: "Current Metadata" card showing values read from the loaded file; "How it works" tip card.
- Saves via `fitz.Document.set_metadata()` + `save(garbage=3, deflate=True)`.
- Wired into `IMPLEMENTED` set and `_load_tool()` in `main.py`.

---

## v1.0 — Current State (baseline as of 2026-03-15)

Everything listed under the individual releases below exists in the codebase today. See `docs/project-state/FEATURES.md` for the full feature catalog.

**Modules shipped:** `main.py`, `library_page.py`, `view_tool.py`, `split_tool.py`, `excerpt_tool.py`, `pdf_to_csv_tool.py`, `utils.py`, `colors.py`, `icons.py`

**Implemented tools:** View PDF (full annotation suite), Excerpt Tool (region capture), Split, PDF → CSV (table extraction)

**Packaging:** Windows `.exe` + Inno Setup installer, macOS `.app` + optional `.dmg` via `build-mac.sh`, GitHub Actions release workflow

---

## 2026-03-15 (convert + page numbers tools)

### feat: add Image→PDF, PDF→Image, and Add Page Numbers tools

- New `img_to_pdf_tool.py`: `ImgToPDFTool` — ordered image list (JPEG/PNG/BMP/GIF/TIFF/WebP) → single PDF. Page size presets (A4, Letter, Fit to Image), margin options, per-image reorder/remove, image preview.
- New `pdf_to_img_tool.py`: `PDFToImgTool` — exports selected PDF pages as PNG or JPEG. Clickable thumbnail grid (all selected by default), DPI selector (72–300), JPEG quality slider, output folder picker.
- New `add_page_numbers_tool.py`: `AddPageNumbersTool` — stamps page numbers via `fitz.Page.insert_textbox()`. Options: 6 positions, 5 formats (1 / Page 1 / 1/N / Page 1 of N / - 1 -), font size, start number, skip N pages. Right panel shows a live preview that updates 200 ms after any setting change.
- All three tools wired into `IMPLEMENTED` set and `_load_tool()` in `main.py`.

---

## 2026-03-15 (password tools)

### feat: add Add Password and Remove Password tools

- New `add_password_tool.py`: `AddPasswordTool` — encrypts a PDF with user + owner passwords.
  - Selectable encryption: AES-256 (default), AES-128, RC4-128.
  - 7 permission checkboxes: Print, Print HQ, Copy, Modify, Annotate, Forms, Assemble.
  - User password confirmation field with inline mismatch error.
  - Rejects already-protected files at load time.
- New `remove_password_tool.py`: `RemovePasswordTool` — strips encryption from a PDF.
  - Detects encryption status on load; shows colored badge (locked/unlocked).
  - Inline unlock step: enter password → verify → Save button activates.
  - Non-encrypted files can be saved directly without a password step.
  - Saves with `fitz.PDF_ENCRYPT_NONE`.
- Both tools wired into `IMPLEMENTED` set and `_load_tool()` in `main.py`.

---

## 2026-03-15 (compress tool)

### feat: add Compress tool

- New `compress_tool.py`: `CompressTool` widget for reducing PDF file size.
- Four selectable presets: Lossless (garbage-collect + deflate), Print (150 DPI re-render), eBook (96 DPI), Screen (72 DPI).
- Lossless uses `fitz.Document.save(garbage=4, deflate=True, deflate_images=True, deflate_fonts=True, clean=True, use_objstms=True)`.
- Lossy presets re-render each page as a raster image at the target DPI into a new fitz document.
- Right panel shows original file info before compression and a result card with actual savings after.
- `IMPLEMENTED` set and `_load_tool()` in `main.py` updated.

---

## 2026-03-15 (rotate tool)

### feat: add Rotate Pages tool

- New `rotate_tool.py`: `RotateTool` widget for rotating individual or all pages of a PDF.
- Right panel: 4-column thumbnail grid; click pages to select (blue highlight). Thumbnails re-render immediately after rotation to show the live result.
- Left panel: per-selection rotate (90° CCW, 90° CW, 180°) and rotate-all shortcuts, Select All / Deselect All, output filename, Save button.
- Rotation angle shown as a badge on each cell; zero-rotation pages show no badge.
- Save via `pypdf.PdfWriter` + `PageObject.rotate()` on changed pages only.
- `IMPLEMENTED` set and `_load_tool()` in `main.py` updated.

---

## 2026-03-15 (remove tool)

### feat: add Remove Pages tool

- New `remove_tool.py`: `RemoveTool` widget for deleting selected pages from a PDF.
- Right panel shows a scrollable thumbnail grid; click any page to toggle it marked for removal (red overlay + X).
- Left panel: file browse/drop, selection summary, Select All / Deselect All / Invert Selection, output filename, Remove button.
- Thumbnails are rendered lazily in batches of 8 via `QTimer` to keep UI responsive on large PDFs.
- Save uses `pypdf.PdfWriter.add_page()` to write only the kept pages.
- Guard: disallows removing all pages (at least one must remain).
- `IMPLEMENTED` set and `_load_tool()` in `main.py` updated.

---

## 2026-03-15 (merge tool)

### feat: add Merge tool

- New `merge_tool.py`: `MergeTool` widget combining multiple PDFs into one.
- Features: multi-file add via browse or drag-and-drop, per-file up/down reorder, remove, page preview with prev/next navigation, thumbnail strip, configurable output filename, `pypdf.PdfWriter.append()` merge with progress bar.
- `IMPLEMENTED` set in `main.py` updated to include `"merge"`.
- `_load_tool()` in `main.py` wired to instantiate `MergeTool`.

---

## 2026-03-15

### `e22ed28` — Update README: point to ArthurWie repo and expand security bypass instructions
- Updated GitHub repository URL to ArthurWie account.
- Added step-by-step guides for bypassing Windows SmartScreen and macOS Gatekeeper (right-click method, System Settings, `xattr` terminal method).

### `8c25c0f` — Update GitHub Actions to Node.js 24-compatible versions
- Bumped `actions/checkout`, `actions/upload-artifact`, and `softprops/action-gh-release` to versions compatible with the Node.js 24 runner.
- Reason: GitHub deprecated Node.js 16/20 action runtimes.

### `d7e50ce` — Add macOS build: .app spec, build script, and GitHub Actions release workflow
- Added `PDFree-mac.spec` (PyInstaller spec for macOS `.app`).
- Added `build-mac.sh` (builds `.app`, optionally packages as `.dmg` via `hdiutil`).
- Added `.github/workflows/release.yml` — on push of a `v*` tag: builds Windows installer and macOS `.app`, uploads both as release assets.
- macOS spec: `bundle_identifier = com.fioerd.pdfree`, minimum macOS 11.0 (Big Sur), dark mode support flag.
- UPX disabled on macOS (unreliable).

---

## 2026-03-13

### `af9cd19` — Switch to onedir build and add Inno Setup installer script
- Switched PyInstaller from onefile to onedir mode (`exclude_binaries=True` + `COLLECT`). Output: `dist/PDFree/` folder with `PDFree.exe` + `_internal/`.
- Added `PDFree.iss` (Inno Setup 6 script): produces `PDFree_Setup.exe`, writes to `%ProgramFiles%\PDFree`, optional desktop shortcut, optional `.pdf` file association via registry.

### `1828312` — Add Windows .exe packaging and update README
- Added `PDFree.spec` (initial PyInstaller spec, onefile at this point).
- Hidden imports declared for pdfplumber, pdfminer, pypdf, fitz, PIL, PySide6.QtSvg.
- Excluded tkinter, matplotlib, numpy, scipy, pandas from bundle.
- Added `LOGO.ico` reference.
- Updated README with Windows installation instructions.

---

## 2026-03-12

### `9da5456` — Add quick macOS setup option and fix Python version requirement
- Clarified Python 3.11+ minimum requirement (previously implied 3.10).
- Added a faster macOS setup path to README.

### `8084c27` — Add pypdf to requirements and expand macOS setup instructions
- Added `pypdf>=4.0` to `requirements.txt` (was omitted from initial release).
- Expanded README macOS section.

### `b01659e` — Merge branch 'main' into fix/mac-compatibility
- Merge commit resolving the mac-compatibility fix branch.

### `ad1b17c` — Fix Python 3.10+ type hint syntax and improve macOS setup instructions
- Replaced `Union[X, Y]` and `Optional[X]` annotations with `X | Y` syntax (Python 3.10+).
- Fixed `list[str]`, `tuple[int, int]` return annotations in `library_page.py`.
- Reason: PySide6 6.7 requires Python 3.9+ but annotations were using 3.12-only syntax in some places.

### `6b1439e` — Fix directory name in README instructions
- Corrected a wrong folder name in the manual setup steps.

### `72ddaaa` — Update repository URL in installation instructions
- Corrected the `git clone` URL in README.

### `2c34a3b` — Fix cross-platform compatibility for reveal-in-folder actions
- Fixed `subprocess` calls for "Reveal in Finder" (macOS) and "Show in Explorer" (Windows) to use the correct platform-specific commands.
- Affected: `library_page.py`, possibly `pdf_to_csv_tool.py`.

### `83fef27` — Initial public release – PDFree v1.0.0
- First public commit. All core modules added in a single commit (12 052 lines across 14 files).
- Included: `main.py`, `view_tool.py`, `split_tool.py`, `excerpt_tool.py`, `pdf_to_csv_tool.py`, `library_page.py`, `utils.py`, `colors.py`, `icons.py`.
- Also included: `README.md`, `LICENSE` (MIT), `LOGO.svg`, `.gitignore`, `requirements.txt` (without pypdf).

---

## Template for future entries

```
## YYYY-MM-DD

### `<hash>` — <commit title>
- <bullet: what changed>
- <bullet: why, if not obvious>
- Affected: <files>
```
