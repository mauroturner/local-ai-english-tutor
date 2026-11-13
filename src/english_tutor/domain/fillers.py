"""Filler sounds in the learner's speech: um, uh, er, hmm (pure).

Whisper keeps these English fillers in the literal transcript (checked with real
audio), so they can be counted. Words that are also real words, such as "like" or
"you know", are not counted, and the Spanish "eh" is not reliable (Whisper turns
it into other letters), so neither appears here.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence

from .corrections import normalize

_ALIASES = {
    "um": "um", "umm": "um", "uhm": "um", "uh": "uh", "uhh": "uh", "er": "er", "erm": "er",
    "err": "er", "hmm": "hmm", "hm": "hmm", "hmmm": "hmm",
}  # fmt: skip
"""Spelling Whisper may use -> the filler it is counted as."""


def count_fillers(text: str) -> Counter[str]:
    """How many times each filler occurs in ``text`` (case and punctuation ignored)."""
    return Counter(_ALIASES[w] for w in normalize(text).split() if w in _ALIASES)


def total_fillers(texts: Iterable[str]) -> Counter[str]:
    """The fillers of every text added together."""
    total: Counter[str] = Counter()
    for text in texts:
        total.update(count_fillers(text))
    return total


def ranked(counts: Counter[str]) -> tuple[tuple[str, int], ...]:
    """``(filler, count)`` pairs, most frequent first, ties by name."""
    return tuple(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def filler_line(counts: Sequence[tuple[str, int]]) -> str:
    """``Filler words: um (3), uh (2)``; empty when there were none."""
    if not counts:
        return ""
    return "Filler words: " + ", ".join(f"{word} ({n})" for word, n in counts)
