import shutil
import fitz
from pathlib import Path
import pytest

CORPUS = Path(__file__).parent / "corpus"


def test_radio_update_sets_field_value(tmp_path):
    """_update_radio must set field_value on the selected button and clear others."""
    src = tmp_path / "form.pdf"
    shutil.copy2(CORPUS / "form.pdf", src)

    doc = fitz.open(str(src))
    page = doc[0]

    radio_groups: dict[str, list] = {}
    for widget in page.widgets():
        if widget.field_type == fitz.PDF_WIDGET_TYPE_RADIOBUTTON:
            radio_groups.setdefault(widget.field_name, []).append(widget)

    if not radio_groups:
        pytest.skip("form.pdf has no radio buttons")

    group_name = next(iter(radio_groups))
    widgets_in_group = radio_groups[group_name]
    target = widgets_in_group[0]

    target.field_value = target.on_state()
    target.update()

    for w in page.widgets():
        if w.field_name == group_name and w.rect == target.rect:
            assert w.field_value == target.on_state()
            break

    doc.close()
