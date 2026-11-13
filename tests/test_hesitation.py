"""Long pauses: detection from word timings, history, report, practice and the setting."""

from __future__ import annotations

from datetime import datetime

from conftest import FakeCoach, FakeLog, major

from english_tutor.adapters.json_mistake_store import JsonMistakeStore
from english_tutor.application.events import MistakesChanged, PracticeFeedback
from english_tutor.application.practice import judge_fluency
from english_tutor.application.report import collect_pauses
from english_tutor.domain.corrections import normalize
from english_tutor.domain.export import report_markdown
from english_tutor.domain.formatting import format_report
from english_tutor.domain.hesitation import (
    as_corrections,
    explanation,
    find_hesitations,
    last_question,
    matching_words,
    pause_inside,
    restore_times,
)
from english_tutor.domain.mistakes import mistake_key
from english_tutor.domain.models import (
    Hesitation,
    MistakeRecord,
    PracticeOutcome,
    PracticeReply,
    SessionReport,
    Severity,
    TimedWord,
    Transcript,
    Turn,
    TutorReply,
)
from english_tutor.domain.practice_prompts import target_block
from english_tutor.settings.model import RESTART_FIELDS, UserSettings
from english_tutor.settings.registry import Category, Control, by_category


def words(*items: tuple[str, float, float]) -> tuple[TimedWord, ...]:
    return tuple(TimedWord(*item) for item in items)


# The example from the request: "how's ... everything" with a long gap in the middle.
HOWS = words((" I", 0.5, 0.6), (" think", 0.6, 0.9), (" how's", 1.0, 1.3),
             (" everything?", 3.0, 3.6))  # fmt: skip


# ------------------------------------------------------------------ detection
def test_a_long_gap_between_words_is_a_pause_with_the_words_around_it():
    (found,) = find_hesitations(HOWS)
    assert (found.before, found.after, found.pause_s) == ("think how's", "everything", 1.7)
    assert found.marked == "think how's … everything"
    assert found.phrase == "think how's everything"
    assert not found.at_start


def test_short_gaps_and_a_quick_start_are_not_pauses():
    assert find_hesitations(words((" Fine,", 0.4, 0.8), (" thanks.", 1.9, 2.3))) == ()
    assert find_hesitations(()) == ()


def test_the_time_from_the_key_press_to_the_first_word_is_a_slow_start():
    (found,) = find_hesitations(words((" Well,", 3.4, 3.7), (" I", 3.8, 3.9), (" went", 4.0, 4.3)))
    assert found.at_start and found.pause_s == 3.4
    assert found.marked == "… Well I went"
    assert explanation(found) == "You took 3.4 s to start speaking."


def test_thresholds_are_inclusive():
    exact = words((" a", 0.0, 0.5), (" b", 1.7, 2.0))
    assert len(find_hesitations(exact)) == 1
    assert find_hesitations(words((" a", 3.0, 3.2))) != ()


def test_explanation_names_the_two_words():
    (found,) = find_hesitations(HOWS)
    assert explanation(found) == "You paused 1.7 s between 'how's' and 'everything'."


# -------------------------------------------------------------------- history
def test_only_pauses_inside_a_sentence_go_to_the_history():
    start = Hesitation("", "Well I", 4.0)
    inside = Hesitation("how's", "everything", 1.5)
    (item,) = as_corrections([start, inside])
    assert item.severity is Severity.HESITATION
    assert (item.original, item.corrected) == ("how's … everything", "how's everything")
    assert normalize(item.original) == normalize(item.corrected)  # cannot match a real error


def test_session_turn_adds_the_pause_to_the_history_and_log(make_harness, fake_store):
    log = FakeLog()
    text = "I think how's everything?"
    timed = Transcript(text, 4.0, HOWS)
    h = make_harness([timed], [TutorReply("Good!")], store=fake_store, log=log)
    h.say()
    (record,) = fake_store.saves[-1]
    assert record.severity is Severity.HESITATION
    assert record.key == mistake_key("think how's … everything", "think how's everything")
    assert record.examples == (text,)
    assert ("pause", "think how's … everything (You paused 1.7 s between 'how's' and "
            "'everything'.)") in log.entries  # fmt: skip
    assert h.of_type(MistakesChanged)[-1].mistakes == (record,)
    assert h.session.turns[0].hesitations[0].pause_s == 1.7
    assert h.session.turns[0].corrections == ()  # a pause is never an error


