"""Tests for theme.py — apply_theme and is_dark."""

import json
import importlib


def _reset_colors():
    import colors

    importlib.reload(colors)


def test_apply_light_theme_sets_white_white(tmp_path, monkeypatch):
    import theme
    import colors

    monkeypatch.setattr(theme, "_pref_path", lambda: tmp_path / "theme.json")
    theme.apply_theme(dark=False)
    assert colors.WHITE == "#FFFFFF"
    assert colors.G900 == "#111827"
    assert colors.SIDEBAR_BG == "#f0f4f8"


def test_apply_dark_theme_sets_dark_bg(tmp_path, monkeypatch):
    import theme
    import colors

    monkeypatch.setattr(theme, "_pref_path", lambda: tmp_path / "theme.json")
    theme.apply_theme(dark=True)
    assert colors.WHITE == "#1E2130"
    assert colors.G900 == "#F9FAFB"
    assert colors.SIDEBAR_BG == "#171923"
    assert colors.HOME_BORDER == "#2D3748"


def test_apply_light_after_dark_restores(tmp_path, monkeypatch):
    import theme
    import colors

    monkeypatch.setattr(theme, "_pref_path", lambda: tmp_path / "theme.json")
    theme.apply_theme(dark=True)
    theme.apply_theme(dark=False)
    assert colors.WHITE == "#FFFFFF"
    assert colors.G900 == "#111827"


def test_is_dark_defaults_false_when_no_file(tmp_path, monkeypatch):
    import theme

    monkeypatch.setattr(theme, "_pref_path", lambda: tmp_path / "nonexistent.json")
    assert theme.is_dark() is False


def test_is_dark_reads_saved_preference(tmp_path, monkeypatch):
    import theme

    pref = tmp_path / "theme.json"
    pref.write_text(json.dumps({"dark": True}), encoding="utf-8")
    monkeypatch.setattr(theme, "_pref_path", lambda: pref)
    assert theme.is_dark() is True


def test_apply_theme_persists_preference(tmp_path, monkeypatch):
    import theme

    pref = tmp_path / "theme.json"
    monkeypatch.setattr(theme, "_pref_path", lambda: pref)
    theme.apply_theme(dark=True)
    data = json.loads(pref.read_text(encoding="utf-8"))
    assert data["dark"] is True

    theme.apply_theme(dark=False)
    data = json.loads(pref.read_text(encoding="utf-8"))
    assert data["dark"] is False
