# Sprint 3 — Test Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add unit tests for the 28+ tools that currently have none. Each test hits the worker's `run()` method directly with a real PDF from `tests/corpus/` and asserts the operation produced the expected output.

**Architecture:** One test file per tool (or one per logical group where tools share the same worker). Every test creates a temp copy of a corpus fixture, runs the worker `.run()` synchronously (by calling it directly, not via Qt signals), and asserts output correctness. Tests never mock fitz — they use the real library on real PDFs.

**Tech Stack:** Python 3.11, pytest, PyMuPDF (fitz), pypdf, Pillow. No Qt event loop needed for worker-only tests.

---

## Corpus fixtures available in `tests/corpus/`

| Fixture | Description |
|---------|-------------|
| `plain.pdf` | Single-page, text only |
| `multipage.pdf` | Multiple pages, text |
| `password.pdf` | AES-256 encrypted, password: `test` |
| `form.pdf` | AcroForm with text/checkbox fields |
| `annotated.pdf` | Has highlight/text annotations |
| `corrupt.pdf` | Intentionally malformed |

---

## The standard worker test pattern

Every test below follows this shape:

```python
import shutil
from pathlib import Path
import pytest

CORPUS = Path(__file__).parent / "corpus"


def _copy(fixture: str, tmp_path: Path) -> Path:
    src = CORPUS / fixture
    dst = tmp_path / fixture
    shutil.copy2(src, dst)
    return dst


def test_worker_produces_valid_pdf(tmp_path):
    import fitz
    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out.pdf"

    worker = _SomeWorker(str(src), str(out), ...args...)
    worker.run()

    assert out.exists(), "output file was not created"
    doc = fitz.open(str(out))
    assert doc.page_count > 0
    doc.close()
```

Variations:
- For split: assert multiple output files exist
- For compress: assert output size <= input size (for lossless) or output is valid PDF
- For rotate: assert page rotation metadata changed
- For extract_images: assert image files were written

---

## Task 1: `split_tool` tests

**Files:**
- Create: `tests/test_split_tool.py`

- [ ] **Step 1: Write failing tests**

```python
import shutil
from pathlib import Path
import pytest

CORPUS = Path(__file__).parent / "corpus"


def _copy(name, tmp):
    p = tmp / name
    shutil.copy2(CORPUS / name, p)
    return p


def test_split_by_range_produces_output(tmp_path):
    import fitz
    from split_tool import _SplitWorker
    src = _copy("multipage.pdf", tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    doc = fitz.open(str(src))
    total = doc.page_count
    doc.close()

    # Actual signature: _SplitWorker(mode, pdf_path, **kwargs)
    # out_dir and ranges are passed as keyword arguments
    worker = _SplitWorker("range", str(src), out_dir=str(out_dir), ranges=[(0, total - 1)])
    worker.run()

    files = list(out_dir.glob("*.pdf"))
    assert len(files) >= 1
    for f in files:
        d = fitz.open(str(f))
        assert d.page_count > 0
        d.close()


def test_split_half_produces_two_files(tmp_path):
    import fitz
    from split_tool import _SplitWorker
    src = _copy("multipage.pdf", tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # Actual signature: _SplitWorker(mode, pdf_path, **kwargs)
    worker = _SplitWorker("half", str(src), out_dir=str(out_dir))
    worker.run()

    files = sorted(out_dir.glob("*.pdf"))
    assert len(files) == 2
    for f in files:
        d = fitz.open(str(f))
        assert d.page_count >= 1
        d.close()
```

- [ ] **Step 2: Run to verify they fail, then implement**

```
pytest tests/test_split_tool.py -v
```
If the worker signature does not match, read `split_tool.py` to find the exact `__init__` parameters and adjust the test arguments accordingly.

- [ ] **Step 3: Run to verify they pass**

```
pytest tests/test_split_tool.py -v
```
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_split_tool.py
git commit -m "test: add split_tool worker tests"
```

---

## Task 2: `merge_tool` tests

**Files:**
- Create: `tests/test_merge_tool.py`

- [ ] **Step 1: Write failing tests**

```python
import shutil
from pathlib import Path
import fitz
import pytest
from merge_tool import _MergeWorker

