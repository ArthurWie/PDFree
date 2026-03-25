"""Thin translation helpers for PDFree.

Usage
-----
Import ``tr`` to translate a string at runtime::

    from i18n import tr
    label = QLabel(tr("Save"))

Import ``QT_TRANSLATE_NOOP`` to mark a string for extraction without
translating it yet (typically used at module level where ``QApplication``
may not exist)::

    from i18n import QT_TRANSLATE_NOOP
    LABEL = QT_TRANSLATE_NOOP("PDFree", "Save")   # still the raw string
    # later, at widget-creation time:
    QLabel(tr(LABEL))

Generating / updating translation files
----------------------------------------
Run from the project root::

    pyside6-lupdate main.py -ts translations/pdffree_en.ts

To add a new locale (e.g. French)::

    cp translations/pdffree_en.ts translations/pdffree_fr.ts
    # edit pdffree_fr.ts with Qt Linguist, then compile:
    pyside6-lrelease translations/pdffree_fr.ts -qm translations/pdffree_fr.qm

The compiled ``.qm`` files must be placed in the ``translations/`` directory
next to ``main.py``. ``_install_translator`` in ``main.py`` loads the
appropriate ``.qm`` file at startup via ``QTranslator`` based on the system
locale, falling back to ``pdffree_en.qm`` when no match is found.
"""

from PySide6.QtCore import QCoreApplication

_CTX = "PDFree"


def tr(text: str) -> str:
    """Return the translation of *text* in the PDFree context."""
    return QCoreApplication.translate(_CTX, text)


def QT_TRANSLATE_NOOP(context: str, text: str) -> str:  # noqa: N802
    """Mark *text* for extraction by lupdate without translating it.

    This is a no-op at runtime — it returns *text* unchanged.
    lupdate recognises the ``QT_TRANSLATE_NOOP("ctx", "string")`` pattern
    and adds the string to the catalogue.
    """
    return text
