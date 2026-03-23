# Sprint 1 — Trust Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add backup-before-save, file-locking detection, CI quality gates (lint + coverage + security), code-signing scaffolding, and a `.env.example` file.

**Architecture:** Two new pure functions in `utils.py` (`backup_original`, `assert_file_writable`) are wired into all tool workers. CI gates are new steps in the existing `test` job in `release.yml`. Code-signing steps are added to the build jobs behind `if: startsWith(github.ref, 'refs/tags/')` guards and read certificates from GitHub Secrets (which must be provisioned separately by the user).

**Tech Stack:** Python 3.11, PySide6, PyMuPDF (fitz), pytest, ruff, bandit, pip-audit, pytest-cov, GitHub Actions

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Modify | `utils.py` | Add `backup_original` and `assert_file_writable` |
| Modify | `tests/test_utils.py` | Tests for both new utilities |
| Modify | `.github/workflows/release.yml` | Add ruff, bandit, pip-audit, pytest-cov steps; code-signing steps |
| Modify | `requirements.txt` | Add `pytest-cov`, `bandit[toml]`, `pip-audit` |
| Modify | all 42 `*_tool.py` workers | Wire `assert_file_writable` before write; catch `PermissionError` specifically |
| Create | `.env.example` | Document `PDFREE_STATE_DIR` env var |

---

## Task 1: `backup_original` and `assert_file_writable` utilities

**Files:**
- Modify: `utils.py`
- Modify: `tests/test_utils.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_utils.py` (or append if it exists):

```python
import shutil
from pathlib import Path
import pytest
from utils import backup_original, assert_file_writable


def test_backup_original_creates_bak(tmp_path):
    src = tmp_path / "input.pdf"
    src.write_bytes(b"%PDF-1.4 test")
    bak = backup_original(src)
    assert bak == src.with_suffix(".pdf.bak")
    assert bak.exists()
    assert bak.read_bytes() == src.read_bytes()


def test_backup_original_overwrites_stale_bak(tmp_path):
    src = tmp_path / "input.pdf"
    src.write_bytes(b"%PDF-1.4 new")
    bak = src.with_suffix(".pdf.bak")
    bak.write_bytes(b"%PDF-1.4 old")
    backup_original(src)
    assert bak.read_bytes() == b"%PDF-1.4 new"


def test_backup_original_missing_source_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        backup_original(tmp_path / "ghost.pdf")


def test_assert_file_writable_new_path_succeeds(tmp_path):
    assert_file_writable(tmp_path / "out.pdf")  # should not raise


def test_assert_file_writable_existing_writable_succeeds(tmp_path):
    f = tmp_path / "out.pdf"
    f.write_bytes(b"x")
    assert_file_writable(f)  # should not raise


def test_assert_file_writable_readonly_raises(tmp_path):
    import stat
    f = tmp_path / "locked.pdf"
    f.write_bytes(b"x")
    f.chmod(stat.S_IREAD)
    try:
        with pytest.raises(PermissionError):
            assert_file_writable(f)
    finally:
        f.chmod(stat.S_IWRITE | stat.S_IREAD)
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_utils.py -v
```
Expected: `ImportError: cannot import name 'backup_original' from 'utils'`

- [ ] **Step 3: Implement both utilities in `utils.py`**

Add after the `sanitize_filename` function:

```python
import shutil
from pathlib import Path


def backup_original(src: Path) -> Path:
    """Copy src to src.bak before a destructive operation.

    Returns the .bak path. Raises FileNotFoundError if src does not exist.
    """
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(src)
    bak = src.with_suffix(src.suffix + ".bak")
    shutil.copy2(src, bak)
    return bak


def assert_file_writable(path: Path) -> None:
    """Raise PermissionError with a clear message if path cannot be written.

    Checks the parent directory for new files, or the file itself if it exists.
    Use before any fitz.save() / PdfWriter.write() call.
    """
    path = Path(path)
    if path.exists():
        try:
            path.open("r+b").close()
        except PermissionError:
            raise PermissionError(
                f"The file is open in another application. "
                f"Close it and try again.\n{path}"
            )
    else:
        parent = path.parent
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)
        if not os.access(parent, os.W_OK):
            raise PermissionError(
                f"Cannot write to folder: {parent}"
            )
```

