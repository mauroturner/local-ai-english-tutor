"""A topic of the day that makes the learner practise their weakest kind of mistake (pure)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta

from .progress import SessionStats

RECENT_DAYS = 14
"""Only sessions from the last two weeks decide what is weakest."""

TOPICS: dict[str, tuple[str, ...]] = {
    "verb_tense": (
        "Tell me about your last trip.",
        "What did you do last weekend?",
    ),
    "agreement": (
        "Describe what each person in your family does every day.",
        "Tell me what your best friend likes and doesn't like.",
    ),
    "articles": (
        "Describe your home: what is in each room?",
        "Describe the street where you live.",
    ),
    "prepositions": (
        "Explain how to get from your home to your favourite place.",
        "Describe your daily routine, from morning to night.",
    ),
    "word_order": (
        "Ask me five questions about my life.",
        "Ask me how my day was, and what I usually do at the weekend.",
    ),
    "word_choice": (
        "Describe your favourite meal in as much detail as you can.",
        "Tell me about a film or a series you really liked.",
    ),
    "false_friend": (
        "Tell me about your job or your studies.",
        "Tell me about a famous person from your country.",
    ),
    "plural": (
        "Tell me what you usually buy at the supermarket.",
        "Tell me about the things you have in your bag.",
    ),
    "pronoun": (
        "Tell me about two people you know and how they are different.",
        "Tell me about a story where you helped someone, or someone helped you.",
    ),
}
"""For each kind of mistake, topics that cannot be answered without using it."""


def weakest_category(
    sessions: Sequence[SessionStats], today: date, days: int = RECENT_DAYS
) -> str | None:
    """The kind of mistake made most in the last ``days`` days, or None if there is none."""
    since = today - timedelta(days=days - 1)
    totals: dict[str, int] = {}
    for session in sessions:
        if since <= session.started_at.date() <= today:
            for category, count in session.categories:
                if category in TOPICS:
                    totals[category] = totals.get(category, 0) + count
    if not totals:
        return None
    return max(sorted(totals), key=lambda c: totals[c])


def topic_of_the_day(
    sessions: Sequence[SessionStats], today: date
) -> tuple[str, str] | None:
    """``(category, topic)`` aimed at the weakest category; the topic changes each day."""
    category = weakest_category(sessions, today)
    if category is None:
        return None
    options = TOPICS[category]
    return category, options[today.toordinal() % len(options)]
