"""Tests for _RenderPane public interface."""

import sys
import pytest


def _get_or_create_app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="module")
def qapp():
    return _get_or_create_app()


def test_render_pane_class_exists():
    from view_tool import _RenderPane  # noqa: F401


def test_render_pane_interface(qapp):
    from view_tool import ViewTool

    vt = ViewTool()
    pane = vt.active_pane
    assert pane is not None
    # State properties
    assert hasattr(pane, "active_page")
    assert hasattr(pane, "page_count")
    assert hasattr(pane, "is_modified")
    assert hasattr(pane, "can_undo")
    assert hasattr(pane, "can_redo")
    assert hasattr(pane, "path")
    # Methods
    assert callable(getattr(pane, "cleanup", None))
    assert callable(getattr(pane, "undo", None))
    assert callable(getattr(pane, "redo", None))
    vt.cleanup()


def test_render_pane_defaults(qapp):
    from view_tool import ViewTool

    vt = ViewTool()
    pane = vt.active_pane
    assert pane.active_page == 0
    assert pane.page_count == 0
    assert pane.is_modified is False
    assert pane.can_undo is False
    assert pane.can_redo is False
    assert pane.path == ""
    vt.cleanup()


def test_viewtool_modified_delegates_to_pane(qapp):
    from view_tool import ViewTool

    vt = ViewTool()
    assert vt._modified is False
    vt.active_pane._is_modified = True
    assert vt._modified is True
    vt.cleanup()
