"""Progress maths: rates, trends, the weekly summary, the streak and the daily goal."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from english_tutor.domain.progress import (
    MIN_WORDS,
    SessionStats,
    Trend,
    best_session,
    goal_met,
    meaningful,
    minutes_on,
    streak_days,
    trend,
    week_summary,
)

TODAY = date(2026, 11, 13)


def session(days_ago=0, words=100, major=2, minor=3, pauses=1, duration_s=600.0, speech_s=50.0):
    when = datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time()).replace(hour=9)
    return SessionStats(when, duration_s, 5, words, speech_s, major, minor, pauses, 0)


# ---- rates ----------------------------------------------------------------------


def test_rates_are_per_one_hundred_words():
    s = session(words=200, major=2, minor=4, pauses=3)
    assert s.mistakes_per_100_words == 3.0
    assert s.pauses_per_100_words == 1.5


def test_rates_are_zero_without_words():
    s = session(words=0, major=2)
    assert s.mistakes_per_100_words == 0.0 and s.pauses_per_100_words == 0.0


def test_short_sessions_are_left_out_of_the_rates():
    sessions = [session(words=MIN_WORDS - 1), session(words=MIN_WORDS)]
    assert meaningful(sessions) == [sessions[1]]


# ---- trend ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "values, lower_is_better, expected",
    [
        ([5, 5, 3, 3], True, Trend.BETTER),
        ([3, 3, 5, 5], True, Trend.WORSE),
        ([3, 3, 5, 5], False, Trend.BETTER),
        ([5, 5, 3, 3], False, Trend.WORSE),
        ([4, 4, 4, 4.2], True, Trend.STEADY),  # within the 10 % tolerance
        ([0, 0, 0, 0], True, Trend.STEADY),
        ([0, 0, 2, 2], True, Trend.WORSE),
        ([2, 3, 4], True, Trend.UNKNOWN),  # too few sessions to say
        ([], True, Trend.UNKNOWN),
    ],
)
def test_trend_compares_the_older_half_with_the_newer_half(values, lower_is_better, expected):
    assert trend(values, lower_is_better) is expected


def test_trend_ignores_the_middle_session_of_an_odd_list():
    assert trend([5, 5, 99, 3, 3], True) is Trend.BETTER


# ---- week summary and best -----------------------------------------------------------


def test_week_summary_counts_the_last_seven_days_including_today():
    sessions = [
        session(0, words=100, duration_s=300), session(6, words=50, duration_s=120),
        session(7, words=999, duration_s=999),  # outside the week
    ]
    summary = week_summary(sessions, TODAY)
    assert (summary.sessions, summary.words) == (2, 150)
    assert summary.minutes == 7.0


def test_week_summary_of_nothing_is_zero():
    assert week_summary([], TODAY).sessions == 0


def test_best_session_has_the_lowest_rate_among_meaningful_ones():
    low = session(3, words=100, major=0, minor=1)
    high = session(1, words=100, major=4, minor=4)
    tiny = session(0, words=MIN_WORDS - 1, major=0, minor=0)  # would win but is too short
    assert best_session([high, tiny, low], lambda s: s.mistakes_per_100_words) is low
    assert best_session([tiny], lambda s: s.mistakes_per_100_words) is None


# ---- daily goal and streak ---------------------------------------------------------------


def test_minutes_on_a_day_add_every_session_of_that_day():
    sessions = [session(0, duration_s=300), session(0, duration_s=180), session(1, duration_s=900)]
    assert minutes_on(sessions, TODAY) == 8.0
    assert minutes_on(sessions, TODAY - timedelta(days=2)) == 0.0


def test_streak_counts_consecutive_days_ending_today():
    assert streak_days([session(0), session(1), session(2), session(4)], TODAY) == 3


def test_streak_is_still_alive_when_today_has_no_session_yet():
    assert streak_days([session(1), session(2)], TODAY) == 2


def test_streak_is_broken_after_a_missed_day():
    assert streak_days([session(2), session(3)], TODAY) == 0
    assert streak_days([], TODAY) == 0


def test_two_sessions_on_one_day_count_once():
    assert streak_days([session(0), session(0), session(1)], TODAY) == 2


def test_goal_met_needs_enough_minutes_today():
    sessions = [session(0, duration_s=600)]
    assert goal_met(sessions, 10, TODAY)
    assert not goal_met(sessions, 11, TODAY)
    assert not goal_met([session(1, duration_s=6000)], 10, TODAY)


def test_a_goal_of_zero_is_off_and_never_met():
    assert not goal_met([session(0, duration_s=6000)], 0, TODAY)
