"""The 'today and streak' line of the main window and the daily goal setting."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from english_tutor import i18n
from english_tutor.domain.progress import SessionStats
from english_tutor.settings.model import RESTART_FIELDS, UserSettings, parse_settings
from english_tutor.settings.registry import Category, Control, by_category
from english_tutor.ui.goal import goal_text

TODAY = date(2026, 11, 13)


@pytest.fixture(autouse=True)
def english():
    i18n.set_language("en")


def session(days_ago=0, minutes=5.0) -> SessionStats:
    when = datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time()).replace(hour=9)
    return SessionStats(when, minutes * 60, 3, 50, 20.0, 1, 1, 0, 0)


def test_nothing_to_say_without_goal_or_sessions():
    assert goal_text([], 0, TODAY) == ""


def test_progress_towards_the_goal_and_the_streak():
    text = goal_text([session(0, 4), session(1)], 10, TODAY)
    assert text == "Today: 4 / 10 min   Streak: 2 days"


def test_a_reached_goal_says_so():
    assert goal_text([session(0, 12)], 10, TODAY) == "Today: 12 min - goal reached   Streak: 1 day"


def test_a_streak_without_a_goal():
    assert goal_text([session(0), session(1), session(2)], 0, TODAY) == "Streak: 3 days"


def test_the_goal_alone_when_there_is_no_streak():
    assert goal_text([], 10, TODAY) == "Today: 0 / 10 min"


def test_the_text_follows_the_interface_language():
    i18n.set_language("es")
    assert goal_text([session(0, 4)], 10, TODAY) == "Hoy: 4 / 10 min   Racha: 1 día"


# ---- the setting ---------------------------------------------------------------------


def test_the_daily_goal_defaults_to_ten_minutes_and_applies_without_restart():
    assert UserSettings().daily_goal_minutes == 10
    spec = {s.key: s for s in by_category(Category.GENERAL)}["daily_goal_minutes"]
    assert spec.control is Control.SLIDER
    assert "daily_goal_minutes" not in RESTART_FIELDS


@pytest.mark.parametrize("raw, expected", [(0, 0), (25, 25), (60, 60)])
def test_valid_goals_are_kept(raw, expected):
    assert parse_settings({"daily_goal_minutes": raw})[0].daily_goal_minutes == expected


@pytest.mark.parametrize("raw", [-1, 61, "lots"])
def test_invalid_goals_fall_back_to_the_default(raw):
    assert parse_settings({"daily_goal_minutes": raw})[0].daily_goal_minutes == 10
