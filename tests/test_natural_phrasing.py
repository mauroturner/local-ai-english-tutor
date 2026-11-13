"""'More natural' phrasing: shown for correct sentences, never a mistake, never spoken."""

from __future__ import annotations

from conftest import major

from english_tutor.adapters.file_conversation_log import FileConversationLog
from english_tutor.adapters.ollama_parsing import parse_tutor_reply
from english_tutor.application.events import TutorSaid
from english_tutor.domain.corrections import pick_natural
from english_tutor.domain.models import TutorReply
from english_tutor.domain.prompts import TURN_SCHEMA, TURN_SYSTEM_PROMPT
from english_tutor.settings.model import UserSettings
from english_tutor.settings.registry import Category, Control, by_category

SAID = "The final was a little bit sad for me"
NATURAL = "The ending was a bit sad for me."


# ---- parsing -------------------------------------------------------------------


def test_the_parser_reads_the_natural_version():
    reply = parse_tutor_reply('{"reply": "ok", "errors": [], "natural": "  Better.  "}')
    assert reply.natural == "Better."


def test_an_empty_or_missing_or_odd_natural_is_none():
    for tail in ('"natural": ""', '"natural": "   "', '"natural": 5', '"natural": null', '"x": 1'):
        assert parse_tutor_reply('{"reply": "ok", "errors": [], ' + tail + "}").natural is None


def test_the_schema_asks_for_natural_and_the_prompt_explains_it():
    assert TURN_SCHEMA["properties"]["natural"] == {"type": "string"}
    assert "natural" in TURN_SCHEMA["required"]
    assert 'NATURAL ("natural")' in TURN_SYSTEM_PROMPT


# ---- which suggestions are worth showing -------------------------------------------


def test_a_suggestion_for_a_correct_sentence_is_kept():
    assert pick_natural(f" {NATURAL} ", SAID, ()) == NATURAL


def test_no_suggestion_when_the_sentence_has_a_real_error():
    assert pick_natural(NATURAL, SAID, (major("a", "b"),)) is None


def test_no_suggestion_when_it_only_repeats_the_sentence():
    assert pick_natural("the final was a little bit sad for me!", SAID, ()) is None


def test_no_suggestion_when_empty():
    assert pick_natural(None, SAID, ()) is None
    assert pick_natural("  ", SAID, ()) is None


# ---- in the session ------------------------------------------------------------------


def said(h) -> TutorSaid:
    return h.of_type(TutorSaid)[-1]


def test_the_session_shows_the_suggestion_without_speaking_it_or_recording_a_mistake(
    make_harness, fake_store, fake_log
):
    h = make_harness([SAID], [TutorReply("I see.", natural=NATURAL)], store=fake_store, log=fake_log)
    h.say()
    assert said(h).natural == NATURAL
    assert fake_store.saves == []  # never a mistake
    assert all(NATURAL not in spoken for spoken in h.tts.spoken)
    assert ("natural", NATURAL) in fake_log.entries


def test_a_suggestion_next_to_a_real_correction_is_dropped(make_harness):
    reply = TutorReply("I see.", (major("I go", "I went"),), natural="I went home.")
    h = make_harness(["I go home"], [reply])
    h.say()
    assert said(h).natural is None


def test_the_switch_is_read_on_every_turn(make_harness):
    enabled = [False]
    h = make_harness(
        [SAID, SAID],
        [TutorReply("a", natural=NATURAL), TutorReply("b", natural=NATURAL)],
        suggest_natural=lambda: enabled[0],
    )
    h.say()
    assert said(h).natural is None
    enabled[0] = True
    h.say()
    assert said(h).natural == NATURAL


def test_without_a_suggestion_the_event_is_unchanged(make_harness):
    h = make_harness(["hello there"], [TutorReply("Hi!")])
    h.say()
    assert said(h) == TutorSaid("Hi!", None, None)


# ---- the setting and the log -------------------------------------------------------------


def test_the_setting_is_on_by_default_and_applies_without_restart():
    from english_tutor.settings.model import RESTART_FIELDS

    assert UserSettings().suggest_natural is True
    spec = {s.key: s for s in by_category(Category.GENERAL)}["suggest_natural"]
    assert spec.control is Control.SWITCH
    assert "suggest_natural" not in RESTART_FIELDS


def test_the_log_labels_the_suggestion(tmp_path):
    log = FileConversationLog(tmp_path)
    log.record("natural", NATURAL)
    assert f"NATURAL: {NATURAL}" in next(tmp_path.glob("*.log")).read_text(encoding="utf-8")