Also add `import os` to the top of `utils.py`.

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_utils.py -v
```
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add utils.py tests/test_utils.py
git commit -m "feat: add backup_original and assert_file_writable utilities"
```

---

## Task 2: Wire utilities into all tool workers

**Files:**
- Modify: all 42 `*_tool.py` files (see list below)

The pattern to apply to every `QThread.run()` method that calls `fitz.save()` or `PdfWriter.write()`:

```python
# At the top of run(), before any PDF operations:
from utils import assert_file_writable, backup_original

assert_file_writable(Path(self._out_path))
backup_original(Path(self._pdf_path))   # only when input file exists

# Change bare except Exception to also catch PermissionError first:
except PermissionError as exc:
    self.failed.emit(str(exc))
except Exception as exc:
    logger.exception("operation failed")
    self.failed.emit(str(exc))
```

For tools where the output overwrites the source (batch tool), call `backup_original` then `assert_file_writable` on the same path.

For tools that write to a directory (e.g. split_tool writing N files), call `assert_file_writable` on a probe path: `assert_file_writable(Path(self._out_dir) / "_probe")`.

**Three tools have no QThread worker — investigate before wiring:**
`bookmarks_tool.py`, `excerpt_tool.py`, and `page_labels_tool.py` perform their save operations inline on the main thread (no `QThread` subclass). For each, run:
```
grep -n "fitz.save\|PdfWriter\|\.save(" bookmarks_tool.py
```
to find the save call site, then wrap it with `assert_file_writable(out_path)` at that point and `backup_original(src_path)` immediately before the write.

**Workers to update — verified class names (39 files with QThread workers):**

```
add_image_tool.py           _AddImageWorker
add_page_numbers_tool.py    _AddPageNumbersWorker
add_password_tool.py        _AddPasswordWorker
batch_tool.py               _BatchWorker
change_metadata_tool.py     _ChangeMetadataWorker
compare_tool.py             _ExportDiffWorker (export only)
compress_tool.py            _CompressWorker
crop_tool.py                _CropWorker
extract_images_tool.py      _ExtractImagesWorker
flatten_tool.py             _FlattenWorker
font_info_tool.py           _FontInfoWorker
form_export_tool.py         _ExtractWorker
form_unlock_tool.py         _FormUnlockWorker
headers_footers_tool.py     _HeadersFootersWorker
html_to_pdf_tool.py         _ConvertWorker
img_to_pdf_tool.py          _ImgToPdfWorker
merge_tool.py               _MergeWorker
nup_tool.py                 _NUpWorker
ocr_tool.py                 _OCRWorker
office_to_pdf_tool.py       _ConvertWorker
pdfa_tool.py                _PDFAWorker
pdf_to_csv_tool.py          _ExtractionWorker
pdf_to_excel_tool.py        _ExcelExtractionWorker
pdf_to_img_tool.py          _ExportImagesWorker
pdf_to_word_tool.py         _ConvertWorker
redact_tool.py              _RedactWorker
remove_annotations_tool.py  _RemoveAnnotationsWorker
remove_password_tool.py     _RemovePasswordWorker
remove_tool.py              _RemovePagesWorker
reorder_tool.py             _ReorderWorker
rotate_tool.py              _RotateWorker
sanitize_tool.py            _SanitizeWorker
scale_pages_tool.py         _ScalePagesWorker
sign_tool.py                _SignWorker
split_tool.py               _SplitWorker
svg_to_pdf_tool.py          _SvgToPdfWorker
validate_signature_tool.py  (read-only — skip)
watermark_tool.py           _WatermarkWorker
```

- [ ] **Step 1: Wire the first worker as a smoke test — `compress_tool.py`**

In `compress_tool.py`, find `_CompressWorker.run()`. Add at the top of the `try` block:

```python
from utils import assert_file_writable, backup_original
assert_file_writable(Path(self._out_path))
backup_original(Path(self._src_path))
```

Add `from pathlib import Path` at the top if not already present.

Change the except clause to:
```python
except PermissionError as exc:
    self.failed.emit(str(exc))
except Exception as exc:
    logger.exception("compress failed")
    self.failed.emit(str(exc))
```

- [ ] **Step 2: Run the full test suite to verify nothing broke**

```
pytest --tb=short -q
```
Expected: same pass count as before; no regressions

