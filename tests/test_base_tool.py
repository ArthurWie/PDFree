import pytest
from base_tool import BaseTool


def test_base_tool_is_abstract():
    """Cannot instantiate BaseTool directly."""
    with pytest.raises(TypeError):
        BaseTool()


def test_concrete_tool_must_implement_cleanup():
    """A subclass that omits cleanup() raises TypeError on instantiation."""
    class BadTool(BaseTool):
        @property
        def _modified(self):
            return False

    with pytest.raises(TypeError):
        BadTool()


def test_concrete_tool_with_cleanup_can_be_created(qtbot):
    """A properly implemented subclass can be instantiated."""
    from PySide6.QtWidgets import QWidget

    class GoodTool(BaseTool):
        def cleanup(self):
            pass

        @property
        def _modified(self):
            return False

    tool = GoodTool()
    qtbot.addWidget(tool)
    assert isinstance(tool, QWidget)
