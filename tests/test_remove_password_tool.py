import shutil
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")

_app = QApplication.instance() or QApplication(sys.argv)
CORPUS = Path(__file__).parent / "corpus"


def _copy(name, tmp):
    p = tmp / name
    shutil.copy2(CORPUS / name, p)
    return p


def test_remove_password_opens_without_password(tmp_path):
    from remove_password_tool import _RemovePasswordWorker

    src = _copy("password.pdf", tmp_path)
    out = tmp_path / "out_unlocked.pdf"
    results = {}

    worker = _RemovePasswordWorker(str(src), str(out), "test")
    worker.finished.connect(lambda p: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()

    doc = fitz.open(str(out))
    assert not doc.is_encrypted
    assert doc.page_count > 0
    doc.close()


def test_remove_password_wrong_password_fails(tmp_path):
    from remove_password_tool import _RemovePasswordWorker

    src = _copy("password.pdf", tmp_path)
    out = tmp_path / "out_unlocked.pdf"
    results = {}

    worker = _RemovePasswordWorker(str(src), str(out), "wrongpassword")
    worker.finished.connect(lambda p: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" in results
    assert "done" not in results


def test_remove_password_unencrypted_passthrough(tmp_path):
    from remove_password_tool import _RemovePasswordWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out_plain.pdf"
    results = {}

    worker = _RemovePasswordWorker(str(src), str(out), "")
    worker.finished.connect(lambda p: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()

    doc = fitz.open(str(out))
    assert not doc.is_encrypted
    assert doc.page_count > 0
    doc.close()