- [ ] **Step 3: Wire the remaining 41 workers**

Apply the same pattern to every worker listed above. For each file:
1. Add `from utils import assert_file_writable, backup_original` inside `run()` (or at file top if not already there)
2. Add `from pathlib import Path` at file top if not already there
3. Call `assert_file_writable(Path(self._out_path))` before the first `fitz.open` or `PdfWriter` call
4. Call `backup_original(Path(self._pdf_path))` if the worker receives a source file path
5. Add the `except PermissionError` clause before `except Exception`

- [ ] **Step 4: Run full test suite**

```
pytest --tb=short -q
```
Expected: same pass count as before; no regressions

- [ ] **Step 5: Commit**

```bash
git add $(git diff --name-only)
git commit -m "feat: wire backup_original and assert_file_writable into all tool workers"
```

---

## Task 3: CI — linting gate

**Files:**
- Modify: `.github/workflows/release.yml`

- [ ] **Step 1: Add ruff steps to the `test` job**

In `release.yml`, find the `test` job. After the `Install dependencies` step and before `Run tests`, add:

```yaml
      - name: Check formatting
        run: ruff format --check .

      - name: Lint
        run: ruff check .
```

- [ ] **Step 2: Add ruff to requirements.txt**

Add to `requirements.txt`:
```
ruff>=0.4
```

- [ ] **Step 3: Run locally to verify no issues**

```
ruff format --check .
ruff check .
```
Expected: both exit 0 (no issues). If issues exist, fix them first: `ruff format . && ruff check --fix .`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release.yml requirements.txt
git commit -m "ci: add ruff format and lint gates to test job"
```

---

## Task 4: CI — code coverage

**Files:**
- Modify: `.github/workflows/release.yml`
- Modify: `requirements.txt`

- [ ] **Step 1: Add pytest-cov to requirements.txt**

Add to `requirements.txt`:
```
pytest-cov>=5.0
```

- [ ] **Step 2: Replace the `Run tests` step in `release.yml`**

Change:
```yaml
      - name: Run tests
        run: pytest --tb=short -q
```
To:
```yaml
      - name: Run tests
        run: pytest --tb=short -q --cov=. --cov-report=term-missing --cov-fail-under=40
```

Note: threshold starts at 40% (current real coverage level). Raise it as tests are added.

- [ ] **Step 3: Verify locally**

```
pytest --tb=short -q --cov=. --cov-report=term-missing --cov-fail-under=40
```
Expected: passes, shows coverage report

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release.yml requirements.txt
git commit -m "ci: add pytest-cov coverage gate at 40%"
```

---

## Task 5: CI — security scanning

**Files:**
- Modify: `.github/workflows/release.yml`
- Modify: `requirements.txt`

- [ ] **Step 1: Add bandit and pip-audit to requirements.txt**

Add to `requirements.txt`:
```
bandit[toml]>=1.7
pip-audit>=2.7
```

- [ ] **Step 2: Add security steps to the `test` job in `release.yml`**

After the lint steps, before `Run tests`, add:

```yaml
      - name: Security scan (bandit)
        run: bandit -r . -ll --exclude ./.venv,./tests

      - name: Dependency vulnerability scan (pip-audit)
        run: pip-audit --ignore-vuln PYSEC-2022-42969
```

Note: `--ignore-vuln PYSEC-2022-42969` is a placeholder — run `pip-audit` locally first, check results, and only add ignores for accepted false positives with a comment explaining why.

- [ ] **Step 3: Run bandit locally and fix any high/medium findings**

```
bandit -r . -ll --exclude ./.venv,./tests
```
Expected: exit 0. Fix any `HIGH` or `MEDIUM` severity findings before proceeding.

- [ ] **Step 4: Run pip-audit locally**

