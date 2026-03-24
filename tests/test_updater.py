import sys
import pytest
from unittest.mock import patch, MagicMock
import json


FAKE_RELEASE = {
    "tag_name": "v99.0.0",
    "html_url": "https://github.com/owner/repo/releases/tag/v99.0.0",
    "assets": [
        {"name": "PDFree_Setup.exe",        "browser_download_url": "https://example.com/PDFree_Setup.exe"},
        {"name": "PDFree.dmg",              "browser_download_url": "https://example.com/PDFree.dmg"},
        {"name": "PDFree-x86_64.AppImage",  "browser_download_url": "https://example.com/PDFree-x86_64.AppImage"},
    ],
}


def test_pick_asset_windows():
    from updater import _pick_asset_url
    url = _pick_asset_url(FAKE_RELEASE["assets"], "win32")
    assert url == "https://example.com/PDFree_Setup.exe"


def test_pick_asset_macos():
    from updater import _pick_asset_url
    url = _pick_asset_url(FAKE_RELEASE["assets"], "darwin")
    assert url == "https://example.com/PDFree.dmg"


def test_pick_asset_linux():
    from updater import _pick_asset_url
    url = _pick_asset_url(FAKE_RELEASE["assets"], "linux")
    assert url == "https://example.com/PDFree-x86_64.AppImage"


def test_pick_asset_unknown_platform_returns_none():
    from updater import _pick_asset_url
    url = _pick_asset_url(FAKE_RELEASE["assets"], "freebsd")
    assert url is None


def test_update_checker_emits_asset_url(monkeypatch):
    """UpdateChecker must emit the binary download URL when available."""
    from updater import UpdateChecker
    import updater

    monkeypatch.setattr(updater, "_due_for_check", lambda: True)
    monkeypatch.setattr(updater, "_write_stamp", lambda: None)

    fake_resp = MagicMock()
    fake_resp.read.return_value = json.dumps(FAKE_RELEASE).encode()
    fake_resp.__enter__ = lambda s: s
    fake_resp.__exit__ = MagicMock(return_value=False)

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: fake_resp)

    import sys
    monkeypatch.setattr(sys, "platform", "win32")

    received = []
    checker = UpdateChecker()
    checker.update_available.connect(lambda tag, url: received.append((tag, url)))
    checker.run()  # call directly (not via QThread.start) for test

    assert len(received) == 1
    tag, url = received[0]
    assert tag == "v99.0.0"
    assert url == "https://example.com/PDFree_Setup.exe"


def test_update_checker_falls_back_to_html_url(monkeypatch):
    """When no asset matches the current platform, emit html_url instead."""
    from updater import UpdateChecker
    import updater

    monkeypatch.setattr(updater, "_due_for_check", lambda: True)
    monkeypatch.setattr(updater, "_write_stamp", lambda: None)

    # Release with no assets
    fake_release = {
        "tag_name": "v99.0.0",
        "html_url": "https://github.com/owner/repo/releases/tag/v99.0.0",
        "assets": [],
    }

    import json
    from unittest.mock import MagicMock
    fake_resp = MagicMock()
    fake_resp.read.return_value = json.dumps(fake_release).encode()
    fake_resp.__enter__ = lambda s: s
    fake_resp.__exit__ = MagicMock(return_value=False)

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: fake_resp)

    import sys
    monkeypatch.setattr(sys, "platform", "win32")

    received = []
    checker = UpdateChecker()
    checker.update_available.connect(lambda tag, url: received.append((tag, url)))
    checker.run()

    assert len(received) == 1
    tag, url = received[0]
    assert tag == "v99.0.0"
    assert url == "https://github.com/owner/repo/releases/tag/v99.0.0"