def test_pauses_and_errors_of_one_turn_are_saved_together(make_harness, fake_store):
    reply = TutorReply("ok", (major("how's", "how is"),))
    h = make_harness([Transcript("I think how's everything?", 4.0, HOWS)], [reply],
                     store=fake_store)  # fmt: skip
    h.say()
    assert len(fake_store.saves) == 1
    assert {r.severity for r in fake_store.saves[0]} == {Severity.MAJOR, Severity.HESITATION}


def test_switch_off_records_no_pauses(make_harness, fake_store):
    h = make_harness([Transcript("I think how's everything?", 4.0, HOWS)], [TutorReply("ok")],
                     store=fake_store, track_pauses=lambda: False)  # fmt: skip
    h.say()
    assert fake_store.saves == [] and h.session.turns[0].hesitations == ()


def test_transcript_without_timings_records_nothing(make_harness, fake_store):
    h = make_harness(["I think how's everything?"], [TutorReply("ok")], store=fake_store)
    h.say()
    assert fake_store.saves == []


def test_pause_items_survive_a_save_and_load(tmp_path):
    now = datetime(2026, 11, 12, 9, 30)
    item = as_corrections([Hesitation("how's", "everything", 1.5)])[0]
    key = mistake_key(item.original, item.corrected)
    record = MistakeRecord(
        key, item.original, item.corrected, item.explanation, item.severity, 2, now, now, ("x",)
    )
    store = JsonMistakeStore(tmp_path / "mistakes.json")
    store.save([record])
    assert store.load() == [record]


# --------------------------------------------------------------------- report
def turn(index: int, reply: str, *pauses: Hesitation) -> Turn:
    return Turn(index, "said", reply, (), None, pauses)


def test_report_lists_unique_pauses_and_slow_starts_with_the_question_before():
    inside = Hesitation("how's", "everything", 1.5)
    turns = (
        turn(1, "Nice to meet you! How's everything?", Hesitation("", "Hi", 5.0)),
        turn(2, "Cool. What did you do yesterday?", inside),
        turn(3, "ok", Hesitation("", "I went", 3.2), Hesitation("How's", "everything", 2.0)),
    )
    pauses, starts = collect_pauses(turns)
    assert pauses == (inside,)  # same words, different case: counted once
    assert starts == (("What did you do yesterday?", 3.2),)  # the first turn has no question


def test_last_question_picks_the_final_question():
    assert last_question("That sounds fun! What did you eat?") == "What did you eat?"
    assert last_question("No question here.") == "No question here."
    assert last_question("x" * 300).endswith("…") and len(last_question("x" * 300)) == 120


def test_report_text_and_markdown_show_pauses_but_not_as_errors():
    report = SessionReport(2, (), (), None, None, (Hesitation("how's", "everything", 1.5),),
                           (("How are you?", 3.5),))  # fmt: skip
    text = format_report(report)
    assert "Major errors: none" in text
    assert 'Long pauses (practice these phrases):\n  - "how\'s … everything"' in text
    assert 'Slow starts:\n  - 3.5 s to answer "How are you?"' in text
    markdown = report_markdown(report, datetime(2026, 11, 12))
    assert "## Long pauses" in markdown and "## Slow starts" in markdown


def test_report_without_pauses_is_unchanged():
    text = format_report(SessionReport(1, (), (), None))
    assert "pauses" not in text.lower() and "slow starts" not in text.lower()


# ------------------------------------------------------------------- practice
def pause_record() -> MistakeRecord:
    now = datetime(2026, 11, 12)
    item = as_corrections([Hesitation("how's", "everything", 1.5)])[0]
    key = mistake_key(item.original, item.corrected)
    return MistakeRecord(
        key, item.original, item.corrected, item.explanation, item.severity, 1, now, now, ()
    )


CORRECT = PracticeReply(PracticeOutcome.CORRECT, "Great!", "Next?")


def test_using_the_phrase_with_a_pause_inside_it_means_try_again():
    pauses = (Hesitation("how's", "everything", 1.4),)
    result = judge_fluency(pause_record(), CORRECT, pauses)
    assert result.outcome is PracticeOutcome.INCORRECT
    assert result.feedback == ("You said it, but you paused 1.4 seconds between 'how's' and "
                               "'everything'. Try once more, in one go.")  # fmt: skip
    assert result.next_prompt == "Next?"


def test_pauses_elsewhere_or_a_slow_start_do_not_count():
    elsewhere = (Hesitation("I", "think", 2.0), Hesitation("", "how's everything", 4.0))
    assert judge_fluency(pause_record(), CORRECT, elsewhere) is CORRECT
    assert pause_inside("how's everything", elsewhere) is None


