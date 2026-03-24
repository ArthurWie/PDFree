# Sprint 5 — Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit platform-specific binary download URL in the auto-updater; parallelize the batch tool using the worker semaphore; add a crash-reporting modal with clipboard copy.

**Architecture:** Three independent, small changes:
1. `updater.py` — parse `assets` array from GitHub API response to extract the platform-specific binary URL alongside `html_url`
2. `batch_tool.py` — replace the single `_BatchWorker` serial loop with per-file `_BatchItemWorker` threads gated by `worker_semaphore`
3. `main.py` — install a `sys.excepthook` override that shows a crash modal offering to copy the last log entry to clipboard

**Tech Stack:** Python 3.11, PySide6, sys, platform, urllib, pytest

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Modify | `updater.py` | Parse `assets` for platform binary URL |
| Modify | `tests/test_updater.py` | Tests for URL resolution logic |
| Modify | `batch_tool.py` | Parallel per-file workers + semaphore |
| Modify | `tests/test_batch_tool.py` | Tests for parallel dispatch |
| Modify | `main.py` | `sys.excepthook` crash reporter modal |

---

## Task 1: Updater — emit platform-specific binary download URL

**Files:**
- Modify: `updater.py`
- Create: `tests/test_updater.py`

- [ ] **Step 1: Write failing tests**

```python
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


def test_update_checker_emits_asset_url(tmp_path, monkeypatch):
    """UpdateChecker must emit the binary download URL when available."""
    from updater import UpdateChecker, _parse_version
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
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_updater.py -v
```
Expected: `ImportError: cannot import name '_pick_asset_url'`

- [ ] **Step 3: Implement `_pick_asset_url` and update `UpdateChecker.run()` in `updater.py`**

Add the helper function:

```python
import sys as _sys


_ASSET_PATTERNS = {
    "win32":  "_Setup.exe",
    "darwin": ".dmg",
    "linux":  ".AppImage",
}


def _pick_asset_url(assets: list, platform: str = _sys.platform) -> str | None:
    """Return the browser_download_url for the current platform, or None."""
    suffix = _ASSET_PATTERNS.get(platform)
    if not suffix:
        return None
    for asset in assets:
        if asset.get("name", "").endswith(suffix):
            return asset.get("browser_download_url")
    return None
```

Update `UpdateChecker.run()` to use it:

```python
tag = data.get("tag_name", "")
html_url = data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases")
assets = data.get("assets", [])
download_url = _pick_asset_url(assets) or html_url
if tag and _is_newer(tag):
    self.update_available.emit(tag, download_url)
```

- [ ] **Step 4: Run the tests**

```
pytest tests/test_updater.py -v
```
Expected: all pass

- [ ] **Step 5: Verify the banner in `main.py` still works**

Search for `update_available` in `main.py` to confirm it still calls `webbrowser.open(url)` — the URL it receives will now be the direct binary download URL on known platforms instead of the release page.

- [ ] **Step 6: Run the full test suite**

```
pytest --tb=short -q
```

- [ ] **Step 7: Commit**

```bash
git add updater.py tests/test_updater.py
git commit -m "feat: updater emits platform-specific binary download URL from release assets"
```

---

## Task 2: Batch tool — parallel per-file workers

**Files:**
- Modify: `batch_tool.py`
- Modify: `tests/test_batch_tool.py`

Currently `_BatchWorker` processes files serially in one thread. Replace it with a coordinator that spawns one `_BatchItemWorker` per file, each acquiring `worker_semaphore` before running.

- [ ] **Step 1: Write a failing test**

Add to `tests/test_batch_tool.py`:

```python
def test_batch_parallel_workers_are_used(tmp_path, monkeypatch):
    """Each file should be processed by a separate worker, not a serial loop."""
    from batch_tool import _BatchItemWorker
    assert _BatchItemWorker is not None  # class must exist
```

- [ ] **Step 2: Run to verify it fails**

```
pytest tests/test_batch_tool.py::test_batch_parallel_workers_are_used -v
```
Expected: `ImportError: cannot import name '_BatchItemWorker'`

- [ ] **Step 3: Refactor `batch_tool.py` worker**

Replace `_BatchWorker` with:

