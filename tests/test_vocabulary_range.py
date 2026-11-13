"""Vocabulary range: distinct words, new words, words used too often."""

from __future__ import annotations

import json
from datetime import datetime

from english_tutor.adapters.json_session_store import JsonSessionStore
from english_tutor.application.report import make_report
from english_tutor.domain.export import report_markdown
from english_tutor.domain.formatting import format_report, vocabulary_summary
from english_tutor.domain.models import SessionReport, Turn
from english_tutor.domain.progress import SessionStats, build_stats
from english_tutor.domain.vocabulary_range import (
    MAX_SHOWN,
    MAX_STORED,
    content_words,
    new_words,
    overused,
    session_words,
)


def test_only_content_words_count():
    assert content_words("I don't like the big, big apples at the market!") == [
        "big", "big", "apples", "market",
    ]


def test_short_words_numbers_and_stopwords_are_left_out():
    assert content_words("It is 15 of them, so we go to my uncle") == ["uncle"]


def test_the_distinct_words_are_sorted_and_bounded():
    assert session_words(["Banana apple", "apple cherry"]) == ("apple", "banana", "cherry")
    many = " ".join(f"word{chr(97 + i % 26)}{chr(97 + i // 26)}" for i in range(900))
    assert len(session_words([many.replace("word", "")])) <= MAX_STORED


def test_words_said_many_times_are_listed_most_frequent_first():
    text = "good good good good nice nice nice nice nice fine fine"
    assert overused([text]) == (("nice", 5), ("good", 4))
    assert overused([text], at=2) == (("nice", 5), ("good", 4), ("fine", 2))
    assert overused(["good good"]) == ()


def test_new_words_exclude_the_known_ones():
    assert new_words(("apple", "banana", "cherry"), {"banana"}) == ("apple", "cherry")
    assert len(new_words([f"w{i}" for i in range(30)], set())) == MAX_SHOWN


class _Tutor:
    def feedback(self, turns):
        raise RuntimeError("no model")


def turn(text) -> Turn:
    return Turn(1, text, "ok", (), None)


def test_the_report_counts_the_words_and_the_new_ones():
    turns = (turn("I visited Cordoba with my sister"), turn("Cordoba was beautiful"))
    report = make_report(_Tutor(), turns, known_words=frozenset({"visited", "sister"}))
    assert report.vocabulary_unique == 4
    assert report.vocabulary_new == ("beautiful", "cordoba")


def test_the_first_session_never_claims_new_words():
    report = make_report(_Tutor(), (turn("I visited Cordoba"),))
    assert report.vocabulary_unique == 2 and report.vocabulary_new == ()


def test_the_summary_text_in_the_chat_and_the_export():
    report = SessionReport(
        1, (), (), None, vocabulary_unique=54, vocabulary_new=("alpha", "beta"),
        overused_words=(("good", 7),),
    )
    line = "Vocabulary: 54 different words (2+ new: alpha, beta). Used often: good (7)"
    assert vocabulary_summary(report) == line
    assert line in format_report(report)
    assert line in report_markdown(report, datetime(2026, 11, 13))
    assert vocabulary_summary(SessionReport(1, (), (), None)) == ""


def test_the_stats_keep_the_words_and_the_file_only_when_there_are_some(tmp_path):
    stats = build_stats([turn("Cordoba was beautiful")], datetime(2026, 11, 13, 9), datetime(2026, 11, 13, 10))
    assert stats.vocabulary == ("beautiful", "cordoba")
    store = JsonSessionStore(tmp_path / "sessions.json")
    store.append(stats)
    store.append(SessionStats(datetime(2026, 11, 13, 11), 60.0, 1, 10, 5.0, 0, 0, 0, 0))
    data = json.loads((tmp_path / "sessions.json").read_text(encoding="utf-8"))
    assert data["sessions"][0]["vocabulary"] == ["beautiful", "cordoba"]
    assert "vocabulary" not in data["sessions"][1]
    assert [s.vocabulary for s in store.load()] == [("beautiful", "cordoba"), ()]


def test_damaged_stored_words_are_dropped(tmp_path):
    path = tmp_path / "sessions.json"
    JsonSessionStore(path).append(SessionStats(datetime(2026, 11, 13, 9), 60.0, 1, 10, 5.0, 0, 0, 0, 0))
    data = json.loads(path.read_text(encoding="utf-8"))
    for bad, expected in (("x", ()), ({"a": 1}, ()), (["ok", 5, "no way", None, "fine"], ("ok", "fine"))):
        data["sessions"][0]["vocabulary"] = bad
        path.write_text(json.dumps(data), encoding="utf-8")
        assert JsonSessionStore(path).load()[0].vocabulary == expected


def test_words_from_earlier_sessions_reach_the_next_report(make_harness, fake_stats):
    from english_tutor.domain.models import TutorReply

    fake_stats.sessions = [SessionStats(datetime(2026, 11, 1, 9), 60.0, 1, 10, 5.0, 0, 0, 0, 0, vocabulary=("sister",))]
    h = make_harness(["my sister visited Cordoba"], [TutorReply("Nice!")], session_stats=fake_stats)
    h.say()
    h.session.end_session()
    from english_tutor.application.events import ReportReady

    report = h.of_type(ReportReady)[-1].report
    assert report.vocabulary_new == ("cordoba", "visited")
