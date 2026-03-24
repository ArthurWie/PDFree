"""Tests for QTabWidget multi-document support in ViewTool."""

import sys
import pytest


def _get_or_create_app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="module")
def qapp():
    return _get_or_create_app()


@pytest.fixture
def pdf_file(tmp_path):
    import fitz

    doc = fitz.open()
    doc.new_page()
    p = tmp_path / "test.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


@pytest.fixture
def pdf_file2(tmp_path):
    import fitz

    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    p = tmp_path / "test2.pdf"
    doc.save(str(p))
    doc.close()
    return str(p)


def test_tab_widget_exists(qapp):
    from view_tool import ViewTool

    vt = ViewTool()
    from PySide6.QtWidgets import QTabWidget

    assert hasattr(vt, "_tab_widget")
    assert isinstance(vt._tab_widget, QTabWidget)
    vt.cleanup()


def test_open_file_creates_tab(qapp, pdf_file):
    from view_tool import ViewTool

    vt = ViewTool()
    vt.open_file(pdf_file)
    assert vt._tab_widget.count() == 1
    vt.cleanup()


def test_open_two_files_creates_two_tabs(qapp, pdf_file, pdf_file2):
    from view_tool import ViewTool

    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.open_file(pdf_file2)
    assert vt._tab_widget.count() == 2
    vt.cleanup()


def test_open_duplicate_focuses_existing_tab(qapp, pdf_file):
    from view_tool import ViewTool

    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.open_file(pdf_file)  # same file again
    assert vt._tab_widget.count() == 1  # still 1, not 2
    vt.cleanup()


def test_active_pane_matches_current_tab(qapp, pdf_file, pdf_file2):
    from view_tool import ViewTool

    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.open_file(pdf_file2)
    # Switch to first tab
    vt._tab_widget.setCurrentIndex(0)
    pane0 = vt.active_pane
    # Switch to second tab
    vt._tab_widget.setCurrentIndex(1)
    pane1 = vt.active_pane
    assert pane0 is not pane1
    vt.cleanup()


def test_modified_aggregate(qapp, pdf_file, pdf_file2):
    from view_tool import ViewTool

    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.open_file(pdf_file2)
    assert vt._modified is False
    # Mark only the second pane as modified
    vt._tab_widget.widget(1)._is_modified = True
    assert vt._modified is True
    vt._tab_widget.widget(1)._is_modified = False
    assert vt._modified is False
    vt.cleanup()


def test_close_tab_removes_pane(qapp, pdf_file, pdf_file2):
    from view_tool import ViewTool

    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.open_file(pdf_file2)
    assert vt._tab_widget.count() == 2
    vt._close_tab(0)
    assert vt._tab_widget.count() == 1
    vt.cleanup()


def test_cleanup_closes_all_panes(qapp, pdf_file, pdf_file2):
    from view_tool import ViewTool

    vt = ViewTool()
    vt.open_file(pdf_file)
    vt.open_file(pdf_file2)
    pane0 = vt._tab_widget.widget(0)
    pane1 = vt._tab_widget.widget(1)
    vt.cleanup()
    # Docs should be closed
    assert pane0._doc is None
    assert pane1._doc is None


def test_close_unmodified_tab_no_dialog(qapp, pdf_file, monkeypatch):
    """Unmodified tab closes immediately without showing a dialog."""
    from view_tool import ViewTool
    from PySide6.QtWidgets import QMessageBox

    dialog_shown = []
    monkeypatch.setattr(
        QMessageBox,
        "exec",
        lambda self: dialog_shown.append(True) or QMessageBox.StandardButton.Discard,
    )
    vt = ViewTool()
    vt.open_file(pdf_file)
    vt._close_tab(0)
    assert len(dialog_shown) == 0
    assert vt._tab_widget.count() == 0
    vt.cleanup()


