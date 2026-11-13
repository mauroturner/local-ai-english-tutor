"""How varied the learner's vocabulary was in a session (pure).

Only content words count: very common words (the, and, is, I...) are left out, and
so are words shorter than three letters. The comparison with earlier sessions uses
the words stored with each session.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Iterable

from .corrections import normalize

MIN_LETTERS = 3
MAX_STORED = 400
"""Most words kept per session in the statistics file."""
OVERUSED_AT = 4
"""A content word said this many times or more in one session is listed as "used often"."""
MAX_SHOWN = 8

STOPWORDS = frozenset(
    """the and but for are was were been being have has had does did doing done not nor
    you your yours his her hers its our ours their theirs him she they them this that these
    those what which who whom whose when where why how with without from into onto over
    under about after before again then than too very just also only even still yet can
    could will would shall should may might must get got getting gets let lets say said
    says one two see saw yes yeah okay well really much many some any all each every more
    most such own same other another there here now out off down while because though
    although until since like dont doesnt didnt cant couldnt wont wouldnt isnt arent wasnt
    werent havent hasnt hadnt youre theyre were ive youve weve theyve ill youll well hell
    shell thats whats theres lets""".split()
)
"""Very common words that say nothing about how rich the vocabulary is."""


def content_words(text: str) -> list[str]:
    """The content words of ``text`` in order, lower case, apostrophes removed."""
    words = (w.replace("'", "") for w in normalize(text).split())
    return [w for w in words if len(w) >= MIN_LETTERS and w not in STOPWORDS and w.isalpha()]


def session_words(texts: Iterable[str]) -> tuple[str, ...]:
    """The distinct content words of ``texts``, alphabetical, at most ``MAX_STORED``."""
    return tuple(sorted({w for text in texts for w in content_words(text)}))[:MAX_STORED]


def overused(texts: Iterable[str], at: int = OVERUSED_AT) -> tuple[tuple[str, int], ...]:
    """Content words said at least ``at`` times, most frequent first (at most 3)."""
    counts = Counter(w for text in texts for w in content_words(text))
    ranked = sorted((p for p in counts.items() if p[1] >= at), key=lambda p: (-p[1], p[0]))
    return tuple(ranked[:3])


def new_words(words: Iterable[str], known: Collection[str]) -> tuple[str, ...]:
    """The words that no earlier session used (alphabetical, at most ``MAX_SHOWN``)."""
    return tuple(w for w in words if w not in known)[:MAX_SHOWN]
