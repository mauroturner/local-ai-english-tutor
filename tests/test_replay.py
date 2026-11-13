"""Repeat the tutor's last words, at the level's pace or more slowly."""

from __future__ import annotations

import dataclasses

from english_tutor.application.session import SLOWER_SPEECH
from english_tutor.domain.learner import LearnerProfile, profile_block, speech_scale
from english_tutor.domain.models import SessionState, TutorReply
from english_tutor.settings.model import UserSettings, learner_profile


def test_repeat_says_the_last_words_again_and_returns_to_idle(make_harness):
    h = make_harness(["hello there"], [TutorReply("Nice to meet you!")])
    h.say()
    first = h.tts.spoken[-1]
    h.session.repeat_last()
    assert h.tts.spoken == [first, first]
    assert h.tts.scales[-1] == 1.0
    assert h.session.state is SessionState.IDLE


def test_repeat_slower_stretches_the_speech(make_harness):
    h = make_harness(["hello there"], [TutorReply("Nice to meet you!")])
    h.say()
    h.session.repeat_last(slower=True)
    assert h.tts.scales[-1] == SLOWER_SPEECH
    assert h.tts.spoken[-1] == h.tts.spoken[0]


def test_slower_comes_on_top_of_the_levels_own_pace(make_harness):
    h = make_harness(["hello there"], [TutorReply("Hi!")], speech_scale=lambda: 1.15)
    h.say()
    h.session.repeat_last(slower=True)
    assert h.tts.scales == [1.15, 1.15 * SLOWER_SPEECH]


def test_nothing_to_repeat_before_the_tutor_spoke(make_harness):
    h = make_harness()
    h.session.repeat_last()
    assert h.tts.spoken == []
    assert h.session.state is SessionState.IDLE


def test_repeat_is_ignored_without_voice_output(make_harness):
    h = make_harness(["hello there"], [TutorReply("Hi!")], tts_available=False)
    h.say()
    h.session.repeat_last()
    assert h.tts.spoken == []
    assert h.session.state is SessionState.IDLE


def test_repeat_is_ignored_while_the_session_is_busy(make_harness):
    h = make_harness(["hello there"], [TutorReply("Hi!")])
    h.say()
    h.session._state = SessionState.THINKING  # a turn is in progress
    h.session.repeat_last()
    assert len(h.tts.spoken) == 1


def test_the_report_summary_can_be_repeated_too(make_harness):
    h = make_harness(["hello there"], [TutorReply("Hi!")])
    h.say()
    h.session.end_session()
    h.session.repeat_last()
    assert h.tts.spoken[-1] == h.tts.spoken[-2] == "Nice work."


# ---- level and pace -----------------------------------------------------------------


def test_only_the_elementary_level_speaks_more_slowly():
    assert speech_scale("A2") > 1.0
    assert [speech_scale(level) for level in ("B1", "B2", "C1", "??")] == [1.0] * 4


def test_the_profile_block_states_the_level_and_its_rules():
    block = profile_block(LearnerProfile("Mauro", "he", "A2"))
    assert "English level (CEFR): A2" in block and "ONE error" in block
    assert "English level (CEFR): C1" in profile_block(LearnerProfile(level="C1"))


def test_an_unknown_level_falls_back_to_the_default():
    assert "English level (CEFR): B1" in profile_block(LearnerProfile(level="Z9"))


def test_the_level_setting_reaches_the_tutor_prompt():
    settings = dataclasses.replace(UserSettings(), level="B2")
    assert learner_profile(settings).level == "B2"
    assert UserSettings().level == "B1"
