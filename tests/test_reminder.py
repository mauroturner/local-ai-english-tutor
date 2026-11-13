"""The daily reminder: time parsing, when it fires, and the setting."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest

from english_tutor.domain.progress import SessionStats
from english_tutor.domain.reminder import normalize_time, parse_time, should_remind, time_error
from english_tutor.settings.model import RESTART_FIELDS, UserSettings, parse_settings
from english_tutor.settings.registry import Category, Control, by_category

NOW = datetime(2026, 11, 13, 19, 30)


def session(minutes=5.0, days_ago=0) -> SessionStats:
    when = datetime.combine(NOW.date() - timedelta(days=days_ago), time(9, 0))
    return SessionStats(when, minutes * 60, 3, 50, 20.0, 1, 1, 0, 0)


@pytest.mark.parametrize("text, expected", [
    ("19:30", time(19, 30)), ("7:05", time(7, 5)), (" 00:00 ", time(0, 0)), ("23:59", time(23, 59)),
])
def test_valid_times(text, expected):
    assert parse_time(text) == expected


@pytest.mark.parametrize("text", ["", "24:00", "12:60", "7pm", "19.30", "1930", "-1:00", "ab:cd"])
def test_invalid_times(text):
    assert parse_time(text) is None


def test_errors_and_normalising():
    assert time_error("") is None and time_error("19:30") is None
    assert "HH:MM" in time_error("soon")
    assert normalize_time("7:05") == "07:05" and normalize_time("nope") == ""


def test_it_fires_at_the_chosen_time_when_nothing_was_done_today():
    assert should_remind(NOW, "19:30", [], 10, None)
    assert should_remind(NOW + timedelta(minutes=90), "19:30", [], 10, None)


def test_it_waits_for_the_time_and_is_not_shown_hours_late():
    assert not should_remind(NOW - timedelta(minutes=1), "19:30", [], 10, None)
    assert not should_remind(NOW + timedelta(hours=2, minutes=1), "19:30", [], 10, None)


def test_it_is_shown_once_a_day():
    assert not should_remind(NOW, "19:30", [], 10, NOW.date())
    assert should_remind(NOW, "19:30", [], 10, NOW.date() - timedelta(days=1))


def test_it_is_not_shown_when_the_goal_is_met():
    assert not should_remind(NOW, "19:30", [session(12)], 10, None)
    assert should_remind(NOW, "19:30", [session(4)], 10, None)  # practised, but not enough
    assert should_remind(NOW, "19:30", [session(40, days_ago=1)], 10, None)  # yesterday does not count


def test_without_a_goal_any_session_today_is_enough():
    assert not should_remind(NOW, "19:30", [session(1)], 0, None)
    assert should_remind(NOW, "19:30", [], 0, None)


def test_an_empty_or_invalid_reminder_never_fires():
    assert not should_remind(NOW, "", [], 10, None)
    assert not should_remind(NOW, "soon", [], 10, None)


def test_the_setting_is_off_by_default_validated_and_live():
    assert UserSettings().reminder_time == ""
    spec = {s.key: s for s in by_category(Category.GENERAL)}["reminder_time"]
    assert spec.control is Control.TEXT and "reminder_time" not in RESTART_FIELDS
    assert parse_settings({"reminder_time": "7:05"})[0].reminder_time == "07:05"
    assert parse_settings({"reminder_time": ""})[0].reminder_time == ""
    bad, warnings = parse_settings({"reminder_time": "tonight"})
    assert bad.reminder_time == "" and warnings


def test_the_day_is_taken_from_the_clock_not_the_session_dates():
    assert should_remind(datetime(2026, 11, 14, 19, 30), "19:30", [session(60)], 10, date(2026, 11, 13))
