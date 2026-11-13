"""Word-by-word comparison of what the learner repeated (or typed) with the target sentence (pure)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum

from .corrections import normalize

_CONTRACTIONS = {
    "i'm": "i am", "you're": "you are", "we're": "we are", "they're": "they are",
    "he's": "he is", "she's": "she is", "it's": "it is", "that's": "that is",
    "there's": "there is", "i've": "i have", "you've": "you have", "we've": "we have",
    "they've": "they have", "i'll": "i will", "you'll": "you will", "we'll": "we will",
    "they'll": "they will", "i'd": "i would", "you'd": "you would", "don't": "do not",
    "doesn't": "does not", "didn't": "did not", "isn't": "is not", "aren't": "are not",
    "wasn't": "was not", "weren't": "were not", "haven't": "have not", "hasn't": "has not",
    "won't": "will not", "wouldn't": "would not", "can't": "cannot", "couldn't": "could not",
    "shouldn't": "should not", "let's": "let us", "what's": "what is", "where's": "where is",
}  # fmt: skip
"""Both spellings count as the same words, so "don't" matches "do not"."""


class Outcome(str, Enum):
    """What happened to one word of the comparison."""

    OK = "ok"
    MISSING = "missing"  # in the target but not said
    EXTRA = "extra"  # said but not in the target
    CHANGED = "changed"  # a different word was said in its place


@dataclass(frozen=True)
class WordDiff:
    """One step of the comparison: the target word, the word said, and what that means."""

    expected: str | None
    said: str | None
    outcome: Outcome


def words(text: str) -> list[str]:
    """The words of ``text`` for comparing: lower case, no punctuation, contractions expanded."""
    out: list[str] = []
    for token in normalize(text).split():
        out.extend(_CONTRACTIONS.get(token, token).split())
    return out


def compare(target: str, said: str) -> tuple[WordDiff, ...]:
    """Align ``said`` with ``target`` and mark every word as ok, missing, extra or changed."""
    wanted, heard = words(target), words(said)
    diffs: list[WordDiff] = []
    for tag, a0, a1, b0, b1 in SequenceMatcher(a=wanted, b=heard, autojunk=False).get_opcodes():
        expected, got = wanted[a0:a1], heard[b0:b1]
        if tag == "equal":
            diffs += [WordDiff(w, w, Outcome.OK) for w in expected]
        elif tag == "delete":
            diffs += [WordDiff(w, None, Outcome.MISSING) for w in expected]
        elif tag == "insert":
            diffs += [WordDiff(None, w, Outcome.EXTRA) for w in got]
        else:  # replace: pair the words up, the rest are missing or extra
            paired = min(len(expected), len(got))
            diffs += [WordDiff(e, g, Outcome.CHANGED) for e, g in zip(expected, got)]
            diffs += [WordDiff(w, None, Outcome.MISSING) for w in expected[paired:]]
            diffs += [WordDiff(None, w, Outcome.EXTRA) for w in got[paired:]]
    return tuple(diffs)


def accuracy(diffs: Sequence[WordDiff]) -> float:
    """Share (0 to 1) of the target's words that were said correctly; 1.0 for an empty target."""
    target = [d for d in diffs if d.expected is not None]
    return sum(1 for d in target if d.outcome is Outcome.OK) / len(target) if target else 1.0


def is_perfect(diffs: Sequence[WordDiff]) -> bool:
    """Whether every word matched and nothing was added."""
    return all(d.outcome is Outcome.OK for d in diffs)


def describe(diffs: Sequence[WordDiff]) -> str:
    """One English line: what was missing, changed and extra; ``Perfect!`` when nothing was."""
    if is_perfect(diffs):
        return "Perfect!"
    parts = []
    missing = [d.expected for d in diffs if d.outcome is Outcome.MISSING]
    changed = [f"'{d.said}' instead of '{d.expected}'" for d in diffs if d.outcome is Outcome.CHANGED]
    extra = [d.said for d in diffs if d.outcome is Outcome.EXTRA]
    if missing:
        parts.append("Missing: " + ", ".join(str(w) for w in missing))
    if changed:
        parts.append("Changed: " + ", ".join(changed))
    if extra:
        parts.append("Extra: " + ", ".join(str(w) for w in extra))
    return ". ".join(parts) + "."
