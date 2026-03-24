# Troubleshooting

Known issues, workarounds, and unusual patterns found in the codebase. New entries go at the bottom of the "Known Issues" section.

---

## Known Issues

### 1. `view_tool.py` redefines `SIDEBAR_BG` locally
**Location:** `view_tool.py` lines 106–108
**What:** `view_tool.py` declares its own local `SIDEBAR_BG = "#E2E6EC"`, shadowing the `colors.py` token `SIDEBAR_BG = "#FAFBFC"` (which is imported by `excerpt_tool.py`).
**Impact:** The viewer sidebar uses a different background color (`#E2E6EC`, a darker slate) than the design system token intended. This is probably intentional (the viewer sidebar is structurally different), but the naming collision is a maintenance hazard — importing `SIDEBAR_BG` from `colors.py` in `view_tool.py` would return the wrong value.
**Recommendation:** Rename the view_tool-local constant to `VIEWER_SIDEBAR_BG` or add it to `colors.py` under a distinct name. Do not change without checking visual regression.

---

### 2. All PDF rendering runs on the main Qt thread
**Location:** All tool modules
**What:** `fitz.Page.get_pixmap()` and related rendering calls are executed synchronously on the main thread. For large PDFs or slow disks this can stall the UI.
**Current mitigation:** Thumbnail rendering uses `QTimer.singleShot(0, ...)` to defer batch work, keeping the UI responsive between frames.
**Impact:** The UI may freeze briefly when opening a large PDF or during table extraction (`pdf_to_csv_tool.py`).
**Recommendation:** Migrate heavy rendering and IO to `QThread` or `QRunnable` with signals for result delivery. See `CLAUDE.md` Python Pitfalls section.

---

### 3. pytest not installed in `.venv`
**Location:** `requirements.txt`, `.venv/`
**What:** `requirements.txt` lists `pytest>=8.0` but the `.venv` does not have it installed (running `python -m pytest` fails with "No module named pytest").
**Fix:** Run `pip install -r requirements.txt` inside the active venv.

---

### 4. Same class name `_PreviewCanvas` in two modules
**Location:** `split_tool.py`, `pdf_to_csv_tool.py`
**What:** Both modules define a private class named `_PreviewCanvas` with different implementations (split_tool draws cut lines; pdf_to_csv draws table overlay boxes).
**Impact:** None at runtime (different namespaces). However, searching the codebase for `_PreviewCanvas` returns both, and refactoring one could be confused with the other.
**Recommendation:** If either is ever promoted to a shared component, rename before moving. Otherwise leave as-is.

---

### 5. `LibraryState` data model uses a list for files, not a dict
**Location:** `library_page.py` — `LibraryState._load()` and all query methods
**What:** `data["files"]` is a `list[dict]` scanned linearly for lookups. For large libraries (thousands of files) this is O(n).
**Impact:** Negligible for typical use (tens to low hundreds of files). Could become a performance issue for power users with hundreds of PDFs in the library.
**Recommendation:** If the library grows, migrate to `{"files": {path: entry}}` (dict keyed by path). This would require a schema migration (see `docs/DATABASE.md`).

---

### 6. Pillow (`Pillow>=10.0`) is in requirements but not imported anywhere in project code
**Location:** `requirements.txt`
**What:** Pillow is declared as a dependency but none of the project `.py` files import it directly.
**Impact:** Adds install time and bundle size.
**Why it may be needed:** PyMuPDF (fitz) can optionally use Pillow for certain image operations, and pdfplumber's image handling may pull it in transitively.
**Recommendation:** Leave it in `requirements.txt` for now as a transitively-required dependency. Do not remove without verifying the fitz and pdfplumber import chains.

---

### 7. No CI test job — tests are not run automatically
**Location:** `.github/workflows/release.yml`
**What:** The GitHub Actions workflow only builds and releases binaries. It does not run `pytest`.
**Impact:** Test regressions will not be caught until a developer runs tests locally.
**Recommendation:** Add a test job to the workflow. See the suggested YAML snippet in `docs/TESTING.md`.

---

### 8. `library_page.py` `LibraryState.data` property returns the raw mutable dict
**Location:** `library_page.py` — `data` property
**What:** `state.data` returns the live internal dict, not a copy. Callers could accidentally mutate it without triggering a save.
**Current usage:** Only test code accesses `state.data` directly. Application code uses the query methods.
**Impact:** Low risk while tests are the only callers, but fragile.
**Recommendation:** If additional callers are added, consider returning a deep copy or exposing only the query methods.

---

## Installation / Runtime Issues

### macOS: "App is damaged and can't be opened"
Gatekeeper quarantine flag is set on unsigned downloads.
```bash
xattr -cr /path/to/PDFree.app
```
Or right-click the app → Open → Open in the confirmation dialog.

### Windows: SmartScreen "Windows protected your PC"
The executable is not code-signed. Click "More info" → "Run anyway". To remove this for distribution, code-sign `PDFree_Setup.exe` with a trusted certificate:
```
signtool sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 /f cert.pfx PDFree_Setup.exe
```

### `fitz.FileDataError` on open
The selected file is corrupt or password-protected. PDFree does not currently support encrypted PDFs.

### Table extraction returns no tables
The PDF may use rasterized (image-based) tables. pdfplumber only detects text-layer tables. Try switching the detection method between Lattice, Stream, and Hybrid in the settings panel.

---

## Template for New Entries

```
### <N>. <Short title>
**Location:** `<file>` line(s) <N>
**What:** <Description of the issue or workaround>
**Impact:** <Who is affected and how>
**Recommendation:** <What to do about it, or "leave as-is because...">
```
