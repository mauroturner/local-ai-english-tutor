"""Filler sounds: counted from the literal transcript, reported, never errors."""

from __future__ import annotations

from datetime import datetime

from english_tutor.adapters.json_session_store import JsonSessionStore
from english_tutor.application.report import make_report
from english_tutor.domain.export import report_markdown
from english_tutor.domain.fillers import count_fillers, filler_line, ranked, total_fillers
from english_tutor.domain.formatting import format_report
from english_tutor.domain.models import SessionReport, TutorReply, Turn
from english_tutor.domain.progress import SessionStats, build_stats


def test_fillers_are_counted_ignoring_case_and_punctuation():
    counts = count_fillers("Um, I think, uh, it is, UM... a good idea. Hmm!")
    assert dict(counts) == {"um": 2, "uh": 1, "hmm": 1}


def test_spelling_variants_count_as_the_same_filler():
    assert dict(count_fillers("umm uhm uhh erm err hmmm hm")) == {
        "um": 2, "uh": 1, "er": 2, "hmm": 2,
    }


def test_words_that_are_also_real_words_are_not_fillers():
    text = "I like it, you know, and I will hum a song with them in the summer"
    assert count_fillers(text) == {}


def test_nothing_is_counted_in_an_empty_text():
    assert count_fillers("") == {} and total_fillers([]) == {}


def test_totals_add_up_and_rank_by_count_then_name():
    total = total_fillers(["um um uh", "uh er", "um"])
    assert ranked(total) == (("um", 3), ("uh", 2), ("er", 1))


def test_the_report_line():
    assert filler_line((("um", 3), ("uh", 2))) == "Filler words: um (3), uh (2)"
    assert filler_line(()) == ""


class _Tutor:
    def feedback(self, turns):
        raise RuntimeError("no model")


def turn(text) -> Turn:
    return Turn(1, text, "ok", (), None)


def test_the_report_lists_fillers_in_the_chat_text_and_the_export():
    report = make_report(_Tutor(), (turn("um I think uh so"), turn("um yes")))
    assert report.fillers == (("um", 2), ("uh", 1))
    assert "Filler words: um (2), uh (1)" in format_report(report)
    assert "Filler words: um (2), uh (1)" in report_markdown(report, datetime(2026, 11, 13))


def test_a_report_without_fillers_has_no_line():
    report = make_report(_Tutor(), (turn("hello there"),))
    assert report.fillers == () and "Filler words" not in format_report(report)
    assert SessionReport(0, (), (), None).fillers == ()


def test_fillers_are_never_mistakes(make_harness, fake_store):
    h = make_harness(["um uh er hmm"], [TutorReply("Ok.")], store=fake_store)
    h.say()
    assert fake_store.saves == [] and h.session.turns[0].user_text == "um uh er hmm"  # literal text


def test_the_session_statistics_count_them_and_store_them_only_when_present(tmp_path):
    turns = [turn("um I see"), turn("uh um well")]
    stats = build_stats(turns, datetime(2026, 11, 13, 9), datetime(2026, 11, 13, 10))
    assert stats.fillers == 3
    store = JsonSessionStore(tmp_path / "sessions.json")
    store.append(stats)
    store.append(SessionStats(datetime(2026, 11, 13, 11), 60.0, 1, 10, 5.0, 0, 0, 0, 0))
    text = (tmp_path / "sessions.json").read_text(encoding="utf-8")
    assert text.count('"fillers"') == 1
    assert [s.fillers for s in store.load()] == [3, 0]


def test_a_damaged_filler_count_is_read_as_zero(tmp_path):
    import json

    path = tmp_path / "sessions.json"
    JsonSessionStore(path).append(SessionStats(datetime(2026, 11, 13, 9), 60.0, 1, 10, 5.0, 0, 0, 0, 0, fillers=2))
    data = json.loads(path.read_text(encoding="utf-8"))
    for bad in ("many", None, -4):
        data["sessions"][0]["fillers"] = bad
        path.write_text(json.dumps(data), encoding="utf-8")
        assert JsonSessionStore(path).load()[0].fillers == 0
