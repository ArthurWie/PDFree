"""Shared Qt utilities for PDFree tool modules."""

import os
import re
import shutil
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QSize
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QPushButton, QScrollArea

from colors import G100, G700
from icons import svg_icon


def _fitz_pix_to_qpixmap(pix, dpr: float = 1.0) -> QPixmap:
    """Convert a fitz.Pixmap (RGB) to a QPixmap.

    Pass dpr=screen.devicePixelRatio() when the pixmap was rendered at
    physical resolution so Qt displays it at the correct logical size.
    """
    try:
        data = pix.samples_mv
    except AttributeError:
        data = pix.samples
    img = QImage(data, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
    pm = QPixmap.fromImage(img.copy())
    pm.setDevicePixelRatio(dpr)
    return pm


def _make_back_button(text: str, callback, color: str = G700) -> QPushButton:
    """Return a styled back button with an arrow-left icon."""
    btn = QPushButton(f"  {text}")
    btn.setIcon(svg_icon("arrow-left", color, 14))
    btn.setIconSize(QSize(14, 14))
    btn.setFixedHeight(36)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: transparent; color: {color}; border: none;
            border-radius: 6px; font: 13px 'Segoe UI';
            text-align: left; padding: 0 8px;
        }}
        QPushButton:hover {{ background: {G100}; }}
    """)
    btn.clicked.connect(callback)
    return btn


_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def sanitize_filename(name: str, replacement: str = "_") -> str:
    name = _UNSAFE.sub(replacement, name).strip(". ")
    if not name:
        return "file"
    stem = name.rsplit(".", 1)[0].upper()
    if stem in _RESERVED:
        name = replacement + name
    return name[:255]


def backup_original(src: Path) -> Path:
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(src)
    bak = src.with_suffix(src.suffix + ".bak")
    shutil.copy2(src, bak)
    return bak


def assert_file_writable(path: Path) -> None:
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


class _WheelToHScroll(QObject):
    """Route vertical wheel events to horizontal scroll on a QScrollArea."""

    def __init__(self, sa: QScrollArea):
        super().__init__(sa)
        self._sa = sa
        sa.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        try:
            viewport = self._sa.viewport()
        except RuntimeError:
            return super().eventFilter(obj, event)
        if obj is viewport and event.type() == QEvent.Type.Wheel:
            delta = event.angleDelta().y()
            sb = self._sa.horizontalScrollBar()
            sb.setValue(sb.value() - delta // 4)
            return True
        return super().eventFilter(obj, event)
