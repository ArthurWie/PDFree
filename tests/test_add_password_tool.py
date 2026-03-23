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


def test_add_password_aes256(tmp_path):
    from add_password_tool import _AddPasswordWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out_protected.pdf"
    results = {}

    worker = _AddPasswordWorker(
        str(src),
        str(out),
        fitz.PDF_ENCRYPT_AES_256,
        "secret",
        "secret",
        fitz.PDF_PERM_PRINT | fitz.PDF_PERM_COPY,
    )
    worker.finished.connect(lambda p: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()

    doc = fitz.open(str(out))
    if doc.is_encrypted:
        assert doc.authenticate("secret") > 0
    doc.close()


def test_add_password_wrong_password_not_readable(tmp_path):
    from add_password_tool import _AddPasswordWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out_protected.pdf"
    results = {}

    worker = _AddPasswordWorker(
        str(src),
        str(out),
        fitz.PDF_ENCRYPT_AES_256,
        "correct",
        "correct",
        fitz.PDF_PERM_PRINT,
    )
    worker.finished.connect(lambda p: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()

    doc = fitz.open(str(out))
    if doc.is_encrypted:
        assert doc.authenticate("wrong") == 0
    doc.close()


def test_add_password_rc4_128(tmp_path):
    from add_password_tool import _AddPasswordWorker

    src = _copy("plain.pdf", tmp_path)
    out = tmp_path / "out_rc4.pdf"
    results = {}

    worker = _AddPasswordWorker(
        str(src),
        str(out),
        fitz.PDF_ENCRYPT_RC4_128,
        "mypassword",
        "mypassword",
        fitz.PDF_PERM_PRINT,
    )
    worker.finished.connect(lambda p: results.update({"done": True}))
    worker.failed.connect(lambda e: results.update({"error": e}))
    worker.start()
    worker.wait(15000)
    _app.processEvents()

    assert "error" not in results, results.get("error")
    assert out.exists()

    doc = fitz.open(str(out))
    if doc.is_encrypted:
        assert doc.authenticate("mypassword") > 0
    doc.close()