CORPUS = Path(__file__).parent / "corpus"


def test_merge_two_pdfs(tmp_path):
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    shutil.copy2(CORPUS / "plain.pdf", a)
    shutil.copy2(CORPUS / "plain.pdf", b)
    out = tmp_path / "merged.pdf"

    doc_a = fitz.open(str(a))
    pages_a = doc_a.page_count
    doc_a.close()

    # entries is a list of dicts with at minimum a "path" key
    entries = [{"path": str(a)}, {"path": str(b)}]
    worker = _MergeWorker(entries, str(out))
    worker.run()

    assert out.exists()
    merged = fitz.open(str(out))
    assert merged.page_count == pages_a * 2
    merged.close()


def test_merge_single_file(tmp_path):
    src = tmp_path / "only.pdf"
    shutil.copy2(CORPUS / "multipage.pdf", src)
    out = tmp_path / "out.pdf"

    worker = _MergeWorker([{"path": str(src)}], str(out))
    worker.run()

    assert out.exists()
    doc = fitz.open(str(out))
    assert doc.page_count >= 1
    doc.close()
```

- [ ] **Step 2: Adjust worker signature if needed, run, verify pass**

```
pytest tests/test_merge_tool.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_merge_tool.py
git commit -m "test: add merge_tool worker tests"
```

---

## Task 3: `compress_tool` tests

**Files:**
- Create: `tests/test_compress_tool.py`

- [ ] **Step 1: Write failing tests**

```python
import shutil
from pathlib import Path
import fitz
import pytest

CORPUS = Path(__file__).parent / "corpus"


def test_compress_lossless_produces_valid_pdf(tmp_path):
    # _CompressWorker(pdf_path, out_path, preset: dict) — no standalone _run_compress
    from compress_tool import _CompressWorker, PRESETS
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    shutil.copy2(CORPUS / "multipage.pdf", src)

    lossless_preset = next(p for p in PRESETS if p["dpi"] is None)
    worker = _CompressWorker(str(src), str(dst), lossless_preset)
    worker.run()

    assert dst.exists()
    doc = fitz.open(str(dst))
    assert doc.page_count >= 1
    doc.close()


def test_compress_screen_preset_produces_valid_pdf(tmp_path):
    from compress_tool import _CompressWorker, PRESETS
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    shutil.copy2(CORPUS / "plain.pdf", src)

    screen_preset = next(p for p in PRESETS if p.get("dpi") == 72)
    worker = _CompressWorker(str(src), str(dst), screen_preset)
    worker.run()

    assert dst.exists()
    doc = fitz.open(str(dst))
    assert doc.page_count >= 1
    doc.close()
```

- [ ] **Step 2: Run and verify pass**

```
pytest tests/test_compress_tool.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_compress_tool.py
git commit -m "test: add compress_tool worker tests"
```

---

## Task 4: `rotate_tool` tests

**Files:**
- Create: `tests/test_rotate_tool.py`

- [ ] **Step 1: Write failing tests**

```python
import shutil
from pathlib import Path
from pypdf import PdfReader
import pytest

CORPUS = Path(__file__).parent / "corpus"


def test_rotate_all_pages_90(tmp_path):
    from rotate_tool import _RotateWorker
    import fitz
    src = tmp_path / "in.pdf"
    out = tmp_path / "out.pdf"
    shutil.copy2(CORPUS / "multipage.pdf", src)

    doc = fitz.open(str(src))
    total = doc.page_count
    doc.close()

    rotations = {i: 90 for i in range(total)}
    worker = _RotateWorker(str(src), str(out), rotations, total)
    worker.run()

    assert out.exists()
    reader = PdfReader(str(out))
    for page in reader.pages:
        rotation = page.get("/Rotate", 0)
        assert rotation % 90 == 0
```

- [ ] **Step 2: Run and verify pass**

```
pytest tests/test_rotate_tool.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_rotate_tool.py
git commit -m "test: add rotate_tool worker tests"
```

---

## Task 5: `crop_tool` tests

**Files:**
- Create: `tests/test_crop_tool.py`

- [ ] **Step 1: Write failing tests**

```python
import shutil, fitz
from pathlib import Path
import pytest