def test_close_modified_tab_discard_closes_tab(qapp, pdf_file, monkeypatch):
    """Modified tab: clicking Discard closes the tab without saving."""
    from view_tool import ViewTool
    from PySide6.QtWidgets import QMessageBox

    def fake_exec(self):
        # simulate Discard by storing the discard button reference
        self._fake_clicked = self._discard_btn
        return 0

    def fake_clicked_button(self):
        return getattr(self, "_fake_clicked", None)

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "clickedButton", fake_clicked_button)

    vt = ViewTool()
    vt.open_file(pdf_file)
    vt._tab_widget.widget(0)._is_modified = True
    vt._close_tab(0)
    assert vt._tab_widget.count() == 0
    vt.cleanup()


def test_close_modified_tab_cancel_keeps_tab(qapp, pdf_file, monkeypatch):
    """Modified tab: clicking Cancel keeps the tab open."""
    from view_tool import ViewTool
    from PySide6.QtWidgets import QMessageBox

    def fake_exec(self):
        # simulate Cancel — clickedButton returns something that is neither save nor discard
        self._fake_clicked = None
        return 0

    def fake_clicked_button(self):
        return None

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "clickedButton", fake_clicked_button)

    vt = ViewTool()
    vt.open_file(pdf_file)
    vt._tab_widget.widget(0)._is_modified = True
    vt._close_tab(0)
    assert vt._tab_widget.count() == 1
    vt.cleanup()


def test_quit_with_no_unsaved_accepts_event(qapp, pdf_file):
    """closeEvent accepts normally when no panes are modified."""
    from view_tool import ViewTool
    from PySide6.QtGui import QCloseEvent

    vt = ViewTool()
    vt.open_file(pdf_file)
    event = QCloseEvent()
    vt.closeEvent(event)
    assert event.isAccepted()
    vt.cleanup()


def test_quit_with_unsaved_dialog_discard_all_accepts(qapp, pdf_file, monkeypatch):
    """closeEvent with unsaved pane: Discard All accepts the event."""
    from view_tool import ViewTool
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QMessageBox

    clicked = []

    def fake_exec(self):
        clicked.append("discard_all")
        self._fake_clicked = self._discard_all_btn
        return 0

    def fake_clicked_button(self):
        return getattr(self, "_fake_clicked", None)

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "clickedButton", fake_clicked_button)

    vt = ViewTool()
    vt.open_file(pdf_file)
    vt._tab_widget.widget(0)._is_modified = True

    event = QCloseEvent()
    vt.closeEvent(event)
    assert len(clicked) == 1
    assert event.isAccepted()
    vt.cleanup()


def test_quit_with_unsaved_dialog_cancel_ignores_event(qapp, pdf_file, monkeypatch):
    """closeEvent with unsaved pane: Cancel ignores the event."""
    from view_tool import ViewTool
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QMessageBox

    def fake_exec(self):
        self._fake_clicked = None
        return 0

    def fake_clicked_button(self):
        return None

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "clickedButton", fake_clicked_button)

    vt = ViewTool()
    vt.open_file(pdf_file)
    vt._tab_widget.widget(0)._is_modified = True

    event = QCloseEvent()
    vt.closeEvent(event)
    assert not event.isAccepted()
    vt.cleanup()


def test_open_btn_initial_label(qapp):
    """Button reads 'Open PDF' when no tabs are open."""
    from view_tool import ViewTool

    vt = ViewTool()
    assert hasattr(vt, "_open_btn")
    assert vt._open_btn.text() == "Open PDF"
    vt.cleanup()


def test_open_btn_label_after_open(qapp, pdf_file):
    """Button reads '+ Add PDF' after a file is opened."""
    from view_tool import ViewTool

    vt = ViewTool()
    vt.open_file(pdf_file)
    assert vt._open_btn.text() == "+ Add PDF"
    vt.cleanup()


def test_open_btn_label_after_close_all(qapp, pdf_file):
    """Button reverts to 'Open PDF' after the last tab is closed."""
    from view_tool import ViewTool

    vt = ViewTool()
    vt.open_file(pdf_file)
    vt._close_tab(0)
    assert vt._open_btn.text() == "Open PDF"
    vt.cleanup()


def test_open_btn_label_with_initial_path(qapp, pdf_file):
    """Button reads '+ Add PDF' when ViewTool is constructed with initial_path."""
    from view_tool import ViewTool

    vt = ViewTool(initial_path=pdf_file)
    assert vt._open_btn.text() == "+ Add PDF"
    vt.cleanup()
