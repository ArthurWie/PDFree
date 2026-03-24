"""Background update checker.

Fetches the latest release from GitHub Releases API and emits
update_available(tag, url) when a newer version is found.
The check is throttled to once every 24 hours using a timestamp
file stored next to the application log.
"""

import json
import logging
import sys as _sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from logging_config import _log_dir
from version import APP_VERSION, GITHUB_REPO

logger = logging.getLogger(__name__)

_CHECK_INTERVAL = timedelta(hours=24)
_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_STAMP_FILE = "last_update_check.txt"

_ASSET_PATTERNS = {
    "win32": "_Setup.exe",
    "darwin": ".dmg",
    "linux": ".AppImage",
}


def _pick_asset_url(assets: list, platform: str = _sys.platform) -> str | None:
    suffix = _ASSET_PATTERNS.get(platform)
    if not suffix:
        return None
    for asset in assets:
        if asset.get("name", "").endswith(suffix):
            return asset.get("browser_download_url")
    return None


def _parse_version(tag: str) -> tuple[int, ...]:
    """Convert 'v1.2.3' or '1.2.3' to (1, 2, 3)."""
    tag = tag.lstrip("v")
    try:
        return tuple(int(p) for p in tag.split("."))
    except ValueError:
        return (0,)


def _is_newer(remote_tag: str, local: str = APP_VERSION) -> bool:
    return _parse_version(remote_tag) > _parse_version(local)


def _stamp_path() -> Path:
    return _log_dir() / _STAMP_FILE


def _last_checked() -> datetime | None:
    p = _stamp_path()
    try:
        text = p.read_text(encoding="utf-8").strip()
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _write_stamp() -> None:
    try:
        _stamp_path().write_text(
            datetime.now(timezone.utc).isoformat(), encoding="utf-8"
        )
    except Exception:
        pass


def _due_for_check() -> bool:
    last = _last_checked()
    if last is None:
        return True
    return datetime.now(timezone.utc) - last >= _CHECK_INTERVAL


class UpdateChecker(QThread):
    """Fetch latest GitHub release in the background.

    Signals:
        update_available(tag, html_url)  — emitted when a newer release exists.
    """

    update_available = Signal(str, str)

    def run(self) -> None:
        if not _due_for_check():
            return
        _write_stamp()
        try:
            req = urllib.request.Request(
                _API_URL,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "PDFree",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310 — URL is a hardcoded https:// constant, never user-supplied
                data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "")
            html_url = data.get(
                "html_url", f"https://github.com/{GITHUB_REPO}/releases"
            )
            assets = data.get("assets") or []
            download_url = _pick_asset_url(assets) or html_url
            if tag and _is_newer(tag):
                self.update_available.emit(tag, download_url)
        except urllib.error.URLError:
            pass  # offline or network error — silently skip
        except Exception:
            logger.exception("update check failed")
