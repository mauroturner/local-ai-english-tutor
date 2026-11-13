"""Builds the end-of-session report from the recorded turns."""

from __future__ import annotations

import logging

from ..domain.categories import count_categories
from ..domain.corrections import dedupe
from ..domain.fillers import ranked, total_fillers
from ..domain.hesitation import last_question
from ..domain.models import Correction, Hesitation, SessionReport, Severity, Turn
from ..domain.scenarios import FREE, unused_vocabulary
from ..ports import TutorModel

logger = logging.getLogger(__name__)


def collect_errors(
    turns: tuple[Turn, ...],
) -> tuple[tuple[Correction, ...], tuple[Correction, ...]]:
    """Return the unique major and minor corrections of ``turns``."""
    every = [c for turn in turns for c in turn.corrections]
    majors = dedupe(c for c in every if c.severity is Severity.MAJOR)
    minors = dedupe(c for c in every if c.severity is Severity.MINOR)
    return majors, minors


def collect_pauses(
    turns: tuple[Turn, ...],
) -> tuple[tuple[Hesitation, ...], tuple[tuple[str, float], ...]]:
    """The unique pauses inside sentences, and each slow start with the question before it.

    The first turn has no question before it, so its start is never counted.
    """
    pauses: dict[str, Hesitation] = {}
    starts: list[tuple[str, float]] = []
    for previous, turn in zip((None, *turns), turns):
        for item in turn.hesitations:
            if not item.at_start:
                pauses.setdefault(item.marked.lower(), item)
            elif previous is not None:
                starts.append((last_question(previous.tutor_reply), item.pause_s))
    return tuple(pauses.values()), tuple(starts)


def make_report(
    tutor: TutorModel, turns: tuple[Turn, ...], scenario: str = FREE
) -> SessionReport:
    """Collect the errors and ask the tutor for feedback (failures are kept as text)."""
    majors, minors = collect_errors(turns)
    feedback = None
    feedback_error = None
    if turns:
        try:
            feedback = tutor.feedback(turns)
        except Exception as exc:  # the recorded errors are still worth reporting
            logger.warning("Feedback generation failed: %s", exc)
            feedback_error = str(exc)
    pauses, starts = collect_pauses(turns)
    categories = count_categories(c for turn in turns for c in turn.corrections)
    unused = unused_vocabulary(scenario, (turn.user_text for turn in turns)) if turns else ()
    uncertain = tuple(dict.fromkeys(w for turn in turns for w in turn.uncertain))
    return SessionReport(
        len(turns), majors, minors, feedback, feedback_error, pauses, starts, categories, unused,
        uncertain, ranked(total_fillers(turn.user_text for turn in turns)),
    )
