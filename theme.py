"""Dark / light theme definitions for PDFree.

Call apply_theme(dark=True/False) once at startup (after reading the saved
preference) and again whenever the user toggles the theme.  The function
mutates the module-level constants in colors.py so that all subsequent
widget construction uses the new palette automatically.

Widgets already built are not retroactively re-styled; the home screen
rebuilds itself on toggle, and tools are opened fresh each time.
"""

import json
import logging

import colors

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Theme colour maps
# ---------------------------------------------------------------------------

_LIGHT: dict[str, str] = {
    "BG": "#EEF2F7",
    "WHITE": "#FFFFFF",
    "G50": "#F9FAFB",
    "G100": "#F3F4F6",
    "G200": "#E5E7EB",
    "G300": "#D1D5DB",
    "G400": "#9CA3AF",
    "G500": "#6B7280",
    "G600": "#4B5563",
    "G700": "#374151",
    "G800": "#1F2937",
    "G900": "#111827",
    "SIDEBAR_BG": "#f0f4f8",
    "HOME_BORDER": "#e2e8f0",
    "HOME_SEARCH_BG": "#f8fafc",
    "HOME_SEARCH_TXT": "#6b7280",
    "HOME_TEXT": "#1a202c",
    "THUMB_BG": "#F0F2F5",
    "SCROLLBAR_HANDLE": "#C4CCD8",
    "SOON_TXT": "#B0B8C4",
    "QS_BG": "#E8F1FB",
    "BLUE_DIM": "#EFF6FF",
    "BLUE_MED": "#DBEAFE",
}

_DARK: dict[str, str] = {
    "BG": "#0F1117",
    "WHITE": "#1E2130",
    "G50": "#1A1D27",
    "G100": "#252836",
    "G200": "#353848",
    "G300": "#454858",
    "G400": "#6B7280",
    "G500": "#9CA3AF",
    "G600": "#C4CBD4",
    "G700": "#D1D5DB",
    "G800": "#E5E7EB",
    "G900": "#F9FAFB",
    "SIDEBAR_BG": "#171923",
    "HOME_BORDER": "#2D3748",
    "HOME_SEARCH_BG": "#1A1D27",
    "HOME_SEARCH_TXT": "#9CA3AF",
    "HOME_TEXT": "#E5E7EB",
    "THUMB_BG": "#252836",
    "SCROLLBAR_HANDLE": "#454858",
    "SOON_TXT": "#4B5563",
    "QS_BG": "#1A2C45",
    "BLUE_DIM": "#1E3A5F",
    "BLUE_MED": "#1E3A5F",
    "BRAND": "#6B8FAD",
    "BRAND_HOVER": "#5A7A96",
    "RED_DIM": "#3B1212",
    "RED_MED": "#5B1A1A",
    "AMBER_BG": "#3B2A00",
    "BLUE_BORDER": "#3B6FD4",
}


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def _pref_path():
    from logging_config import _log_dir

    return _log_dir() / "theme.json"


def is_dark() -> bool:
    try:
        data = json.loads(_pref_path().read_text(encoding="utf-8"))
        return bool(data.get("dark", False))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_theme(dark: bool) -> None:
    """Mutate colors module constants to the chosen theme and persist."""
    import sys

    theme = _DARK if dark else _LIGHT
    for name, value in theme.items():
        if hasattr(colors, name):
            setattr(colors, name, value)
    # Propagate to any already-imported modules that did `from colors import TOKEN`.
    # Without this, stale local bindings survive after theme switches.
    for mod in list(sys.modules.values()):
        if mod is None or mod is colors:
            continue
        for name, value in theme.items():
            if type(getattr(mod, name, None)) is str:
                try:
                    setattr(mod, name, value)
                except (AttributeError, TypeError):
                    pass
    try:
        _pref_path().write_text(json.dumps({"dark": dark}), encoding="utf-8")
    except Exception:
        logger.exception("could not save theme preference")