def test_grammar_mistakes_are_judged_by_the_coach_alone():
    record = MistakeRecord("k", "I go", "I went", "Past.", Severity.MAJOR, 1,
                           datetime(2026, 1, 1), datetime(2026, 1, 1), ())  # fmt: skip
    pauses = (Hesitation("I", "went", 3.0),)
    assert judge_fluency(record, CORRECT, pauses) is CORRECT


def test_practice_turn_counts_the_measured_pause(make_harness, fake_store):
    fake_store.records = [pause_record()]
    coach = FakeCoach([PracticeReply(PracticeOutcome.NOT_USED, "Let's go.", "How's it going?"),
                       CORRECT])  # fmt: skip
    timed = words((" how's", 0.3, 0.6), (" everything", 2.2, 2.8))
    h = make_harness([Transcript("how's everything", 3.0, timed)], store=fake_store, coach=coach)
    h.session.start_practice(pause_record().key)
    h.say()
    assert h.of_type(PracticeFeedback)[-1].outcome is PracticeOutcome.INCORRECT
    saved = fake_store.saves[-1][0]
    assert (saved.practice_attempts, saved.practice_successes) == (1, 0)


def test_pause_target_prompt_asks_for_the_phrase_not_for_grammar():
    block = target_block(pause_record())
    assert block.startswith("TARGET (fluency, not a grammar mistake):")
    assert 'say "how\'s everything" smoothly' in block
    assert 'Never "incorrect"' in block


# -------------------------------------------------------------------- setting
def test_setting_is_on_by_default_in_general_and_applies_without_restart():
    assert UserSettings().track_pauses is True
    spec = {s.key: s for s in by_category(Category.GENERAL)}["track_pauses"]
    assert spec.control is Control.SWITCH
    assert "track_pauses" not in RESTART_FIELDS


def test_switch_is_read_on_every_turn(make_harness, fake_store):
    enabled = [False]
    h = make_harness([Transcript("I think how's everything?", 4.0, HOWS)] * 2,
                     [TutorReply("a"), TutorReply("b")], store=fake_store,
                     track_pauses=lambda: enabled[0])  # fmt: skip
    h.say()
    enabled[0] = True  # what Save does
    h.say()
    assert [len(t.hesitations) for t in h.session.turns] == [0, 1]


# ------------------------------------------------------------- timing words
def test_timed_words_are_kept_only_while_they_repeat_the_text():
    timed = words((" How's", 0.4, 0.8), (" everything?", 2.5, 3.1), (" everything.", 3.1, 3.4),
                  (" Thank", 5.0, 5.2))  # fmt: skip
    kept = matching_words("How's everything?", timed)
    assert [w.text for w in kept] == [" How's", " everything?"]


def test_timed_words_stop_at_the_first_difference():
    timed = words((" I", 0.0, 0.2), (" think", 0.2, 0.5), (" so", 2.0, 2.2))
    assert [w.text for w in matching_words("I thought so", timed)] == [" I"]


def test_session_asks_for_timings_only_while_tracking(make_harness):
    enabled = [True]
    h = make_harness(["hi", "hi"], [TutorReply("a"), TutorReply("b")],
                     track_pauses=lambda: enabled[0])  # fmt: skip
    h.say()
    enabled[0] = False
    h.say()
    assert h.stt.with_words == [True, False]


def test_words_timed_on_joined_speech_go_back_to_the_recording():
    # Speech from 0.5-1.5 s and 3.5-4.5 s; aligned on the 2 s of joined speech.
    joined = words((" how's", 0.6, 0.95), ("?", 0.95, 0.95), (" everything", 1.05, 1.6))
    restored = restore_times(joined, [(0.5, 1.5), (3.5, 4.5)])
    assert [(w.text, round(w.start_s, 2), round(w.end_s, 2)) for w in restored] == [
        (" how's", 1.1, 1.45), (" everything", 3.55, 4.1),
    ]  # fmt: skip
    (pause,) = find_hesitations(restored)
    assert (pause.before, pause.after, pause.pause_s) == ("how's", "everything", 2.1)


def test_a_word_is_kept_inside_its_stretch_of_speech():
    stretched = words((" well", 0.5, 1.4))  # middle in the first stretch, end past it
    (word,) = restore_times(stretched, [(3.0, 4.0), (6.0, 7.0)])
    assert (word.start_s, word.end_s) == (3.5, 4.0)
    assert restore_times(stretched, []) == ()
