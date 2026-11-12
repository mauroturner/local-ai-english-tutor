"""Pure parts of the UI layer: theme tokens, spacing and the state chip style."""

from __future__ import annotations

import pytest

from english_tutor.domain.models import SessionState
from english_tutor.i18n import en, es
from english_tutor.ui import theme
from english_tutor.ui.state_style import state_style


def test_every_theme_colour_is_a_light_dark_pair():
    assert theme.COLOR_NAMES, "the theme must list its colour tokens"
    for name in theme.COLOR_NAMES:
        value = getattr(theme, name)
        assert isinstance(value, tuple) and len(value) == 2, name
        assert all(isinstance(part, str) and part for part in value), name
        assert value[0] != value[1] or name.startswith("CHIP_"), name


def test_theme_colour_list_covers_every_pair_constant():
    pairs = {
        name
        for name, value in vars(theme).items()
        if name.isupper() and isinstance(value, tuple) and len(value) == 2
        and all(isinstance(v, str) for v in value)
    }
    assert pairs == set(theme.COLOR_NAMES)


def test_spacing_tokens_and_comfortable_density():
    assert (theme.SPACE_XS, theme.SPACE_S, theme.SPACE_M, theme.SPACE_L, theme.SPACE_XL) == (
        4, 8, 12, 16, 24,
    )
    assert theme.spacing("comfortable") == theme.Spacing(4, 8, 12, 16, 24)


def test_compact_density_is_tighter_but_never_zero():
    comfortable, compact = theme.spacing("comfortable"), theme.spacing("compact")
    for name in ("xs", "s", "m", "l", "xl"):
        assert 0 < getattr(compact, name) < getattr(comfortable, name), name
    assert compact.xs < compact.s < compact.m < compact.l < compact.xl


def test_unknown_density_means_comfortable():
    assert theme.spacing("huge") == theme.spacing("comfortable")


def test_font_family_is_segoe_ui():
    for font in (theme.FONT_TITLE, theme.FONT_HEADING, theme.FONT_HINT, theme.FONT_BODY):
        assert font[0] == "Segoe UI"
    assert theme.FONT_TITLE[1] == 20


@pytest.mark.parametrize(
    ("state", "key"),
    [(s, f"chip.{s.value}") for s in SessionState],
)
def test_state_style_returns_a_translated_key_and_a_colour_pair(state, key):
    got_key, colour = state_style(state)
    assert got_key == key
    assert key in en.STRINGS and key in es.STRINGS
    assert isinstance(colour, tuple) and len(colour) == 2


def test_state_style_colours_follow_the_traffic_light_rule():
    assert state_style(SessionState.IDLE)[1] == theme.CHIP_GREEN
    assert state_style(SessionState.RECORDING)[1] == theme.CHIP_RED
    for busy in (
        SessionState.LOADING,
        SessionState.TRANSCRIBING,
        SessionState.THINKING,
        SessionState.SPEAKING,
        SessionState.REPORTING,
    ):
        assert state_style(busy)[1] == theme.CHIP_AMBER


def test_new_ui_keys_exist_in_both_languages():
    for key in ("chat.empty", "tooltip.settings", "tooltip.end_session_disabled"):
        assert key in en.STRINGS and key in es.STRINGS