CORPUS = Path(__file__).parent / "corpus"


def test_crop_reduces_page_rect(tmp_path):
    # _CropWorker(pdf_path, out_path, apply_all, current_page, page_w, page_h, x0, y0, x1, y1)
    from crop_tool import _CropWorker
    src = tmp_path / "in.pdf"
    out = tmp_path / "out.pdf"
    shutil.copy2(CORPUS / "plain.pdf", src)

    doc = fitz.open(str(src))
    r = doc.load_page(0).rect
    doc.close()

    margin = 10.0
    worker = _CropWorker(
        str(src), str(out),
        apply_all=True, current_page=0,
        page_w=r.width, page_h=r.height,
        x0=margin, y0=margin,
        x1=r.width - margin, y1=r.height - margin,
    )
    worker.run()

    assert out.exists()
    doc = fitz.open(str(out))
    new_rect = doc.load_page(0).rect
    doc.close()
    assert new_rect.width < r.width
    assert new_rect.height < r.height
```

- [ ] **Step 2: Adjust worker signature if needed, run, verify pass**

```
pytest tests/test_crop_tool.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_crop_tool.py
git commit -m "test: add crop_tool worker tests"
```

---

## Tasks 6–28: Remaining tool tests

Apply the same pattern for each remaining untested tool. For each:

1. Find the worker class name and `__init__` signature by reading the tool file
2. Write a test that: copies a corpus fixture, calls `worker.run()`, asserts output exists and is a valid PDF (or expected file type)
3. Run `pytest tests/test_<tool>.py -v`, fix signature mismatches
4. Commit with message `test: add <tool_name> worker tests`

**Remaining tools and what to assert:**

| Tool file | Worker class | Test fixture | Assert |
|-----------|-------------|-------------|--------|
| `remove_tool.py` | `_RemovePagesWorker` | `multipage.pdf` | output page count < input page count. Pass a list of page indices to **keep** (e.g. `[0]` keeps only first page). Read `__init__` signature first. |
| `reorder_tool.py` | `_ReorderWorker` | `multipage.pdf` | output page count == input page count |
| `nup_tool.py` | `_NUpWorker` | `multipage.pdf` | output page count < input page count |
| `scale_pages_tool.py` | `_ScalePagesWorker` | `plain.pdf` | output page rect matches target size |
| `excerpt_tool.py` | (no QThread worker — inline save) | `plain.pdf` | read file to find save call site; test the save function directly |
| `compare_tool.py` | `_ExportDiffWorker` | `plain.pdf` + `plain.pdf` | output (image or HTML) exists |
| `extract_images_tool.py` | `_ExtractImagesWorker` | `plain.pdf` | output dir exists (even if no images in plain.pdf) |
| `flatten_tool.py` | `_FlattenWorker` | `annotated.pdf` | output is valid PDF, no annotations |
| `headers_footers_tool.py` | `_HeadersFootersWorker` | `plain.pdf` | output is valid PDF |
| `remove_annotations_tool.py` | `_RemoveAnnotationsWorker` | `annotated.pdf` | output has 0 annotations |
| `change_metadata_tool.py` | `_SaveMetaWorker` | `plain.pdf` | output metadata matches input values |
| `add_image_tool.py` | `_AddImageWorker` | `plain.pdf` | output is valid PDF |
| `add_page_numbers_tool.py` | `_AddPageNumbersWorker` | `multipage.pdf` | output is valid PDF, same page count |
| `add_password_tool.py` | `_AddPasswordWorker` | `plain.pdf` | output requires password to open |
| `remove_password_tool.py` | `_RemovePasswordWorker` | `password.pdf` (pw=`test`) | output opens without password |
| `sanitize_tool.py` | `_SanitizeWorker` | `plain.pdf` | output is valid PDF |
| `img_to_pdf_tool.py` | `_BuildWorker` | PNG image (create in tmp_path) | output is valid PDF |
| `pdf_to_word_tool.py` | `_ConvertWorker` | `plain.pdf` | output `.docx` exists |
| `pdf_to_img_tool.py` | `_ExportWorker` | `plain.pdf` | PNG file(s) written to output dir |
| `pdf_to_excel_tool.py` | `_ExportWorker` | `plain.pdf` | `.xlsx` file exists |
| `html_to_pdf_tool.py` | `_ConvertWorker` | HTML string (write to tmp file) | output PDF exists OR fails gracefully with no external tool |
| `office_to_pdf_tool.py` | `_ConvertWorker` | skip if no LibreOffice; mark with `pytest.mark.skipif` | output PDF exists |
| `ocr_tool.py` | `_OcrWorker` | skip if no ocrmypdf installed; mark with `pytest.mark.skipif` | output PDF exists |
| `watermark_tool.py` | `_WatermarkWorker` | `plain.pdf` | output is valid PDF |

For `img_to_pdf_tool.py`, create a small test PNG:
```python
from PIL import Image
img = Image.new("RGB", (100, 100), color=(255, 0, 0))
img_path = tmp_path / "test.png"
img.save(str(img_path))
```

For `html_to_pdf_tool.py` and `office_to_pdf_tool.py`, wrap with:
```python
pytest.importorskip("weasyprint")  # or check for external converter
```

For `ocr_tool.py`:
```python
pytestmark = pytest.mark.skipif(
    shutil.which("ocrmypdf") is None,
    reason="ocrmypdf not installed"
)
```

- [ ] **Step 1: Implement `tests/test_remove_tool.py`** — run, verify pass, commit
- [ ] **Step 2: Implement `tests/test_reorder_tool.py`** — run, verify pass, commit
- [ ] **Step 3: Implement `tests/test_nup_tool.py`** — run, verify pass, commit
- [ ] **Step 4: Implement `tests/test_scale_pages_tool.py`** — run, verify pass, commit
- [ ] **Step 5: Implement `tests/test_excerpt_tool.py`** — run, verify pass, commit
- [ ] **Step 6: Implement `tests/test_compare_tool.py`** — run, verify pass, commit
- [ ] **Step 7: Implement `tests/test_extract_images_tool.py`** — run, verify pass, commit
- [ ] **Step 8: Implement `tests/test_flatten_tool.py`** — run, verify pass, commit
- [ ] **Step 9: Implement `tests/test_headers_footers_tool.py`** — run, verify pass, commit
- [ ] **Step 10: Implement `tests/test_remove_annotations_tool.py`** — run, verify pass, commit
- [ ] **Step 11: Implement `tests/test_change_metadata_tool.py`** — run, verify pass, commit
- [ ] **Step 12: Implement `tests/test_add_image_tool.py`** — run, verify pass, commit
- [ ] **Step 13: Implement `tests/test_add_page_numbers_tool.py`** — run, verify pass, commit
- [ ] **Step 14: Implement `tests/test_add_password_tool.py`** — run, verify pass, commit
- [ ] **Step 15: Implement `tests/test_remove_password_tool.py`** — run, verify pass, commit
- [ ] **Step 16: Implement `tests/test_sanitize_tool.py`** — run, verify pass, commit
- [ ] **Step 17: Implement `tests/test_img_to_pdf_tool.py`** — run, verify pass, commit
- [ ] **Step 18: Implement `tests/test_pdf_to_word_tool.py`** — run, verify pass, commit
- [ ] **Step 19: Implement `tests/test_pdf_to_img_tool.py`** — run, verify pass, commit
- [ ] **Step 20: Implement `tests/test_pdf_to_excel_tool.py`** — run, verify pass, commit
- [ ] **Step 21: Implement `tests/test_html_to_pdf_tool.py`** — run, verify pass, commit
- [ ] **Step 22: Implement `tests/test_office_to_pdf_tool.py`** — run, verify pass, commit
- [ ] **Step 23: Implement `tests/test_ocr_tool.py`** — run, verify pass, commit
- [ ] **Step 24: Implement `tests/test_watermark_tool.py`** — run, verify pass, commit

- [ ] **Final step: Run the full suite**

```
pytest --tb=short -q
```
Expected: all previous tests still pass; 24+ new test files added
