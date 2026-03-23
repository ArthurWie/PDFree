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
