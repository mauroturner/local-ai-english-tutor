"""Pure display helpers used by the Settings rows."""

from __future__ import annotations

import pytest

from english_tutor.i18n import set_language
from english_tutor.ui.settings.values import (
    format_scale,
    index_of_nearest,
    option_labels,
    value_for_label,
)


@pytest.fixture(autouse=True)
def english():
    set_language("en")
    yield
    set_language("en")


@pytest.mark.parametrize(
    ("value", "text"), [(0.8, "80%"), (1.0, "100%"), (1.1, "110%"), (1.25, "125%"), (1.5, "150%")]
)
def test_format_scale(value, text):
    assert format_scale(value) == text


def test_index_of_nearest():
    options = [0.8, 0.9, 1.0, 1.1, 1.25, 1.5]
    assert index_of_nearest(options, 1.25) == 4
    assert index_of_nearest(options, 1.2) == 4
    assert index_of_nearest(options, 0.1) == 0
    assert index_of_nearest(options, 9) == 5


def test_option_labels_use_translations_when_they_exist():
    assert option_labels("appearance_mode", ("system", "light", "dark")) == [
        "System", "Light", "Dark",
    ]  # fmt: skip
    set_language("es")
    assert option_labels("appearance_mode", ("system", "light", "dark")) == [
        "Sistema", "Claro", "Oscuro",
    ]  # fmt: skip


def test_option_labels_fall_back_to_the_value():
    assert option_labels("log_level", ("DEBUG", "INFO")) == ["DEBUG", "INFO"]


def test_value_for_label_round_trips():
    options = ("auto", "cuda", "cpu")
    for value, label in zip(options, option_labels("whisper_device", options), strict=True):
        assert value_for_label("whisper_device", options, label) == value
    assert value_for_label("whisper_device", options, "nope") is None
