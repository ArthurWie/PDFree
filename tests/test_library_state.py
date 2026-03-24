"""Tests for LibraryState and pure helpers in library_page."""

from datetime import datetime, timedelta, timezone

import pytest


# ---------------------------------------------------------------------------
# Helpers (no Qt required)
# ---------------------------------------------------------------------------


def test_fmt_size_bytes():
    from library_page import _fmt_size

    assert _fmt_size(0) == "0 B"
    assert _fmt_size(512) == "512 B"
    assert _fmt_size(1023) == "1023 B"


def test_fmt_size_kb():
    from library_page import _fmt_size

    assert _fmt_size(1024) == "1.0 KB"
    assert _fmt_size(2048) == "2.0 KB"
    assert _fmt_size(1536) == "1.5 KB"


def test_fmt_size_mb():
    from library_page import _fmt_size

    assert _fmt_size(1024**2) == "1.0 MB"
    assert _fmt_size(1024**2 * 2) == "2.0 MB"


def test_age_str_just_now():
    from library_page import _age_str

    iso = datetime.now(timezone.utc).isoformat()
    assert _age_str(iso) == "just now"


def test_age_str_minutes():
    from library_page import _age_str

    dt = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert _age_str(dt.isoformat()) == "5m ago"


def test_age_str_hours():
    from library_page import _age_str

    dt = datetime.now(timezone.utc) - timedelta(hours=3)
    assert _age_str(dt.isoformat()) == "3h ago"


def test_age_str_days():
    from library_page import _age_str

    dt = datetime.now(timezone.utc) - timedelta(days=7)
    assert _age_str(dt.isoformat()) == "7d ago"


def test_age_str_invalid():
    from library_page import _age_str

    assert _age_str("not-a-date") == ""
    assert _age_str("") == ""


def test_file_size_missing():
    from library_page import _file_size

    assert _file_size("/nonexistent/path/file.pdf") == 0


def test_file_size_real(tmp_path):
    from library_page import _file_size

    f = tmp_path / "test.txt"
    f.write_bytes(b"hello")
    assert _file_size(str(f)) == 5


# ---------------------------------------------------------------------------
# LibraryState — uses a temp dir via PDFREE_STATE_DIR
# ---------------------------------------------------------------------------


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("PDFREE_STATE_DIR", str(tmp_path))
    import library_page

    monkeypatch.setattr(
        library_page,
        "_STATE_PATH",
        tmp_path / "library.json",
    )
    from library_page import LibraryState

    return LibraryState()


def test_state_starts_empty(state):
    assert state.data["files"] == []
    assert state.data["folders"] == []


def test_track_adds_file(state, tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"")
    state.track(str(f))
    assert len(state.data["files"]) == 1
    assert state.data["files"][0]["name"] == "a.pdf"
    assert not state.data["files"][0]["trashed"]
    assert not state.data["files"][0]["favorited"]


def test_track_updates_existing(state, tmp_path):
    f = tmp_path / "b.pdf"
    f.write_bytes(b"")
    state.track(str(f))
    state.track(str(f))
    assert len(state.data["files"]) == 1


def test_favorite(state, tmp_path):
    f = tmp_path / "c.pdf"
    f.write_bytes(b"")
    state.track(str(f))
    path = str(f.resolve())
    state.set_favorite(path, True)
    assert state.data["files"][0]["favorited"]
    state.set_favorite(path, False)
    assert not state.data["files"][0]["favorited"]


def test_trash_and_restore(state, tmp_path):
    f = tmp_path / "d.pdf"
    f.write_bytes(b"")
    state.track(str(f))
    path = str(f.resolve())
    state.trash(path)
    assert state.data["files"][0]["trashed"]
    # restore
    for e in state.data["files"]:
        if e["path"] == path:
            e["trashed"] = False
    assert not state.data["files"][0]["trashed"]


def test_state_persists(tmp_path, monkeypatch):
    import library_page

    state_path = tmp_path / "library.json"
    monkeypatch.setattr(library_page, "_STATE_PATH", state_path)
    from library_page import LibraryState

    f = tmp_path / "e.pdf"
    f.write_bytes(b"")
    s1 = LibraryState()
    s1.track(str(f))

    s2 = LibraryState()
    assert len(s2.data["files"]) == 1
    assert s2.data["files"][0]["name"] == "e.pdf"


def test_state_path_env_var(tmp_path, monkeypatch):
    custom_dir = tmp_path / "custom_state"
    monkeypatch.setenv("PDFREE_STATE_DIR", str(custom_dir))
    import importlib
    import library_page

    importlib.reload(library_page)
    assert str(custom_dir) in str(library_page._STATE_PATH)


def test_get_last_page_unknown_path(state):
    assert state.get_last_page("/does/not/exist.pdf") == 0


def test_get_last_page_absent_field(state, tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"%PDF-1.4")
    state.track(str(p))
    # Entry exists but no last_page field yet
    assert state.get_last_page(str(p)) == 0


def test_set_last_page_updates(state, tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"%PDF-1.4")
    state.track(str(p))
    state.set_last_page(str(p), 5)
    assert state.get_last_page(str(p)) == 5


def test_set_last_page_unknown_is_noop(state):
    # Must not raise and must not create an entry
    state.set_last_page("/does/not/exist.pdf", 3)
    assert state.get_last_page("/does/not/exist.pdf") == 0


def test_set_last_page_trashed_is_noop(state, tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"%PDF-1.4")
    state.track(str(p))
    state.trash(str(p))
    state.set_last_page(str(p), 7)
    # Assert immediately — while still trashed — that the write was skipped
    assert state.get_last_page(str(p)) == 0
    # Also verify after restore that the field was never set
    state.restore(str(p))
    assert state.get_last_page(str(p)) == 0