```
pip-audit
```
Expected: exit 0. If CVEs are found, either update the affected package or add a documented ignore with reasoning.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/release.yml requirements.txt
git commit -m "ci: add bandit and pip-audit security scanning gates"
```

---

## Task 6: Code signing CI scaffolding

**Files:**
- Modify: `.github/workflows/release.yml`

> **User action required before this task:** Code signing requires external certificates:
> - **macOS:** Apple Developer account → Developer ID Application certificate → export as `.p12` → add to GitHub Secret `APPLE_CERT_P12` + passphrase as `APPLE_CERT_PASSWORD` + team ID as `APPLE_TEAM_ID` + notarization App Store Connect API key as `APPLE_NOTARIZE_KEY`
> - **Windows:** OV/EV code signing certificate from DigiCert/Sectigo → export as `.pfx` → add to GitHub Secret `WINDOWS_CERT_PFX` + passphrase as `WINDOWS_CERT_PASSWORD`
>
> These certificates cost money and require identity verification. The CI steps below are no-ops until the secrets are set.

- [ ] **Step 1: Add macOS code signing to `build-mac` job**

In the `build-mac` job, after `Build PDFree.app` and before `Create PDFree.dmg`, add:

```yaml
      - name: Sign and notarize (macOS)
        if: startsWith(github.ref, 'refs/tags/') && env.APPLE_CERT_P12 != ''
        env:
          APPLE_CERT_P12: ${{ secrets.APPLE_CERT_P12 }}
          APPLE_CERT_PASSWORD: ${{ secrets.APPLE_CERT_PASSWORD }}
          APPLE_TEAM_ID: ${{ secrets.APPLE_TEAM_ID }}
          APPLE_NOTARIZE_KEY: ${{ secrets.APPLE_NOTARIZE_KEY }}
        run: |
          # Import certificate into temporary keychain
          echo "$APPLE_CERT_P12" | base64 --decode -o cert.p12
          security create-keychain -p "" build.keychain
          security default-keychain -s build.keychain
          security unlock-keychain -p "" build.keychain
          security import cert.p12 -k build.keychain -P "$APPLE_CERT_PASSWORD" -T /usr/bin/codesign
          security set-key-partition-list -S apple-tool:,apple: -s -k "" build.keychain
          # Sign the app bundle (deep sign with hardened runtime)
          codesign --deep --force --options runtime \
            --sign "Developer ID Application: $APPLE_TEAM_ID" \
            dist/PDFree.app
          # Notarize
          xcrun notarytool submit dist/PDFree.app \
            --key-id "$APPLE_NOTARIZE_KEY" \
            --issuer "$APPLE_TEAM_ID" \
            --wait
          xcrun stapler staple dist/PDFree.app
```

- [ ] **Step 2: Add Windows code signing to `build-windows` job**

In `build-windows`, after `Build PDFree.exe` and before `Build installer with Inno Setup`, add:

```yaml
      - name: Sign executable (Windows)
        if: startsWith(github.ref, 'refs/tags/') && env.WINDOWS_CERT_PFX != ''
        env:
          WINDOWS_CERT_PFX: ${{ secrets.WINDOWS_CERT_PFX }}
          WINDOWS_CERT_PASSWORD: ${{ secrets.WINDOWS_CERT_PASSWORD }}
        shell: powershell
        run: |
          $certBytes = [Convert]::FromBase64String($env:WINDOWS_CERT_PFX)
          [IO.File]::WriteAllBytes("cert.pfx", $certBytes)
          & "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe" sign `
            /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com `
            /f cert.pfx /p $env:WINDOWS_CERT_PASSWORD `
            dist\PDFree\_internal\PDFree.exe
          Remove-Item cert.pfx
```

- [ ] **Step 3: Update the release body to remove SmartScreen / Gatekeeper workaround notes**

Once signing is active, update the `body:` block in the `release` job to remove the "right-click → Open" and "More info → Run anyway" instructions.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: add code signing scaffolding for macOS and Windows (certs required)"
```

---

## Task 7: `.env.example`

**Files:**
- Create: `.env.example`

- [ ] **Step 1: Create the file**

```
# PDFree environment variables
# Copy this file to .env and adjust values for your setup.
# PDFree does not require any of these to be set — defaults are shown.

# Directory where PDFree stores library.json, logs, and theme.json.
# Default: ~/.pdfree
# PDFREE_STATE_DIR=~/.pdfree
```

- [ ] **Step 2: Verify .env is in .gitignore**

```
grep -n "\.env" .gitignore
```
Expected: a line matching `.env` or `.env*`. If not present, add `.env` to `.gitignore`.

- [ ] **Step 3: Commit**

```bash
git add .env.example .gitignore
git commit -m "chore: add .env.example with PDFREE_STATE_DIR documentation"
```
