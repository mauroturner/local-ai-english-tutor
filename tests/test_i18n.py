"""i18n: catalogs stay in sync, lookups fall back safely, dates and statuses translate."""

from __future__ import annotations

import string
from datetime import date, datetime, time

import pytest

from english_tutor import i18n
from english_tutor.i18n import en, es


@pytest.fixture(autouse=True)
def english_after():
    i18n.set_language("en")
    yield
    i18n.set_language("en")


def placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_catalogs_have_identical_keys():
    assert set(en.STRINGS) == set(es.STRINGS)


def test_placeholders_match_between_languages():
    for key, text in en.STRINGS.items():
        assert placeholders(text) == placeholders(es.STRINGS[key]), key


def test_no_empty_translations():
    assert all(text.strip() for text in en.STRINGS.values())
    assert all(text.strip() for text in es.STRINGS.values())


def test_t_uses_the_active_language():
    assert i18n.t("tab.mistakes") == "Mistakes"
    i18n.set_language("es")
    assert i18n.t("tab.mistakes") == "Errores"


def test_t_formats_placeholders():
    assert i18n.t("hint.hold", key="V") == "Hold 'V' to speak, release to send"
    i18n.set_language("es")
    assert "V" in i18n.t("hint.hold", key="V")


def test_unknown_key_returns_the_key():
    assert i18n.t("no.such.key") == "no.such.key"
    i18n.set_language("es")
    assert i18n.t("no.such.key", x=1) == "no.such.key"


def test_missing_spanish_key_falls_back_to_english(monkeypatch):
    monkeypatch.setitem(en.STRINGS, "only.english", "English only")
    i18n.set_language("es")
    assert i18n.t("only.english") == "English only"


def test_missing_placeholder_value_does_not_raise():
    assert i18n.t("hint.hold") == "Hold '{key}' to speak, release to send"


def test_unknown_language_falls_back_to_english():
    i18n.set_language("fr")
    assert i18n.current_language() == "en"
    assert i18n.t("tab.mistakes") == "Mistakes"


def test_dates_and_times_in_english():
    moment = datetime(2026, 11, 12, 14, 5)
    assert i18n.format_date(moment) == "Nov 12, 2026"
    assert i18n.format_date(date(2026, 1, 3)) == "Jan 3, 2026"
    assert i18n.format_time(moment) == "2:05 PM"
    assert i18n.format_time(datetime(2026, 1, 1, 0, 7)) == "12:07 AM"
    assert i18n.format_time(time(12, 0)) == "12:00 PM"


def test_dates_and_times_in_spanish():
    i18n.set_language("es")
    moment = datetime(2026, 11, 12, 14, 5)
    assert i18n.format_date(moment) == "12 nov 2026"
    assert i18n.format_date(date(2026, 1, 3)) == "3 ene 2026"
    assert i18n.format_time(moment) == "14:05"
    assert i18n.format_time(datetime(2026, 1, 1, 0, 7)) == "00:07"


@pytest.mark.parametrize(
    "message",
    [
        "Ready",
        "Loading speech model...",
        "Listening...",
        "Transcribing...",
        "Thinking...",
        "Speaking...",
        "Preparing practice...",
        "Checking your answer...",
        "Writing feedback...",
        "Initializing...",
        "Too short or too quiet, try again",
        "Didn't catch that, try again",
    ],
)
def test_exact_status_messages_translate(message):
    assert i18n.translate_status(message) == message
    i18n.set_language("es")
    translated = i18n.translate_status(message)
    assert translated != message
    assert translated


def test_status_with_the_ptt_key_translates():
    assert i18n.translate_status("Ready: hold V") == "Ready: hold V"
    i18n.set_language("es")
    assert i18n.translate_status("Ready: hold Right Ctrl") == "Listo: mantén Right Ctrl"
    assert (
        i18n.translate_status("Practice: hold V to answer")
        == "Práctica: mantén V para responder"
    )


def test_unknown_status_passes_through():
    i18n.set_language("es")
    assert i18n.translate_status("Idle") == "Idle"
    assert i18n.translate_status("Recording failed: boom") == "Recording failed: boom"
    assert i18n.translate_status("") == ""
