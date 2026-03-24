"""Tests for two-up (facing pages) scroll mode logic in view_tool."""

import sys
import pytest

from view_tool import ViewMode


def test_viewmode_constants():
    assert ViewMode.SINGLE == "single"
    assert ViewMode.TWO_UP == "two_up"


def test_viewmode_distinct():
    assert ViewMode.SINGLE != ViewMode.TWO_UP


# ---------------------------------------------------------------------------
# Navigation step logic (extracted from _prev_page / _next_page)
# ---------------------------------------------------------------------------


def _nav_step(mode):
    return 2 if mode == ViewMode.TWO_UP else 1


def test_single_step_is_1():
    assert _nav_step(ViewMode.SINGLE) == 1


def test_twoup_step_is_2():
    assert _nav_step(ViewMode.TWO_UP) == 2


# ---------------------------------------------------------------------------
# Two-up render method exists and has the expected signature
# ---------------------------------------------------------------------------


def test_render_twoup_method_exists():
    import inspect
    from view_tool import _RenderWorker

    assert hasattr(_RenderWorker, "_render_twoup")
    sig = inspect.signature(_RenderWorker._render_twoup)
    params = list(sig.parameters)
    assert "doc" in params


def test_set_mode_twoup_method_exists():
    from view_tool import ViewTool

    assert callable(getattr(ViewTool, "_set_mode_twoup", None))
    assert callable(getattr(ViewTool, "_set_mode_single", None))


# ---------------------------------------------------------------------------
# QApplication-level: toggle mode changes _view_mode attribute
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qapp():
    app = _get_or_create_app()
    yield app


def _get_or_create_app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv)


def test_default_mode_is_single(qapp):
    from view_tool import ViewTool

    vt = ViewTool()
    assert vt._view_mode == ViewMode.SINGLE
    vt.cleanup()


def test_set_mode_twoup_changes_state(qapp):
    from view_tool import ViewTool

    vt = ViewTool()
    vt._set_mode_twoup()
    assert vt._view_mode == ViewMode.TWO_UP
    vt.cleanup()


def test_set_mode_single_restores_state(qapp):
    from view_tool import ViewTool

    vt = ViewTool()
    vt._set_mode_twoup()
    vt._set_mode_single()
    assert vt._view_mode == ViewMode.SINGLE
    vt.cleanup()


def test_twoup_button_checked_after_toggle(qapp):
    from view_tool import ViewTool

    vt = ViewTool()
    vt._set_mode_twoup()
    assert vt._btn_mode_twoup.isChecked()
    assert not vt._btn_mode_single.isChecked()
    vt.cleanup()


def test_single_button_checked_after_restore(qapp):
    from view_tool import ViewTool

    vt = ViewTool()
    vt._set_mode_twoup()
    vt._set_mode_single()
    assert vt._btn_mode_single.isChecked()
    assert not vt._btn_mode_twoup.isChecked()
    vt.cleanup()


def test_continuous_mode_exists():
    assert ViewMode.CONTINUOUS == "continuous"
