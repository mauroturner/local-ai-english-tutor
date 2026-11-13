"""The footer shows the hold instruction once: chip = state, status line = hint or detail."""

from __future__ import annotations

import pytest

from english_tutor import i18n
from english_tutor.domain.models import SessionState as St
from english_tutor.ui.state_style import status_line


@pytest.fixture(autouse=True)
def english():
    i18n.set_language("en")
    yield
    i18n.set_language("en")


def test_idle_shows_the_hold_hint_instead_of_repeating_ready():
    for message in ("Ready", "Ready: hold V"):
        assert status_line(St.IDLE, message, "V") == "Hold 'V' to speak, release to send"


def test_the_hint_uses_the_configured_key_and_language():
    assert status_line(St.IDLE, "Ready: hold Right Ctrl", "Right Ctrl").count("Right Ctrl") == 1
    i18n.set_language("es")
    assert "Right Ctrl" in status_line(St.IDLE, "Ready", "Right Ctrl")
    assert "Hold" not in status_line(St.IDLE, "Ready", "V")


def test_useful_messages_are_kept():
    too_short = "Too short or too quiet, try again"
    assert status_line(St.IDLE, too_short, "V") == too_short
    assert status_line(St.RECORDING, "Listening...", "V") == "Listening..."
    assert status_line(St.LOADING, "Loading speech model...", "V") == "Loading speech model..."


def test_practice_prompt_stays_and_is_translated():
    assert status_line(St.IDLE, "Practice: hold V to answer", "V") == "Practice: hold V to answer"
    i18n.set_language("es")
    assert status_line(St.IDLE, "Practice: hold V to answer", "V") != "Practice: hold V to answer"


def test_a_message_that_only_repeats_the_chip_is_dropped():
    assert status_line(St.THINKING, "Thinking...", "V") == ""
    assert status_line(St.TRANSCRIBING, "Transcribing...", "V") == ""
    assert status_line(St.SPEAKING, "Speaking...", "V") == ""


def test_empty_message_is_empty():
    assert status_line(St.IDLE, "", "V") == ""
    assert status_line(St.IDLE, None, "V") == ""


def test_unknown_messages_pass_through():
    assert status_line(St.IDLE, "Recording failed: boom", "V") == "Recording failed: boom"
