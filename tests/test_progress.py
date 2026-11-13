"""Session statistics: word counting and folding turns into numbers."""

from __future__ import annotations

from datetime import datetime, timedelta

from conftest import major, minor

from english_tutor.domain.models import Hesitation, Turn
from english_tutor.domain.progress import build_stats, count_words

START = datetime(2026, 11, 13, 10, 0, 0)


def turn(text="I go home", corrections=(), hesitations=(), speech_s=2.0, index=1) -> Turn:
    return Turn(index, text, "ok", tuple(corrections), None, tuple(hesitations), speech_s)


def test_count_words_keeps_contractions_whole():
    assert count_words("Don't worry, how's everything?") == 4
    assert count_words("") == 0
    assert count_words("  ...  ") == 0


def test_stats_fold_every_turn():
    turns = [
        turn("I go home", [major("I go", "I went"), minor("a apple", "an apple")], speech_s=3.0),
        turn(
            "and then I eat",
            hesitations=[Hesitation("and", "then", 1.5), Hesitation("", "and", 4.0)],
            speech_s=2.0,
            index=2,
        ),
    ]
    stats = build_stats(turns, START, START + timedelta(minutes=5))
    assert (stats.turns, stats.words, stats.speech_s) == (2, 7, 5.0)
    assert (stats.major, stats.minor) == (1, 1)
    assert (stats.pauses, stats.slow_starts) == (1, 1)
    assert stats.duration_s == 300.0
    assert stats.started_at == START


def test_repeated_corrections_are_all_counted():
    turns = [turn(corrections=[major("I go", "I went")]), turn(corrections=[major("I go", "I went")])]
    assert build_stats(turns, START, START).major == 2


def test_words_per_minute_uses_the_recorded_speech():
    stats = build_stats([turn("one two three four five six", speech_s=3.0)], START, START)
    assert stats.words_per_minute == 120.0


def test_words_per_minute_is_zero_without_speech_time():
    assert build_stats([turn(speech_s=0.0)], START, START).words_per_minute == 0.0


def test_a_clock_going_backwards_gives_zero_duration():
    assert build_stats([turn()], START, START - timedelta(seconds=5)).duration_s == 0.0


def test_stats_count_mistakes_per_category():
    from english_tutor.domain.models import Correction, Severity

    def fix(category):
        return Correction("a", "b", "x", Severity.MAJOR, category)

    turns = [turn(corrections=[fix("articles"), fix("articles"), fix("other"), fix(None)])]
    assert build_stats(turns, START, START).categories == (("articles", 2),)
