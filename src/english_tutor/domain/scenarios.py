"""Role-play situations the learner can practise, and the vocabulary each one needs (pure)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .corrections import normalize

FREE = "free"
"""No scenario: an ordinary conversation."""

MAX_UNUSED_SHOWN = 6


@dataclass(frozen=True)
class Scenario:
    """One situation: who the tutor plays, how it starts and which phrases it calls for."""

    key: str
    role: str
    opening: str
    vocabulary: tuple[str, ...]


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        "job_interview",
        "a friendly hiring manager interviewing the learner for a job",
        "Thanks for coming in today. Please, have a seat. Can you tell me a little about yourself?",
        ("experience", "strengths", "weakness", "responsibilities", "team", "deadline",
         "salary", "skills", "look forward to", "background"),
    ),
    Scenario(
        "restaurant",
        "a polite waiter taking the learner's order in a restaurant",
        "Good evening, and welcome! Can I get you something to drink while you look at the menu?",
        ("menu", "order", "recommend", "I'd like", "starter", "main course", "dessert",
         "bill", "allergic", "tip"),
    ),
    Scenario(
        "doctor",
        "a calm family doctor seeing the learner at the clinic",
        "Hello, please take a seat. What brings you in today?",
        ("symptoms", "headache", "fever", "prescription", "appointment", "pain",
         "I've been feeling", "allergic", "medicine", "how long"),
    ),
    Scenario(
        "airport",
        "an airline check-in agent at the airport",
        "Good morning! May I see your passport and your ticket, please?",
        ("flight", "boarding pass", "luggage", "gate", "delayed", "passport",
         "check in", "customs", "window seat", "carry-on"),
    ),
    Scenario(
        "small_talk",
        "a friendly neighbour chatting with the learner",
        "Hi! Nice to see you. How has your week been so far?",
        ("weekend", "how about you", "hobby", "weather", "by the way", "actually",
         "sounds like fun", "lately", "I'm into", "busy"),
    ),
    Scenario(
        "meeting",
        "a colleague in a team meeting at work",
        "Okay, let's get started. Could you give us a quick update on your project?",
        ("agenda", "update", "deadline", "follow up", "action item", "schedule",
         "on track", "feedback", "I suggest", "let's discuss"),
    ),
)

KEYS = (FREE, *(s.key for s in SCENARIOS))
"""Every valid scenario key, the free conversation first."""


def get_scenario(key: str) -> Scenario | None:
    """The scenario named ``key``; None for the free conversation or an unknown key."""
    return next((s for s in SCENARIOS if s.key == key), None)


def scenario_block(key: str) -> str:
    """The SCENARIO section added to the turn prompt; empty for a free conversation."""
    scenario = get_scenario(key)
    if scenario is None:
        return ""
    return "\n".join(
        [
            "SCENARIO (role-play):",
            f"- You are {scenario.role}. Stay in this role for the whole conversation.",
            f'- You already opened with: "{scenario.opening}" Continue from the learner\'s answer.',
            "- Keep the same rules for \"reply\" and \"errors\": the role never changes how you correct.",
        ]
    )


def with_scenario(prompt: str, key: str) -> str:
    """``prompt`` followed by the scenario section (unchanged for a free conversation)."""
    block = scenario_block(key)
    return f"{prompt.rstrip(chr(10))}\n\n{block}" if block else prompt


def unused_vocabulary(key: str, said: Iterable[str]) -> tuple[str, ...]:
    """Key phrases of the scenario that none of the learner's sentences contained.

    Matching is on whole words after normalising, so "menus" does not count as
    "menu"; the list is a hint, not a test. At most ``MAX_UNUSED_SHOWN`` are returned.
    """
    scenario = get_scenario(key)
    if scenario is None:
        return ()
    haystack = f" {' '.join(normalize(text) for text in said)} "
    missing = tuple(p for p in scenario.vocabulary if f" {normalize(p)} " not in haystack)
    return missing[:MAX_UNUSED_SHOWN]
