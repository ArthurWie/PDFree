"""Logging setup for PDFree.

Call setup_logging() once at application startup before importing tool modules.
Log file location:
  Windows : %APPDATA%\\PDFree\\pdfree.log
  macOS   : ~/Library/Logs/PDFree/pdfree.log
  Linux   : ~/.local/share/PDFree/pdfree.log
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path


def _log_dir() -> Path:
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Logs"
    else:
        base = Path.home() / ".local" / "share"
    d = base / "PDFree"
    d.mkdir(parents=True, exist_ok=True)
    return d


def setup_logging(level: int = logging.DEBUG) -> None:
    log_path = _log_dir() / "pdfree.log"
    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(handler)
