"""Listening and speaking drills: what to say, and how to judge the answer (pure).

Three kinds share one flow: the tutor says a sentence and the learner answers.

- ``SHADOW``: repeat a sentence the tutor just said (or a fixed one).
- ``PAIRS``: read a sentence that holds one word of a minimal pair (ship / sheep);
  the transcript decides which word was heard, so Whisper itself is the judge.
- ``DICTATION``: type what was heard.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from enum import Enum

from .shadowing import accuracy, compare, describe, is_perfect, words


class DrillKind(str, Enum):
    """The three kinds of listening and speaking drill."""

    SHADOW = "shadow"
    PAIRS = "pairs"
    DICTATION = "dictation"


@dataclass(frozen=True)
class Target:
    """One sentence to say or type; ``focus`` and ``other`` are set for a minimal pair."""

    text: str
    focus: str | None = None  # the word of the pair that must be heard
    other: str | None = None  # the word it is easily mistaken for


@dataclass(frozen=True)
class Verdict:
    """The outcome of one answer: whether it was right and what to tell the learner."""

    perfect: bool
    feedback: str


FALLBACK_SENTENCES = (
    "I usually have breakfast at eight o'clock.",
    "Could you tell me where the station is?",
    "We are planning a trip to the mountains next month.",
    "She has been learning English for two years.",
    "What do you like to do on weekends?",
    "I would like a glass of water, please.",
    "They didn't arrive on time because of the traffic.",
    "My brother works in a small company near the river.",
)
"""Used when the tutor has not said a usable sentence yet."""

MIN_WORDS = 4
MAX_WORDS = 14

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

# Each pair: (word a, word b, sentence with a, sentence with b). Both words have the same
# part of speech, so either sentence is grammatical and the speech model cannot "fix" the word
# from context alone. Spanish speakers often mix up the vowels of these pairs.
_PAIRS: tuple[tuple[str, str, str, str], ...] = (
    ("ship", "sheep", "I can see a ship near the farm.", "I can see a sheep near the farm."),
    ("live", "leave", "I want to live here.", "I want to leave here."),
    ("hat", "hut", "I like this hat very much.", "I like this hut very much."),
    ("cap", "cup", "I bought a new cap today.", "I bought a new cup today."),
    ("wash", "watch", "I need to wash it now.", "I need to watch it now."),
    ("pen", "pan", "I need a pen today.", "I need a pan today."),
    ("walk", "work", "I like to walk here.", "I like to work here."),
    ("beat", "bit", "Listen to the beat again.", "Listen to the bit again."),
)  # fmt: skip


def sentences_from(reply: str) -> list[str]:
    """The sentences of ``reply`` that are a sensible length to repeat (4 to 14 words)."""
    parts = _SENTENCE_END.split(" ".join(reply.split()))
    return [s for s in parts if MIN_WORDS <= len(s.split()) <= MAX_WORDS]


def pick_shadow(last_reply: str, rng: random.Random) -> Target:
    """A sentence from the tutor's last reply, or a fixed one when there is none."""
    options = sentences_from(last_reply) or list(FALLBACK_SENTENCES)
    return Target(rng.choice(options))


def pick_pair(rng: random.Random) -> Target:
    """A minimal-pair sentence: one of the two words, chosen at random."""
    a, b, sentence_a, sentence_b = rng.choice(_PAIRS)
    if rng.random() < 0.5:
        return Target(sentence_a, focus=a, other=b)
    return Target(sentence_b, focus=b, other=a)


def pick_dictation(last_reply: str, rng: random.Random) -> Target:
    """A sentence to dictate (same source as shadowing)."""
    return pick_shadow(last_reply, rng)


def judge(target: Target, said: str) -> Verdict:
    """Judge ``said`` (a transcript or typed text) against ``target``."""
    if target.focus is not None and target.other is not None:
        return _judge_pair(target, said)
    diffs = compare(target.text, said)
    if is_perfect(diffs):
        return Verdict(True, "Perfect!")
    return Verdict(False, f"{describe(diffs)} ({round(accuracy(diffs) * 100)}% of the words)")


def _judge_pair(target: Target, said: str) -> Verdict:
    assert target.focus is not None and target.other is not None
    heard = words(said)
    if target.focus in heard and target.other not in heard:
        return Verdict(True, f"I heard '{target.focus}'. Well done!")
    if target.other in heard:
        return Verdict(
            False,
            f"I heard '{target.other}' but the word was '{target.focus}'. Try again.",
        )
    return Verdict(False, f"I did not hear '{target.focus}'. Try again.")
