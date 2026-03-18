# Changelog

All changes in reverse chronological order. Dates are YYYY-MM-DD.

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
