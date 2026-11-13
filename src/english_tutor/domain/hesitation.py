"""Long pauses in the learner's speech: signs that a phrase is hard to say (pure).

A pause is not a mistake. It is stored in the mistake history with the
``HESITATION`` severity so the learner can practise saying the phrase smoothly.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from .categories import FLUENCY
from .models import Correction, Hesitation, Severity, TimedWord

START_PAUSE_S = 3.0
"""Silence between the push-to-talk press and the first word that counts as a pause."""
GAP_PAUSE_S = 1.2
"""Silence between two words that counts as a pause."""
CONTEXT_WORDS = 2
"""Words kept on each side of a pause to show where it happened."""

_EDGE_PUNCT_RE = re.compile(r"^[^\w']+|[^\w']+$")


def _clean(word: str) -> str:
    return _EDGE_PUNCT_RE.sub("", word.strip())


def _span(words: Sequence[str]) -> str:
    return " ".join(w for w in words if w)


def find_hesitations(
    words: Sequence[TimedWord],
    start_pause_s: float = START_PAUSE_S,
    gap_pause_s: float = GAP_PAUSE_S,
    context: int = CONTEXT_WORDS,
) -> tuple[Hesitation, ...]:
    """Every pause of at least the given length, in the order they happened.

    The recording starts at the push-to-talk press, so the first word's start
    time is how long the learner took to begin.
    """
    texts = [_clean(w.text) for w in words]
    found: list[Hesitation] = []
    if words and words[0].start_s >= start_pause_s and texts[0]:
        found.append(Hesitation("", _span(texts[: context + 1]), round(words[0].start_s, 1)))
    for i in range(1, len(words)):
        gap = words[i].start_s - words[i - 1].end_s
        if gap < gap_pause_s:
            continue
        before = _span(texts[max(0, i - context) : i])
        after = _span(texts[i : i + context])
        if before and after:
            found.append(Hesitation(before, after, round(gap, 1)))
    return tuple(found)


def explanation(item: Hesitation) -> str:
    """One English sentence saying where the pause was, as stored in the history."""
    if item.at_start:
        return f"You took {item.pause_s:.1f} s to start speaking."
    last = item.before.split()[-1]
    first = item.after.split()[0]
    return f"You paused {item.pause_s:.1f} s between '{last}' and '{first}'."


def as_corrections(items: Iterable[Hesitation]) -> tuple[Correction, ...]:
    """Pauses inside a sentence, in the shape the mistake history counts.

    A slow start is left out: it says the question was hard, not which words
    were, and every answer starts differently, so it would only add noise.
    The normalized original and corrected texts are equal, which no real
    correction can be (those are dropped as cosmetic), so keys never collide.
    """
    return tuple(
        Correction(h.marked, h.phrase, explanation(h), Severity.HESITATION, FLUENCY)
        for h in items
        if not h.at_start
    )


def _words_of(text: str) -> list[str]:
    return [w for w in (_clean(part).lower() for part in text.split()) if w]


def pause_inside(phrase: str, pauses: Iterable[Hesitation]) -> Hesitation | None:
    """The first pause between two words that both belong to ``phrase``, if any.

    Used in practice: a pause elsewhere in the answer does not count against
    the phrase being practised.
    """
    wanted = set(_words_of(phrase))
    for item in pauses:
        if item.at_start:
            continue
        last, first = _words_of(item.before)[-1:], _words_of(item.after)[:1]
        if last and first and last[0] in wanted and first[0] in wanted:
            return item
    return None


def restore_times(
    words: Sequence[TimedWord], spans: Sequence[tuple[float, float]]
) -> tuple[TimedWord, ...]:
    """Move words timed on joined speech back to the recording's timeline.

    ``spans`` are the ``(start, end)`` seconds of each stretch of speech in the
    recording; ``words`` were timed on those stretches played back to back. A
    word belongs to the stretch its middle falls in and is kept inside it, so the
    silence between stretches shows up as a gap. Words without letters are dropped.
    """
    if not spans:
        return ()
    offsets: list[float] = []
    position = 0.0
    for start, end in spans:
        offsets.append(position)
        position += end - start
    restored: list[TimedWord] = []
    for word in words:
        if not _clean(word.text):
            continue
        middle = (word.start_s + word.end_s) / 2
        index = max((i for i, offset in enumerate(offsets) if offset <= middle), default=0)
        low = offsets[index]
        high = low + spans[index][1] - spans[index][0]
        shift = spans[index][0] - low
        start = min(max(word.start_s, low), high) + shift
        end = max(min(word.end_s, high), low) + shift
        restored.append(TimedWord(word.text, start, max(start, end)))
    return tuple(restored)


def matching_words(text: str, timed: Sequence[TimedWord]) -> tuple[TimedWord, ...]:
    """The timed words that repeat ``text`` word for word, from the start.

    The timing pass can add words at the end (see ``adapters.whisper_stt``), so
    it stops at the first word that differs; pauses are only found in words the
    learner is shown to have said.
    """
    spoken = _words_of(text)
    kept: list[TimedWord] = []
    for expected, item in zip(spoken, (w for w in timed if _clean(w.text))):
        if _clean(item.text).lower() != expected:
            break
        kept.append(item)
    return tuple(kept)


def retry_feedback(item: Hesitation) -> str:
    """What the coach says when the phrase was used but still with a long pause."""
    last, first = item.before.split()[-1], item.after.split()[0]
    return (
        f"You said it, but you paused {item.pause_s:.1f} seconds between '{last}' and "
        f"'{first}'. Try once more, in one go."
    )


def last_question(reply: str, limit: int = 120) -> str:
    """The question the tutor ended ``reply`` with (or the whole reply), shortened."""
    text = " ".join(reply.split())
    end = text.rfind("?")
    if end != -1:
        start = max(text.rfind(mark, 0, end) for mark in ".!?") + 1
        text = text[start : end + 1].strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
