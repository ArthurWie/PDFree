import importlib
import importlib.util
import os
import threading

import pytest

MINIMAL_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
    b'<rect width="100" height="100" fill="red"/>'
    b"</svg>"
)


def test_import():
    import svg_to_pdf_tool

    assert hasattr(svg_to_pdf_tool, "SvgToPdfTool")
    assert hasattr(svg_to_pdf_tool, "_SvgToPdfWorker")


def test_worker_nonexistent_file(tmp_path):
    from PySide6.QtCore import Qt

    from svg_to_pdf_tool import _SvgToPdfWorker

    out = str(tmp_path / "out.pdf")
    worker = _SvgToPdfWorker(["/nonexistent/file.svg"], out, (595, 842))

    errors = []
    results = []

    def on_failed(msg):
        errors.append(msg)

    def on_finished(path):
        results.append(path)

    worker.failed.connect(on_failed, Qt.ConnectionType.DirectConnection)
    worker.finished.connect(on_finished, Qt.ConnectionType.DirectConnection)
    worker.start()
    worker.wait(10000)

    # Either backend missing (no cairosvg/svglib) or file not found
    assert len(errors) == 1 or not results


def test_worker_empty_list(tmp_path):
    from PySide6.QtCore import Qt

    from svg_to_pdf_tool import _SvgToPdfWorker

    out = str(tmp_path / "out.pdf")
    worker = _SvgToPdfWorker([], out, (595, 842))

    errors = []

    def on_failed(msg):
        errors.append(msg)

    worker.failed.connect(on_failed, Qt.ConnectionType.DirectConnection)
    worker.start()
    worker.wait(10000)

    assert len(errors) == 1
    assert errors[0]  # non-empty message


@pytest.mark.skipif(
    importlib.util.find_spec("cairosvg") is None,
    reason="cairosvg not installed",
)
def test_valid_svg_conversion(tmp_path):
    import fitz

    from svg_to_pdf_tool import _SvgToPdfWorker

    svg_file = tmp_path / "test.svg"
    svg_file.write_bytes(MINIMAL_SVG)
    out = str(tmp_path / "out.pdf")

    results = []
    errors = []
    done = threading.Event()

    def on_finished(path):
        results.append(path)
        done.set()

    def on_failed(msg):
        errors.append(msg)
        done.set()

    worker = _SvgToPdfWorker([str(svg_file)], out, (595, 842))
    worker.finished.connect(on_finished)
    worker.failed.connect(on_failed)
    worker.start()
    done.wait(timeout=30)
    worker.wait()

    assert not errors, f"Worker failed: {errors}"
    assert results and results[0] == out
    assert os.path.exists(out)

    doc = fitz.open(out)
    assert doc.page_count >= 1
    doc.close()
