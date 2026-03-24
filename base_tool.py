"""Abstract base class for all PDFree tool panels."""

from PySide6.QtWidgets import QWidget

_REQUIRED = ("cleanup", "_modified")


class BaseTool(QWidget):
    """Base class for all tool panels.

    Subclasses must implement:
        cleanup()   — close fitz documents and release resources
        _modified   — property returning True if unsaved changes exist
    """

    def __init__(self, parent=None):
        missing = [
            name
            for name in _REQUIRED
            if getattr(type(self), name) is getattr(BaseTool, name)
        ]
        if missing:
            raise TypeError(
                f"Can't instantiate class {type(self).__name__} without "
                f"implementations for: {', '.join(missing)}"
            )
        super().__init__(parent)

    def cleanup(self):
        """Release all resources held by this tool."""
        raise NotImplementedError(f"{type(self).__name__} must implement cleanup()")

    @property
    def _modified(self):
        """True if the tool has unsaved changes."""
        raise NotImplementedError(f"{type(self).__name__} must implement _modified")
