import pytest

fitz = pytest.importorskip("fitz")
pytest.importorskip("pyhanko")


def _make_plain_pdf(path):
    doc = fitz.open()
    doc.new_page()
    doc.save(path)
    doc.close()


def test_plain_pdf_returns_empty(tmp_path):
    from validate_signature_tool import validate_signatures

    src = str(tmp_path / "plain.pdf")
    _make_plain_pdf(src)
    assert validate_signatures(src) == []


def test_missing_file_raises(tmp_path):
    from validate_signature_tool import validate_signatures

    with pytest.raises(Exception):
        validate_signatures(str(tmp_path / "nonexistent.pdf"))


def test_result_has_required_keys(tmp_path):
    from unittest.mock import MagicMock, patch

    from validate_signature_tool import validate_signatures

    src = str(tmp_path / "plain.pdf")
    _make_plain_pdf(src)
    mock_sig = MagicMock()
    mock_sig.field_name = "Sig1"
    mock_sig.signer_cert.subject.human_friendly = "CN=Test"
    mock_status = MagicMock()
    mock_status.trusted = True
    mock_status.bottom_line = True
    mock_status.summary.return_value = "OK"
    mock_status.signer_reported_dt = None
    mock_status.timestamp_validity = None
    with patch("validate_signature_tool.PdfFileReader") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_reader.embedded_regular_signatures = [mock_sig]
        mock_reader_cls.return_value = mock_reader
        with patch(
            "validate_signature_tool.validate_pdf_signature", return_value=mock_status
        ):
            results = validate_signatures(src)
    assert len(results) == 1
    r = results[0]
    for key in (
        "field",
        "signer",
        "trusted",
        "intact",
        "summary",
        "signing_time",
        "has_timestamp",
    ):
        assert key in r


def test_validation_error_is_caught(tmp_path):
    from unittest.mock import MagicMock, patch

    from validate_signature_tool import validate_signatures

    src = str(tmp_path / "plain.pdf")
    _make_plain_pdf(src)
    mock_sig = MagicMock()
    mock_sig.field_name = "Sig1"
    with patch("validate_signature_tool.PdfFileReader") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_reader.embedded_regular_signatures = [mock_sig]
        mock_reader_cls.return_value = mock_reader
        with patch(
            "validate_signature_tool.validate_pdf_signature",
            side_effect=Exception("cert error"),
        ):
            results = validate_signatures(src)
    assert len(results) == 1
    assert "Validation error" in results[0]["summary"]
    assert results[0]["trusted"] is False


def test_no_signatures_returns_empty_list(tmp_path):
    from unittest.mock import MagicMock, patch

    from validate_signature_tool import validate_signatures

    src = str(tmp_path / "plain.pdf")
    _make_plain_pdf(src)
    with patch("validate_signature_tool.PdfFileReader") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_reader.embedded_regular_signatures = []
        mock_reader_cls.return_value = mock_reader
        results = validate_signatures(src)
    assert results == []
