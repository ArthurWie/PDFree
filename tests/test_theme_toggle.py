import colors
from theme import apply_theme


def test_apply_dark_sets_bg():
    apply_theme(True)
    assert colors.BG == "#0F1117"


def test_apply_light_sets_bg():
    apply_theme(False)
    assert colors.BG == "#EEF2F7"


def test_toggle_twice_returns_to_original():
    apply_theme(False)
    original_bg = colors.BG
    apply_theme(True)
    apply_theme(False)
    assert colors.BG == original_bg
