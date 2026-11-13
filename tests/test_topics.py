"""Topic of the day: aimed at the weakest category of the last two weeks."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from english_tutor import i18n
from english_tutor.domain.categories import MODEL_CATEGORIES
from english_tutor.domain.progress import SessionStats
from english_tutor.domain.topics import RECENT_DAYS, TOPICS, topic_of_the_day, weakest_category
from english_tutor.ui.goal import topic_text

TODAY = date(2026, 11, 13)


def session(days_ago, **counts) -> SessionStats:
    when = datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time()).replace(hour=9)
    return SessionStats(when, 60.0, 3, 50, 20.0, 1, 1, 0, 0, tuple(counts.items()))


def test_every_model_category_has_topics_except_other():
    assert set(TOPICS) == set(MODEL_CATEGORIES) - {"other"}
    assert all(len(options) >= 2 for options in TOPICS.values())


def test_the_most_frequent_category_of_recent_sessions_wins():
    sessions = [session(1, articles=2, plural=1), session(3, plural=2)]
    assert weakest_category(sessions, TODAY) == "plural"


def test_old_sessions_are_ignored():
    old = session(RECENT_DAYS, verb_tense=9)
    assert weakest_category([old], TODAY) is None
    assert weakest_category([session(RECENT_DAYS - 1, verb_tense=1)], TODAY) == "verb_tense"


def test_ties_are_broken_by_name_so_the_answer_is_stable():
    assert weakest_category([session(0, plural=2, articles=2)], TODAY) == "articles"


def test_unknown_categories_and_empty_history_give_nothing():
    assert weakest_category([session(0, banana=5)], TODAY) is None
    assert weakest_category([], TODAY) is None
    assert topic_of_the_day([], TODAY) is None


def test_the_topic_belongs_to_the_category_and_changes_with_the_day():
    sessions = [session(0, verb_tense=3)]
    category, today_topic = topic_of_the_day(sessions, TODAY)
    _, tomorrow_topic = topic_of_the_day(sessions, TODAY + timedelta(days=1))
    assert category == "verb_tense"
    assert today_topic in TOPICS[category] and tomorrow_topic in TOPICS[category]
    assert today_topic != tomorrow_topic


@pytest.fixture
def english():
    i18n.set_language("en")


def test_the_main_window_line_names_the_topic_and_what_it_practises(english):
    text = topic_text([session(0, prepositions=2)], TODAY)
    assert text.startswith("Topic for today: ")
    assert "prepositions" in text.lower()


def test_no_line_without_a_weak_category(english):
    assert topic_text([], TODAY) == ""
