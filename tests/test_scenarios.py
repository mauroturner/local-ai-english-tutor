"""Role-play scenarios: prompt, opening line, vocabulary hints and the session flow."""

from __future__ import annotations

from datetime import datetime

import pytest

from english_tutor.adapters.json_session_store import JsonSessionStore
from english_tutor.application.events import ScenarioChanged, TutorSaid
from english_tutor.application.report import make_report
from english_tutor.application.scenario_choice import ScenarioChoice
from english_tutor.domain.formatting import format_report
from english_tutor.domain.models import SessionState, TutorReply, Turn
from english_tutor.domain.prompts import TURN_SYSTEM_PROMPT
from english_tutor.domain.scenarios import (
    FREE,
    KEYS,
    MAX_UNUSED_SHOWN,
    SCENARIOS,
    get_scenario,
    scenario_block,
    unused_vocabulary,
    with_scenario,
)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.key)
def test_every_scenario_is_complete(scenario):
    assert scenario.role and scenario.opening.endswith("?") and len(scenario.vocabulary) >= 8
    assert len(set(scenario.vocabulary)) == len(scenario.vocabulary)


def test_keys_start_with_the_free_conversation_and_are_unique():
    assert KEYS[0] == FREE and len(set(KEYS)) == len(KEYS) == len(SCENARIOS) + 1


def test_the_free_conversation_leaves_the_prompt_untouched():
    assert with_scenario(TURN_SYSTEM_PROMPT, FREE) == TURN_SYSTEM_PROMPT
    assert with_scenario(TURN_SYSTEM_PROMPT, "nonsense") == TURN_SYSTEM_PROMPT
    assert scenario_block(FREE) == ""


def test_a_scenario_adds_the_role_and_the_opening_line():
    prompt = with_scenario(TURN_SYSTEM_PROMPT, "restaurant")
    scenario = get_scenario("restaurant")
    assert prompt.startswith(TURN_SYSTEM_PROMPT.rstrip("\n"))
    assert scenario.role in prompt and scenario.opening in prompt
    assert "never changes how you correct" in prompt


def test_unused_vocabulary_lists_what_was_not_said():
    said = ["I would like to see the menu", "I'd like the soup, and the bill please"]
    missing = unused_vocabulary("restaurant", said)
    assert "menu" not in missing and "I'd like" not in missing and "bill" not in missing
    assert "recommend" in missing and "dessert" in missing


def test_unused_vocabulary_matches_whole_words_only():
    assert "menu" in unused_vocabulary("restaurant", ["the menus were big"])


def test_unused_vocabulary_is_capped_and_empty_without_a_scenario():
    assert len(unused_vocabulary("restaurant", [])) == MAX_UNUSED_SHOWN
    assert unused_vocabulary(FREE, ["anything"]) == ()


# ---- the report -----------------------------------------------------------------------


class _Tutor:
    def feedback(self, turns):
        raise RuntimeError("no model")


def turn(text) -> Turn:
    return Turn(1, text, "ok", (), None)


def test_the_report_lists_unused_scenario_phrases():
    report = make_report(_Tutor(), (turn("I want the menu"),), "restaurant")
    assert "menu" not in report.unused_vocabulary and "order" in report.unused_vocabulary
    assert "Useful for this situation (not used yet):" in format_report(report)


def test_a_free_conversation_report_has_no_vocabulary_line():
    report = make_report(_Tutor(), (turn("hello"),))
    assert report.unused_vocabulary == ()
    assert "Useful for this situation" not in format_report(report)


# ---- the session ---------------------------------------------------------------------------


def test_picking_a_scenario_opens_it_with_the_tutors_line(make_harness, fake_log):
    choice = ScenarioChoice()
    h = make_harness(log=fake_log, scenario=choice)
    h.session.set_scenario("airport")
    opening = get_scenario("airport").opening
    assert choice.key == "airport" and h.session.scenario == "airport"
    assert h.of_type(ScenarioChanged)[-1].key == "airport"
    assert h.of_type(TutorSaid)[-1].text == opening
    assert h.tts.spoken[-1] == opening and ("tutor", opening) in fake_log.entries
    assert h.session.state is SessionState.IDLE


def test_the_free_conversation_says_nothing_when_picked(make_harness):
    h = make_harness()
    h.session.set_scenario(FREE)
    assert h.of_type(TutorSaid) == [] and h.tts.spoken == []


def test_an_unknown_scenario_becomes_free(make_harness):
    h = make_harness()
    h.session.set_scenario("pirates")
    assert h.session.scenario == FREE


def test_the_scenario_cannot_change_after_the_first_answer(make_harness):
    h = make_harness(["hello there"], [TutorReply("Hi!")])
    h.say()
    h.session.set_scenario("doctor")
    assert h.session.scenario == FREE


def test_ending_the_session_returns_to_the_free_conversation_and_tells_the_ui(
    make_harness, fake_stats
):
    h = make_harness(["I want the menu"], [TutorReply("Sure.")], session_stats=fake_stats)
    h.session.set_scenario("restaurant")
    h.say()
    h.session.end_session()
    assert h.session.scenario == FREE
    assert h.of_type(ScenarioChanged)[-1].key == FREE
    assert fake_stats.sessions[0].scenario == "restaurant"


def test_a_free_session_stores_no_scenario(make_harness, fake_stats):
    h = make_harness(["hello there"], [TutorReply("Hi!")], session_stats=fake_stats)
    h.say()
    h.session.end_session()
    assert fake_stats.sessions[0].scenario is None


def test_the_scenario_is_stored_with_the_session(tmp_path):
    from english_tutor.domain.progress import SessionStats

    store = JsonSessionStore(tmp_path / "sessions.json")
    stats = SessionStats(datetime(2026, 11, 13, 9), 60.0, 2, 30, 10.0, 0, 1, 0, 0, (), "doctor")
    store.append(stats)
    store.append(SessionStats(datetime(2026, 11, 13, 10), 60.0, 2, 30, 10.0, 0, 1, 0, 0))
    assert [s.scenario for s in store.load()] == ["doctor", None]


def test_the_model_prompt_follows_the_current_scenario():
    from english_tutor.adapters.ollama_chat import OllamaTutorModel

    sent = []

    class Http:
        def post(self, url, json, timeout):
            sent.append(json["messages"][0]["content"])
            raise RuntimeError("stop here")

    choice = ScenarioChoice()
    tutor = OllamaTutorModel("http://x", "m", 1.0, 0.3, session=Http(), scenario=lambda: choice.key)
    for key in ("doctor", FREE):
        choice.set(key)
        with pytest.raises(Exception):  # noqa: B017 - the fake server only records the request
            tutor.reply([], "hello")
    assert "SCENARIO" in sent[0] and "SCENARIO" not in sent[1]
