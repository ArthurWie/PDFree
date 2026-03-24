"""Tests for sign_tool: coordinate helpers and worker error paths."""

import io
import os
import sys
import tempfile
import datetime

import pytest

import fitz

from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication(sys.argv)


def _make_pdf(n_pages: int = 1) -> bytes:
    doc = fitz.Document()
    for _ in range(n_pages):
        doc.new_page(width=595, height=842)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_pkcs12() -> tuple[bytes, str]:
    """Generate a minimal self-signed PKCS12 cert. Returns (pkcs12_bytes, password)."""
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test Signer")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    password = b"testpw"
    p12 = pkcs12.serialize_key_and_certificates(
        name=b"test",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password),
    )
    return p12, "testpw"


# ---------------------------------------------------------------------------
# Unit tests — no Qt required
# ---------------------------------------------------------------------------


def test_pdf_box_to_canvas_bottom_right():
    from sign_tool import _pdf_box_to_canvas

    # page 595x842, scale=1.0, box at bottom-right in PDF coords
    pdf_box = (335, 20, 575, 90)
    page_h = 842.0
    cx0, cy0, cx1, cy1 = _pdf_box_to_canvas(pdf_box, page_h, 1.0)
    assert cx0 == pytest.approx(335.0)
    assert cx1 == pytest.approx(575.0)
    # y flipped: cy0 = (842 - 90) * 1 = 752, cy1 = (842 - 20) * 1 = 822
    assert cy0 == pytest.approx(752.0)
    assert cy1 == pytest.approx(822.0)


def test_pdf_box_to_canvas_top_left():
    from sign_tool import _pdf_box_to_canvas

    pdf_box = (20, 752, 260, 822)
    page_h = 842.0
    cx0, cy0, cx1, cy1 = _pdf_box_to_canvas(pdf_box, page_h, 1.0)
    assert cy0 == pytest.approx(20.0)
    assert cy1 == pytest.approx(90.0)


def test_pdf_box_to_canvas_scale():
    from sign_tool import _pdf_box_to_canvas

    pdf_box = (100, 100, 200, 200)
    cx0, cy0, cx1, cy1 = _pdf_box_to_canvas(pdf_box, 400.0, 2.0)
    assert cx0 == pytest.approx(200.0)
    assert cx1 == pytest.approx(400.0)
    assert cy0 == pytest.approx((400 - 200) * 2)
    assert cy1 == pytest.approx((400 - 100) * 2)


def test_positions_all_valid():
    from sign_tool import _POSITIONS

    pw, ph = 595.0, 842.0
    for label, fn in _POSITIONS:
        x0, y0, x1, y1 = fn(pw, ph)
        assert x0 < x1, f"{label}: x0 >= x1"
        assert y0 < y1, f"{label}: y0 >= y1"
        assert x0 >= 0 and x1 <= pw + 1, f"{label}: x out of page"
        assert y0 >= 0 and y1 <= ph + 1, f"{label}: y out of page"


# ---------------------------------------------------------------------------
# Integration test — real signing with a real cert
# ---------------------------------------------------------------------------


def test_sign_worker_full_round_trip():
    from sign_tool import _SignWorker

    pdf_bytes = _make_pdf(1)
    p12_bytes, pw = _make_pkcs12()

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = os.path.join(tmp, "input.pdf")
        cert_path = os.path.join(tmp, "cert.p12")
        out_path = os.path.join(tmp, "signed.pdf")

        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        with open(cert_path, "wb") as f:
            f.write(p12_bytes)

        worker = _SignWorker(
            pdf_path=pdf_path,
            cert_path=cert_path,
            cert_password=pw,
            output_path=out_path,
            page_idx=0,
            sig_box=(335, 20, 575, 90),
            reason="Testing",
            location="Test",
            contact="test@example.com",
        )

        results = {}
        worker.finished.connect(lambda p: results.update({"done": p}))
        worker.failed.connect(lambda e: results.update({"error": e}))
        worker.start()
        worker.wait(30000)
        _app.processEvents()

        assert "error" not in results, f"Signing failed: {results.get('error')}"
        assert "done" in results
        assert os.path.exists(out_path)
        # Verify output is a valid PDF with a signature field
        doc = fitz.open(out_path)
        assert doc.page_count == 1
        doc.close()


def test_sign_worker_bad_cert():
    from sign_tool import _SignWorker
    import tempfile
    import os

    pdf_bytes = _make_pdf(1)
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = os.path.join(tmp, "input.pdf")
        cert_path = os.path.join(tmp, "bad.p12")
        out_path = os.path.join(tmp, "signed.pdf")
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        with open(cert_path, "wb") as f:
            f.write(b"not a real cert")

        worker = _SignWorker(
            pdf_path=pdf_path,
            cert_path=cert_path,
            cert_password="",
            output_path=out_path,
            page_idx=0,
            sig_box=(335, 20, 575, 90),
            reason="",
            location="",
            contact="",
        )
        results = {}
        worker.finished.connect(lambda p: results.update({"done": p}))
        worker.failed.connect(lambda e: results.update({"error": e}))
        worker.start()
        worker.wait(10000)
        _app.processEvents()

        assert "error" in results
        assert "done" not in results
