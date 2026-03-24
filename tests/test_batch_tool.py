"""Tests for batch_tool pure operation functions."""

from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")


def _make_pdf(path: str, pages: int = 2) -> None:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), f"Page {i + 1}")
    doc.save(path)
    doc.close()


# ---------------------------------------------------------------------------
# _fmt_size
# ---------------------------------------------------------------------------


def test_fmt_size_bytes():
    from batch_tool import _fmt_size

    assert _fmt_size(500) == "500 B"


def test_fmt_size_kb():
    from batch_tool import _fmt_size

    assert _fmt_size(2048) == "2.0 KB"


def test_fmt_size_mb():
    from batch_tool import _fmt_size

    assert _fmt_size(1024**2) == "1.00 MB"


# ---------------------------------------------------------------------------
# _run_compress
# ---------------------------------------------------------------------------


def test_run_compress_lossless(tmp_path):
    from batch_tool import _run_compress

    src = str(tmp_path / "src.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src)
    _run_compress(src, dst, preset_idx=0)
    assert Path(dst).exists()
    doc = fitz.open(dst)
    assert doc.page_count == 2
    doc.close()


def test_run_compress_lossy_screen(tmp_path):
    from batch_tool import _run_compress

    src = str(tmp_path / "src.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src)
    _run_compress(src, dst, preset_idx=3)  # screen 72 DPI
    assert Path(dst).exists()
    doc = fitz.open(dst)
    assert doc.page_count == 2
    doc.close()


# ---------------------------------------------------------------------------
# _run_rotate
# ---------------------------------------------------------------------------


def test_run_rotate_90cw(tmp_path):
    from batch_tool import _run_rotate

    src = str(tmp_path / "src.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src)
    _run_rotate(src, dst, degrees=90)
    assert Path(dst).exists()
    doc = fitz.open(dst)
    assert doc.page_count == 2
    doc.close()


def test_run_rotate_180(tmp_path):
    from batch_tool import _run_rotate

    src = str(tmp_path / "src.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src)
    _run_rotate(src, dst, degrees=180)
    assert Path(dst).exists()


# ---------------------------------------------------------------------------
# _run_add_page_numbers
# ---------------------------------------------------------------------------


def test_run_add_page_numbers_default(tmp_path):
    from batch_tool import _run_add_page_numbers

    src = str(tmp_path / "src.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src, pages=3)
    _run_add_page_numbers(src, dst, pos_idx=0, fmt_idx=0, start=1)
    assert Path(dst).exists()
    doc = fitz.open(dst)
    assert doc.page_count == 3
    doc.close()


def test_run_add_page_numbers_format_page_of_n(tmp_path):
    from batch_tool import _run_add_page_numbers

    src = str(tmp_path / "src.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src, pages=2)
    _run_add_page_numbers(src, dst, pos_idx=0, fmt_idx=3, start=1)
    assert Path(dst).exists()


# ---------------------------------------------------------------------------
# _run_add_password / _run_remove_password
# ---------------------------------------------------------------------------


def test_run_add_password_aes256(tmp_path):
    from batch_tool import _run_add_password

    src = str(tmp_path / "src.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src)
    _run_add_password(src, dst, password="secret", enc_idx=0)
    assert Path(dst).exists()
    doc = fitz.open(dst)
    assert doc.needs_pass
    authenticated = doc.authenticate("secret")
    assert authenticated
    doc.close()


def test_run_remove_password(tmp_path):
    from batch_tool import _run_add_password, _run_remove_password

    src = str(tmp_path / "src.pdf")
    pw_pdf = str(tmp_path / "pw.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src)
    _run_add_password(src, pw_pdf, password="mypass", enc_idx=0)
    _run_remove_password(pw_pdf, dst, password="mypass")
    doc = fitz.open(dst)
    assert not doc.needs_pass
    doc.close()


def test_run_remove_password_wrong_password(tmp_path):
    from batch_tool import _run_add_password, _run_remove_password

    src = str(tmp_path / "src.pdf")
    pw_pdf = str(tmp_path / "pw.pdf")
    dst = str(tmp_path / "dst.pdf")
    _make_pdf(src)
    _run_add_password(src, pw_pdf, password="correct", enc_idx=0)
    with pytest.raises(ValueError, match="incorrect password"):
        _run_remove_password(pw_pdf, dst, password="wrong")


# ---------------------------------------------------------------------------
# _BatchWorker integration
# ---------------------------------------------------------------------------


def test_batch_worker_process_compress(tmp_path):
    from batch_tool import _BatchWorker

    src = str(tmp_path / "a.pdf")
    _make_pdf(src)
    out_dir = str(tmp_path / "out")
    Path(out_dir).mkdir()
    dst = str(Path(out_dir) / "a_batch.pdf")

    worker = _BatchWorker(
        tasks=[src],
        op_id="compress",
        settings={"preset_idx": 0},
        out_dir=out_dir,
    )
    worker._process(src, dst)

    assert Path(dst).exists()
    doc = fitz.open(dst)
    assert doc.page_count == 2
    doc.close()


# ---------------------------------------------------------------------------
# BATCH_REGISTRY
# ---------------------------------------------------------------------------


def test_batch_registry_contains_watermark():
    from batch_tool import BATCH_REGISTRY

    assert "watermark" in BATCH_REGISTRY


def test_batch_registry_contains_pdfa():
    from batch_tool import BATCH_REGISTRY

    assert "pdf_to_pdfa" in BATCH_REGISTRY


def test_batch_registry_all_have_run_fn():
    from batch_tool import BATCH_REGISTRY

    for op_id, entry in BATCH_REGISTRY.items():
        assert callable(entry["run"]), f"{op_id} missing callable 'run'"
        assert "label" in entry, f"{op_id} missing 'label'"