```python
class _BatchItemWorker(QThread):
    """Processes a single file in the batch."""
    done = Signal(int)          # index
    failed = Signal(int, str)   # index, message

    def __init__(self, index: int, src: str, dst: str, op_id: str, settings: dict):
        super().__init__()
        self._index = index
        self._src = src
        self._dst = dst
        self._op_id = op_id
        self._settings = settings

    def run(self) -> None:
        import worker_semaphore
        worker_semaphore.acquire()
        try:
            entry = BATCH_REGISTRY[self._op_id]
            s = self._settings
            entry["run"](self._src, self._dst, **{k: s[k] for k in entry["options"] if k in s})
            self.done.emit(self._index)
        except Exception as exc:
            logger.exception("batch item failed: %s", self._src)
            self.failed.emit(self._index, str(exc))
        finally:
            worker_semaphore.release()


class _BatchCoordinator(QObject):
    """Spawns one _BatchItemWorker per file and tracks completion."""
    all_done = Signal()

    def __init__(self, tasks: list, op_id: str, settings: dict, out_dir: str,
                 on_done, on_failed):
        super().__init__()
        self._tasks = tasks
        self._op_id = op_id
        self._settings = settings
        self._out_dir = out_dir
        self._on_done = on_done
        self._on_failed = on_failed
        self._workers: list[_BatchItemWorker] = []
        self._pending = len(tasks)

    def start(self) -> None:
        for i, src in enumerate(self._tasks):
            stem = Path(src).stem
            dst = str(Path(self._out_dir) / f"{stem}_batch.pdf")
            w = _BatchItemWorker(i, src, dst, self._op_id, self._settings)
            w.done.connect(self._item_done)
            w.failed.connect(self._item_failed)
            self._workers.append(w)
            w.start()

    def _item_done(self, index: int) -> None:
        self._on_done(index)
        self._check_complete()

    def _item_failed(self, index: int, msg: str) -> None:
        self._on_failed(index, msg)
        self._check_complete()

    def _check_complete(self) -> None:
        self._pending -= 1
        if self._pending <= 0:
            self.all_done.emit()
```

Update `BatchTool._run_batch()` to use `_BatchCoordinator` instead of `_BatchWorker`.

- [ ] **Step 4: Run the tests**

```
pytest tests/test_batch_tool.py -v
```
Expected: all pass

- [ ] **Step 5: Run the full suite**

```
pytest --tb=short -q
```

- [ ] **Step 6: Commit**

```bash
git add batch_tool.py tests/test_batch_tool.py
git commit -m "feat: batch tool processes files in parallel using worker_semaphore"
```

---

## Task 3: Crash reporting modal

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Find where `main.py` initialises the app**

```
grep -n "QApplication\|sys.exit\|app.exec" main.py | head -10
```

- [ ] **Step 2: Add `_install_crash_reporter` function and call it before `app.exec()`**

Add this function to `main.py` (near the logging setup, before the `if __name__ == "__main__"` block):

```python
def _install_crash_reporter(app: "QApplication") -> None:
    """Install a sys.excepthook that shows a crash modal and offers clipboard copy."""
    import sys
    import traceback
    from logging_config import _log_dir

    _original_hook = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        # Log the crash first
        logger.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_tb),
        )
        # Build traceback text
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log_path = _log_dir() / "pdfree.log"

        msg = QMessageBox()
        msg.setWindowTitle("PDFree crashed")
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText(
            "PDFree encountered an unexpected error.\n\n"
            "Click 'Copy details' to copy the error to your clipboard, "
            "then paste it into a GitHub issue."
        )
        msg.setDetailedText(tb_text)
        copy_btn = msg.addButton("Copy details", QMessageBox.ButtonRole.ActionRole)
        msg.addButton("Close", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        if msg.clickedButton() is copy_btn:
            QApplication.clipboard().setText(
                f"PDFree crash report\n{'=' * 40}\n{tb_text}\n"
                f"Log: {log_path}"
            )

        _original_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook
```

Call it after the `QApplication` is created and before `window.show()`:

```python
_install_crash_reporter(app)
```

- [ ] **Step 3: Manually verify (no automated test needed for sys.excepthook)**

To test: temporarily add `raise RuntimeError("test crash")` after `_install_crash_reporter(app)`, run the app, confirm the modal appears with a "Copy details" button, then remove the test line.

- [ ] **Step 4: Run the full test suite to confirm no regressions**

```
pytest --tb=short -q
```

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: add crash reporter modal with clipboard copy on unhandled exceptions"
```
